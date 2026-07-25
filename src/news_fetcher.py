"""
新闻抓取模块 — 从 RSS 源获取中文新闻
支持多源聚合、日期过滤、标题去重、代理自动检测
"""

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 北京时间 (UTC+8)
CST = timezone(timedelta(hours=8))


@dataclass
class NewsItem:
    """标准化新闻条目"""
    title: str
    url: str
    source: str          # 来源名称，如 "BBC 中文"
    summary: str = ""
    published: Optional[datetime] = None

    def __hash__(self):
        # 用标题前20字做去重
        return hash(self.title[:20])


class NewsFetcher:
    """多源新闻抓取器，支持代理/直连分离"""

    def __init__(self, sources: list[dict], max_per_source: int = 15,
                 max_total: int = 40, proxy_sources: list[dict] | None = None):
        self.sources = sources           # 直连源
        self.proxy_sources = proxy_sources or []  # 需要代理的源
        self.max_per_source = max_per_source
        self.max_total = max_total

        # 检查环境变量中的代理设置
        self.proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy") or os.getenv("HTTP_PROXY")
        if self.proxy:
            logger.info(f"检测到代理配置: {self.proxy}")

        # 创建两个 session：一个直连，一个走代理
        self.direct_session = self._make_session()
        self.proxy_session = self._make_session(use_proxy=True) if self.proxy else None

    def _make_session(self, use_proxy: bool = False) -> requests.Session:
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        if use_proxy and self.proxy:
            s.proxies = {"http": self.proxy, "https": self.proxy}
        return s

    def fetch_all(self) -> list[NewsItem]:
        """从所有源抓取新闻，去重、过滤"""
        all_items: list[NewsItem] = []

        # ── 1. 抓取直连源 ──
        logger.info(f"--- 直连源 ({len(self.sources)} 个) ---")
        for src in self.sources:
            items = self._fetch_one(src, use_proxy=False)
            all_items.extend(items)

        # ── 2. 抓取代理源（如果配置了代理） ──
        if self.proxy_sources:
            if self.proxy:
                logger.info(f"--- 代理源 ({len(self.proxy_sources)} 个) ---")
                for src in self.proxy_sources:
                    items = self._fetch_one(src, use_proxy=True)
                    all_items.extend(items)
            else:
                logger.warning(
                    f"[警告] 已配置 {len(self.proxy_sources)} 个代理源，但未设置 HTTPS_PROXY 环境变量，跳过"
                )
                logger.warning("   如需启用，请在 .env 中设置: HTTPS_PROXY=http://your-proxy:port")

        # ── 3. 全局去重 ──
        deduped = self._deduplicate(all_items)
        logger.info(f"去重后共 {len(deduped)} 条新闻（原始 {len(all_items)} 条）")

        result = deduped[: self.max_total]
        return result

    def _fetch_one(self, src: dict, use_proxy: bool = False) -> list[NewsItem]:
        """抓取单个源"""
        name = src.get("name", urlparse(src["url"]).netloc)
        url = src["url"]
        session = self.proxy_session if use_proxy else self.direct_session

        try:
            logger.info(f"正在抓取: {name} ({url})")
            items = self._fetch_rss(url, name, session)
            logger.info(f"  ✓ {name}: 获取 {len(items)} 条")

            # 过滤最近的新闻
            recent_items = self._filter_recent(items, days=1)
            if len(recent_items) < len(items):
                logger.info(f"  → 过滤后（昨天/今天）: {len(recent_items)} 条")

            return recent_items[: self.max_per_source]
        except requests.Timeout as e:
            logger.warning(f"  ✗ {name} 连接超时: {e}")
        except requests.ConnectionError as e:
            logger.warning(f"  ✗ {name} 连接失败（可能需要代理）: {e}")
        except Exception as e:
            logger.warning(f"  ✗ {name} 抓取异常: {type(e).__name__}: {e}")
        return []

    def _fetch_rss(self, url: str, source_name: str, session: requests.Session) -> list[NewsItem]:
        """解析单个 RSS 源"""
        # 先用 requests 获取（处理跳转和编码）
        resp = session.get(url, timeout=15)
        resp.raise_for_status()

        # 有些"RSS"源返回的是 HTML 页面，需要判断
        content_type = resp.headers.get("Content-Type", "")
        if "html" in content_type and "xml" not in content_type:
            # 可能是网站首页，不是真正的 RSS
            logger.debug(f"  {source_name}: Content-Type 是 HTML，尝试作为 RSS 解析")

        content = resp.content
        feed = feedparser.parse(content)

        if not feed.entries:
            # 可能是 feedparser 解析失败，检查是否有 bozo 错误
            if hasattr(feed, "bozo_exception") and feed.bozo_exception:
                logger.debug(f"  {source_name}: feedparser bozo: {feed.bozo_exception}")
            return []

        items = []
        for entry in feed.entries:
            title = self._clean_text(entry.get("title", ""))
            if not title or len(title) < 4:
                continue

            link = entry.get("link", "")
            summary = self._clean_html(entry.get("summary", entry.get("description", "")))

            # 解析发布时间
            published = None
            for attr in ("published_parsed", "updated_parsed"):
                if hasattr(entry, attr):
                    val = getattr(entry, attr)
                    if val:
                        try:
                            published = datetime(*val[:6], tzinfo=timezone.utc)
                            break
                        except (TypeError, ValueError):
                            pass

            items.append(NewsItem(
                title=title,
                url=link,
                source=source_name,
                summary=summary[:200] if summary else "",
                published=published,
            ))

        return items

    def _filter_recent(self, items: list[NewsItem], days: int = 1) -> list[NewsItem]:
        """过滤最近 N 天的新闻（保留无时间戳的新闻，放宽到2天避免遗漏）"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days + 1)
        result = []
        for item in items:
            if item.published is None:
                result.append(item)  # 无时间戳的也保留
            elif item.published >= cutoff:
                result.append(item)
        return result

    def _deduplicate(self, items: list[NewsItem]) -> list[NewsItem]:
        """标题相似度去重"""
        seen_titles = set()
        result = []

        for item in items:
            # 取标题前 15 个字符做简易去重
            key = re.sub(r"\s+", "", item.title)[:15]
            if key and key not in seen_titles:
                seen_titles.add(key)
                result.append(item)

        return result

    @staticmethod
    def _clean_text(text: str) -> str:
        """清理文本中的 HTML 实体和多余空白"""
        if not text:
            return ""
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _clean_html(html: str) -> str:
        """去除 HTML 标签，保留纯文本"""
        if not html:
            return ""
        try:
            soup = BeautifulSoup(html, "lxml")
            return soup.get_text(separator=" ", strip=True)
        except Exception:
            return NewsFetcher._clean_text(html)

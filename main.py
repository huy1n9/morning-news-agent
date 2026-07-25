#!/usr/bin/env python3
"""
每日早报 AI Agent — 主入口

每天 7:00 自动运行：
  1. 从多个 RSS 源抓取前一天的中文新闻
  2. 调用 DeepSeek API 整理成结构化早报
  3. 通过 163 邮箱发送 HTML 邮件

配置：
  - API Key 等信息 → .env 文件
  - 新闻源、模型参数    → config.yaml
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

# 项目根目录
ROOT_DIR = Path(__file__).parent.absolute()

# 加载环境变量
load_dotenv(ROOT_DIR / ".env")

# 加载配置
with open(ROOT_DIR / "config.yaml", "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

# 配置日志
LOG_LEVEL = os.getenv("LOG_LEVEL", CONFIG.get("logging", {}).get("level", "INFO"))
LOG_FILE = ROOT_DIR / CONFIG.get("logging", {}).get("file", "logs/morning-news.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("morning-news")

# 北京时间
CST = timezone(timedelta(hours=8))

# === 导入模块 ===
from src.news_fetcher import NewsFetcher
from src.ai_formatter import AIFormatter
from src.email_sender import EmailSender


def get_env_or_config(env_key: str, config_path: str, default: str = "") -> str:
    """优先读环境变量，其次是 config.yaml，最后是默认值"""
    keys = config_path.split(".")
    val = CONFIG
    for k in keys:
        val = val.get(k, {}) if isinstance(val, dict) else {}
    config_val = val if isinstance(val, str) else default
    return os.getenv(env_key, config_val)


def main():
    logger.info("=" * 50)
    logger.info("📰 每日早报 Agent 启动")
    logger.info("=" * 50)

    # ── 1. 配置检查 ──────────────────────────────────
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not deepseek_api_key:
        logger.error("❌ 未设置 DEEPSEEK_API_KEY，请在 .env 文件中配置")
        sys.exit(1)

    email_from = os.getenv("EMAIL_FROM", "")
    email_to = os.getenv("EMAIL_TO", "")
    email_password = os.getenv("EMAIL_PASSWORD", "")

    smtp_server = os.getenv("EMAIL_SMTP_SERVER", "smtp.163.com")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "465"))

    if not all([email_from, email_to, email_password]):
        logger.error("❌ 邮箱配置不完整，请检查 .env 文件中的 EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD")
        logger.info("提示: 163 邮箱需要开启 SMTP 服务并获取授权码 → https://mail.163.com/ > 设置 > POP3/SMTP/IMAP")
        sys.exit(1)

    # ── 2. 抓取新闻 ──────────────────────────────────
    logger.info("\n📡 第1步：抓取新闻...")
    sources = CONFIG.get("news", {}).get("sources", [])
    if not sources:
        logger.error("❌ 未配置新闻源，请检查 config.yaml")
        sys.exit(1)

    proxy_sources = CONFIG.get("news", {}).get("proxy_sources", [])

    fetcher = NewsFetcher(
        sources=sources,
        max_per_source=CONFIG["news"].get("max_per_source", 15),
        max_total=CONFIG["news"].get("max_total", 40),
        proxy_sources=proxy_sources,
    )
    news_items = fetcher.fetch_all()

    if not news_items:
        logger.warning("⚠️ 未获取到任何新闻，将发送空报告")

    # ── 3. AI 格式化 ──────────────────────────────────
    logger.info("\n🤖 第2步：DeepSeek AI 格式化...")
    formatter = AIFormatter(
        api_key=deepseek_api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1",
        model=os.getenv("DEEPSEEK_MODEL") or CONFIG["deepseek"]["model"],
        max_tokens=CONFIG["deepseek"].get("max_tokens", 4096),
        temperature=CONFIG["deepseek"].get("temperature", 0.3),
    )
    # 合并所有源名称
    all_source_names = [s.get("name", s["url"]) for s in sources + proxy_sources]
    html_body = formatter.format_news(news_items, all_source_names)

    # ── 4. 发送邮件 ──────────────────────────────────
    logger.info("\n📧 第3步：发送邮件...")
    today_str = datetime.now(CST).strftime("%Y-%m-%d")
    subject_template = CONFIG["email"].get("subject_template", "📰 每日早报 - {date}")
    subject = subject_template.format(date=today_str)

    sender = EmailSender(
        smtp_server=smtp_server,
        smtp_port=smtp_port,
        from_addr=email_from,
        password=email_password,
        use_ssl=True,
    )

    success = sender.send(to_addr=email_to, subject=subject, html_body=html_body)

    # ── 5. 结果 ──────────────────────────────────
    if success:
        logger.info(f"\n✅ 早报发送成功！请检查 {email_to} 的收件箱")
        logger.info(f"   主题: {subject}")
        logger.info(f"   新闻数: {len(news_items)} 条")
    else:
        logger.error("\n❌ 早报发送失败，请查看上方日志排查问题")
        sys.exit(1)


def _parse_args():
    parser = argparse.ArgumentParser(description="每日早报 AI Agent")
    parser.add_argument("--test", action="store_true",
                        help="测试模式：只抓取新闻并格式化，不发送邮件，输出到控制台")
    parser.add_argument("--output", type=str, metavar="FILE",
                        help="将 HTML 邮件内容保存到指定文件")
    parser.add_argument("--fetch-only", action="store_true",
                        help="只抓取新闻，不格式化也不发送")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.fetch_only:
        # 仅抓取模式
        logger.info("模式: 仅抓取新闻")
        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not deepseek_api_key:
            logger.warning("⚠️ 未设置 DEEPSEEK_API_KEY（仅抓取不需要，但发邮件需要）")

        sources = CONFIG.get("news", {}).get("sources", [])
        proxy_sources = CONFIG.get("news", {}).get("proxy_sources", [])

        fetcher = NewsFetcher(
            sources=sources,
            max_per_source=CONFIG["news"].get("max_per_source", 15),
            max_total=CONFIG["news"].get("max_total", 40),
            proxy_sources=proxy_sources,
        )
        items = fetcher.fetch_all()
        print(f"\n📊 共获取 {len(items)} 条新闻:\n")
        for i, item in enumerate(items, 1):
            time_str = item.published.strftime("%m-%d %H:%M") if item.published else "?"
            print(f"{i:2d}. [{item.source:10s}] {item.title[:70]}")
            print(f"     {time_str}  {item.url}")
        sys.exit(0)

    if args.test:
        logger.info("=" * 50)
        logger.info("📰 每日早报 Agent — 测试模式")
        logger.info("=" * 50)
        logger.info("（测试模式：抓取 + 格式化，邮件内容输出到控制台）\n")

        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not deepseek_api_key:
            logger.error("❌ 未设置 DEEPSEEK_API_KEY，请在 .env 文件中配置")
            sys.exit(1)

        # 抓取
        sources = CONFIG.get("news", {}).get("sources", [])
        proxy_sources = CONFIG.get("news", {}).get("proxy_sources", [])
        fetcher = NewsFetcher(
            sources=sources,
            max_per_source=CONFIG["news"].get("max_per_source", 15),
            max_total=CONFIG["news"].get("max_total", 40),
            proxy_sources=proxy_sources,
        )
        items = fetcher.fetch_all()

        if not items:
            logger.warning("⚠️ 未获取到任何新闻")
            sys.exit(0)

        # 格式化
        formatter = AIFormatter(
            api_key=deepseek_api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            model=os.getenv("DEEPSEEK_MODEL", CONFIG["deepseek"]["model"]),
            max_tokens=CONFIG["deepseek"].get("max_tokens", 4096),
            temperature=CONFIG["deepseek"].get("temperature", 0.3),
        )
        all_source_names = [s.get("name", s["url"]) for s in sources + proxy_sources]
        html_body = formatter.format_news(items, all_source_names)

        # 输出到控制台
        print("\n" + "=" * 60)
        print("  📧 邮件预览（HTML 会被邮件客户端渲染）")
        print("=" * 60)
        print(html_body)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(html_body)
            logger.info(f"\nHTML 已保存到: {args.output}")

        sys.exit(0)

    main()

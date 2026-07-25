"""
AI 格式化模块 — 使用 DeepSeek API 将原始新闻整理为结构化早报
"""

import json
import logging
from datetime import timedelta, timezone

from openai import OpenAI

logger = logging.getLogger(__name__)

# 北京时间
CST = timezone(timedelta(hours=8))

# DeepSeek 格式化提示词
SYSTEM_PROMPT = """你是一位资深的新闻编辑，每天早上为读者制作一份简洁、专业的"每日早报"。

你的任务是将提供的原始新闻列表，整理成一份结构清晰、重点突出的新闻摘要。

请严格按以下格式输出 HTML 邮件内容（邮件标题已包含日期，正文无需再写标题）：

<p style="color:#666;">共 {count} 条重要新闻，祝你一天好心情 ☀️</p>

<h3>🔥 要闻速览（Top 5）</h3>
<ol>
  <li><strong>一句话标题概括</strong> — 1-2句新闻要点</li>
</ol>

<h3>🌍 国际</h3>
<ul>
  <li><strong>原标题</strong>：内容简介（20-40字）<br><small>来源：XXX</small></li>
</ul>

<h3>💻 科技</h3>
<ul>
  <li>...</li>
</ul>

<h3>💰 财经</h3>
<ul>
  <li>...</li>
</ul>

<h3>🗞️ 其他值得关注</h3>
<ul>
  <li>...</li>
</ul>

<hr>
<p style="color:#999;font-size:12px;">本早报由 AI 自动生成，新闻来源包括：{sources}<br>仅供参考，不构成任何建议。</p>

要求：
1. 对新闻进行分类（要闻、国际、科技、财经、其他），每类5-10条
2. 每条新闻用 40-80 字做精炼总结，保留关键信息
3. 同一事件的报道合并为一条，选择最权威的来源
4. 优先报道与中文读者相关的新闻
5. 如果没有某类新闻，可省略该版块
6. 只输出 HTML 片段（从计数行到末尾），不要 ```html``` 标记
"""


class AIFormatter:
    """使用 DeepSeek API 格式化新闻"""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com/v1",
                 model: str = "deepseek-chat", max_tokens: int = 4096, temperature: float = 0.3):
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def format_news(self, news_items: list, source_names: list[str]) -> str:
        """
        将新闻列表格式化为 HTML 早报邮件

        Args:
            news_items: NewsItem 对象列表
            source_names: 新闻来源名称列表

        Returns:
            HTML 格式的邮件正文
        """
        if not news_items:
            return self._empty_report(source_names)

        # 构建新闻文本输入
        news_text = self._build_news_text(news_items)
        prompt = SYSTEM_PROMPT.replace("{count}", str(len(news_items)))
        prompt = prompt.replace("{sources}", "、".join(source_names[:6]))

        print(f"\n🔍 [DEBUG] 准备调用 DeepSeek API")
        print(f"   model     = {self.model}")
        print(f"   base_url  = {self.client.base_url}")
        print(f"   api_key   = {self.client.api_key[:8]}***{self.client.api_key[-4:] if len(self.client.api_key) > 4 else '????'}")
        print(f"   news条数  = {len(news_items)}")
        print(f"   max_tokens= {self.max_tokens}")
        logger.info(f"正在调用 DeepSeek API ({self.model}) 格式化 {len(news_items)} 条新闻...")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"请将以下 {len(news_items)} 条新闻整理为每日早报：\n\n{news_text}"},
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            html = response.choices[0].message.content or ""
            # 去掉可能包裹的 markdown 代码块标记
            html = html.strip()
            if html.startswith("```html"):
                html = html[7:]
            if html.startswith("```"):
                html = html[3:]
            if html.endswith("```"):
                html = html[:-3]
            html = html.strip()

            token_used = response.usage.total_tokens if response.usage else 0
            print(f"✅ [DEBUG] DeepSeek API 调用成功，消耗 {token_used} tokens，HTML长度={len(html)}")
            logger.info(f"DeepSeek API 调用成功，消耗 {token_used} tokens")
            return html

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            logger.error(f"DeepSeek API 调用失败: {e}")
            logger.error(f"详细堆栈:\n{error_detail}")
            import sys
            print(f"\n{'='*60}")
            print(f"❌ [DEBUG] DeepSeek API 调用失败！进入降级逻辑...")
            print(f"   错误类型: {type(e).__name__}")
            print(f"   错误信息: {e}")
            print(f"   模型: {self.model}")
            print(f"   API Base: {self.client.base_url}")
            print(f"{'='*60}\n")
            # 降级：返回简单的纯文本格式
            return self._fallback_format(news_items, source_names)

    def _build_news_text(self, items: list) -> str:
        """构建发送给 DeepSeek 的原始新闻文本"""
        lines = []
        for i, item in enumerate(items, 1):
            time_str = ""
            if item.published:
                time_str = item.published.astimezone(CST).strftime("%m-%d %H:%M")
            lines.append(f"{i}. [{item.source}] {item.title}")
            if item.summary:
                lines.append(f"   摘要: {item.summary}")
            if time_str:
                lines.append(f"   时间: {time_str}")
            lines.append(f"   链接: {item.url}")
            lines.append("")
        return "\n".join(lines)

    def _empty_report(self, sources: list[str]) -> str:
        """没有新闻时的空报告"""
        return """<p style="color:#999;">今天没有抓取到新闻，可能是网络问题或 RSS 源暂时不可用。</p>
<p style="color:#999;font-size:12px;">来源：{"、".join(sources)}</p>"""

    def _fallback_format(self, items: list, sources: list[str]) -> str:
        """API 失败时的降级格式"""
        items_html = ""
        for item in items[:20]:
            items_html += f'<li><a href="{item.url}"><strong>{item.title}</strong></a>'
            if item.summary:
                items_html += f" — {item.summary[:80]}"
            items_html += f'<br><small>来源：{item.source}</small></li>\n'

        return f"""<p style="color:#e67e22;">⚠️ AI 格式化暂不可用，以下为原始新闻列表</p>
<ol>{items_html}</ol>
<hr>
<p style="color:#999;font-size:12px;">来源：{"、".join(sources)}</p>"""

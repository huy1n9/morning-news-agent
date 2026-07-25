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
SYSTEM_PROMPT = """你是一位资深新闻编辑，每天早上为读者制作一份高信息密度的"每日早报"。

你的任务是从原始新闻列表中精选最有价值的新闻，按重要性排序，用精炼语言呈现核心信息。

请严格按以下格式输出 HTML 邮件内容（邮件标题已包含日期，正文无需再写标题）：

<p style="color:#666;font-size:13px;">今日共精选 {count} 条重要新闻</p>

<h3>一、要闻速览（Top 5）</h3>
<ol>
  <li><strong>标题概括</strong> — 1-2句话概括事件核心与影响</li>
</ol>

<h3>二、国际</h3>
<ul>
  <li><strong>原标题</strong>：60-100字精炼摘要，包含事件背景、关键数据和影响<br><small>来源：XXX</small></li>
</ul>

<h3>三、科技</h3>
<ul>
  <li>...</li>
</ul>

<h3>四、财经</h3>
<ul>
  <li>...</li>
</ul>

<h3>五、其他值得关注</h3>
<ul>
  <li>...</li>
</ul>

<hr>
<p style="color:#999;font-size:12px;">本早报由 AI 自动生成，来源：{sources}<br>仅供参考，不构成任何建议。</p>

编辑要求：
1. 严格按重要性排序，头条必须是当日最有影响力的新闻
2. 每条新闻用 60-100 字做精炼摘要，保留具体数据、人名、影响范围等关键信息
3. 同一事件的多篇报道合并为一条，选用信息最完整的来源
4. 合并同类新闻，避免信息碎片化（如同一主题的多条新闻可合并为一个条目）
5. 优先报道对中文读者有直接影响的新闻
6. 每类 5-10 条，某类无合适新闻可省略该版块
7. 只输出 HTML 片段（从计数行到末尾），不要 ```html``` 标记
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

        print(f"\n[DEBUG] 准备调用 DeepSeek API")
        print(f"   model     = {self.model}")
        print(f"   base_url  = {self.client.base_url}")
        print(f"   api_key   = {self.client.api_key[:8]}***{self.client.api_key[-4:] if len(self.client.api_key) > 4 else '????'}")
        print(f"   news_count= {len(news_items)}")
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
            print(f"[成功] DeepSeek API 调用完成，消耗 {token_used} tokens，HTML长度={len(html)}")
            logger.info(f"DeepSeek API 调用成功，消耗 {token_used} tokens")
            return html

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            logger.error(f"DeepSeek API 调用失败: {e}")
            logger.error(f"详细堆栈:\n{error_detail}")
            import sys
            print(f"\n{'='*60}")
            print(f"[错误] DeepSeek API 调用失败，进入降级逻辑...")
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

        return f"""<p style="color:#e67e22;">[注意] AI 格式化暂不可用，以下为原始新闻列表</p>
<ol>{items_html}</ol>
<hr>
<p style="color:#999;font-size:12px;">来源：{"、".join(sources)}</p>"""

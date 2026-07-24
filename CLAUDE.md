# 每日早报 AI Agent — CLAUDE.md

## 项目概述

基于 DeepSeek API 的 AI 新闻早报系统。每天早上 7:00 自动从多个 RSS 源抓取前一日中文新闻，调用 DeepSeek API 进行智能分类和摘要，然后以精美的 HTML 邮件发送到指定邮箱。

## 技术栈

- **语言**: Python 3.10+
- **AI 服务**: DeepSeek API (OpenAI 兼容接口, `deepseek-chat` 模型)
- **新闻获取**: RSS (feedparser) + requests + BeautifulSoup
- **邮件发送**: 163 SMTP (smtplib + email.mime)
- **调度**: Linux cron (系统级)
- **配置**: .env (敏感信息) + config.yaml (业务配置)

## 项目结构

```
morning-news-agent/
├── main.py                # 主入口，编排整个流程
├── config.yaml            # 业务配置（新闻源、模型参数、邮件模板）
├── .env                   # 敏感信息（API Key、邮箱授权码）⚠️ 不提交 git
├── .env.example           # .env 模板
├── requirements.txt       # Python 依赖
├── install.sh             # 一键安装脚本
├── CLAUDE.md              # 本文件
├── README.md              # 使用说明
├── logs/                  # 日志目录
│   └── morning-news.log
└── src/
    ├── __init__.py
    ├── news_fetcher.py    # RSS 新闻抓取 + 去重 + 日期过滤
    ├── ai_formatter.py    # DeepSeek API → 结构化 HTML 早报
    └── email_sender.py    # 163 SMTP HTML 邮件发送
```

## 核心流程

```
cron (7:00 AM)
    │
    ▼
main.py
    │
    ├─[1] news_fetcher.py
    │     ├─ 遍历 config.yaml 中的 RSS 源
    │     ├─ feedparser 解析 → NewsItem 列表
    │     ├─ 过滤非昨日新闻
    │     └─ 标题相似度去重
    │
    ├─[2] ai_formatter.py
    │     ├─ 构建 system prompt（编辑角色 + 格式规范）
    │     ├─ 调用 DeepSeek API (openai SDK)
    │     └─ 返回 HTML 邮件正文
    │
    └─[3] email_sender.py
          ├─ 构建 MIMEMultipart (HTML + plain text)
          ├─ 163 SMTP SSL 认证
          └─ 发送 → 目标邮箱
```

## 常用命令

```bash
# 安装依赖
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 配置环境（先编辑 .env）
cp .env.example .env
vim .env

# 手动运行一次（测试用）
python main.py

# 安装 cron 定时任务（每天早上 7:00）
./install_cron.sh

# 查看日志
tail -f logs/morning-news.log
```

## 关键技术决策

### 为什么用 RSS 而不是 News API？
- RSS 免费、无配额限制
- 多源聚合可覆盖中英文主流媒体
- 不依赖第三方 API Key

### 为什么用 DeepSeek 而不是直接拼接？
- AI 可以自动分类（要闻/国际/科技/财经）
- 能做智能摘要（原文 → 20-40字精炼）
- 同一事件自动去重合并

### 为什么 HTML 邮件？
- 视觉效果好，阅读体验佳
- 支持链接点击跳转原文
- 同时发送纯文本备选（兼容老邮件客户端）

## 163 邮箱 SMTP 配置

1. 登录 mail.163.com
2. 设置 → POP3/SMTP/IMAP
3. 开启 SMTP 服务
4. 获取"授权码"（这就是 .env 中的 EMAIL_PASSWORD，不是登录密码！）

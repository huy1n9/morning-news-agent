# 📰 每日早报 AI Agent

基于 **DeepSeek API** 的 AI 新闻早报系统 —— 每天早上 7:00 从多个 RSS 源抓取中文新闻，由 AI 智能分类整理，以精美 HTML 邮件发送到你的邮箱。

## ✨ 功能

- 📡 **多源聚合**：IT之家、36氪、少数派、开源中国、InfoQ 等科技/财经媒体
- 🤖 **AI 整理**：DeepSeek 自动分类（要闻、国际、科技、财经），精炼 20-40 字摘要
- 📧 **邮件投递**：HTML 精美排版，支持跳转原文，自动降级纯文本
- 🕖 **定时发送**：Linux cron 每天早上 7:00 自动运行
- 🌐 **代理支持**：设置 HTTPS_PROXY 后可接入 Google News、BBC 等国际源

## 🚀 快速开始

### 1. 安装依赖

```bash
cd ~/morning-news-agent
pip3 install --user -r requirements.txt
```

### 2. 配置

```bash
# 编辑 .env，填入你的 API Key 和邮箱
vim .env
```

必需填写：
```ini
DEEPSEEK_API_KEY=sk-xxxxxxxx    # DeepSeek API Key
EMAIL_FROM=you@163.com          # 发件邮箱
EMAIL_TO=you@163.com            # 收件邮箱
EMAIL_PASSWORD=授权码            # 163 SMTP 授权码（非登录密码！）
```

> 📌 **163 邮箱授权码获取**：登录 mail.163.com → 设置 → POP3/SMTP/IMAP → 开启 SMTP → 获取授权码

### 3. 测试运行

```bash
# 测试新闻抓取
python3 main.py --fetch-only

# 测试完整流程（抓取 + AI 格式化，不发邮件）
python3 main.py --test

# 手动运行（实际发送邮件）
python3 main.py
```

### 4. 设置定时任务

```bash
# 安装 cron（每天早上 7:00 运行）
./install_cron.sh

# 查看定时任务
crontab -l

# 移除定时任务
./install_cron.sh --remove
```

## 📂 项目结构

```
morning-news-agent/
├── main.py              # 主入口（支持 --test / --fetch-only）
├── config.yaml          # 新闻源 + 模型参数
├── .env                 # API Key + 邮箱配置（敏感）
├── requirements.txt     # 依赖
├── install_cron.sh      # 定时任务安装
├── CLAUDE.md            # AI 编程助手文档
├── README.md            # 本文件
├── logs/                # 运行日志
└── src/
    ├── news_fetcher.py  # RSS 抓取 + 去重
    ├── ai_formatter.py  # DeepSeek 格式化
    └── email_sender.py  # 邮件发送
```

## 🔧 命令行参数

| 参数 | 说明 |
|------|------|
| `--fetch-only` | 仅抓取新闻，输出到控制台 |
| `--test` | 测试模式：抓取 + 格式化，不发邮件 |
| `--output FILE` | 将 HTML 邮件保存到文件（配合 `--test`） |

## 🌐 启用国际新闻源

编辑 `.env`，设置代理：

```ini
HTTPS_PROXY=http://127.0.0.1:7890   # 你的代理地址
```

之后 `config.yaml` 中的国际源（Google News、BBC等）会自动启用。

## 📊 邮件效果

邮件包含以下版块：
- 🔥 **要闻速览** (Top 5)
- 🌍 **国际**
- 💻 **科技**
- 💰 **财经**
- 🗞️ **其他值得关注**

## 🛠️ 技术栈

- Python 3.10+
- DeepSeek API (OpenAI 兼容)
- feedparser (RSS)
- smtplib + email.mime (邮件)
- Linux cron (调度)

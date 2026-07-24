#!/bin/bash
# 每日早报 AI Agent — 一键安装脚本

set -e

echo "==========================================="
echo "  📰 每日早报 AI Agent 安装"
echo "==========================================="
echo ""

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# 1. 检查 Python
echo "→ 检查 Python 环境..."
python3 --version || { echo "❌ 请先安装 Python 3.10+"; exit 1; }

# 2. 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "→ 创建 Python 虚拟环境..."
    python3 -m venv venv
else
    echo "→ 虚拟环境已存在，跳过"
fi

# 3. 激活并安装依赖
echo "→ 安装 Python 依赖..."
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

# 4. 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "→ 创建 .env 配置文件..."
    cp .env.example .env
    echo ""
    echo "⚠️  请编辑 .env 文件，填入你的 API Key 和邮箱信息："
    echo "   vim .env"
    echo ""
    echo "   需要填写："
    echo "   - DEEPSEEK_API_KEY:    你的 DeepSeek API Key"
    echo "   - EMAIL_FROM:          发件邮箱（如 yourname@163.com）"
    echo "   - EMAIL_TO:            收件邮箱"
    echo "   - EMAIL_PASSWORD:      SMTP 授权码（非登录密码！）"
else
    echo "→ .env 文件已存在，跳过"
fi

echo ""
echo "==========================================="
echo "  ✅ 安装完成！"
echo "==========================================="
echo ""
echo "下一步："
echo "  1. vim .env                  # 填写配置"
echo "  2. source venv/bin/activate  # 激活环境"
echo "  3. python main.py            # 测试运行"
echo "  4. ./install_cron.sh         # 设置定时任务"
echo ""

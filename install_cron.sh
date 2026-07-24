#!/bin/bash
# 安装 cron 定时任务 — 每天早上 7:00 运行每日早报 Agent
#
# 使用方式:
#   ./install_cron.sh          # 安装 cron
#   ./install_cron.sh --remove # 移除 cron

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 自动检测 Python 路径：优先 venv，其次系统 python3
if [ -f "$PROJECT_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_DIR/venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "❌ 未找到 Python3，请先安装"
    exit 1
fi

MAIN_SCRIPT="$PROJECT_DIR/main.py"
CRON_MARKER="# morning-news-agent"

if [ "$1" = "--remove" ]; then
    echo "→ 移除定时任务..."
    crontab -l 2>/dev/null | grep -v "$CRON_MARKER" | crontab -
    echo "✅ 定时任务已移除"
    exit 0
fi

# 检查 .env
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "⚠️  .env 文件不存在，请先配置: cp .env.example .env && vim .env"
fi

# 构建 cron 表达式：每天 7:00
CRON_JOB="0 7 * * * cd $PROJECT_DIR && $PYTHON_BIN $MAIN_SCRIPT >> $PROJECT_DIR/logs/cron.log 2>&1 $CRON_MARKER"

echo "==========================================="
echo "  📰 每日早报 cron 定时任务安装"
echo "==========================================="
echo ""
echo "  Python:   $PYTHON_BIN"
echo "  脚本:     $MAIN_SCRIPT"
echo "  时间:     每天 7:00 AM"
echo ""

# 检查是否已存在
if crontab -l 2>/dev/null | grep -q "$CRON_MARKER"; then
    echo "  ⚠️  已有旧定时任务，正在替换..."
fi

# 写入 crontab
(crontab -l 2>/dev/null | grep -v "$CRON_MARKER"; echo "$CRON_JOB") | crontab -

echo "✅ 定时任务已安装！"
echo ""
echo "查看现有定时任务:"
echo "  crontab -l"
echo ""
echo "查看日志:"
echo "  tail -f $PROJECT_DIR/logs/morning-news.log"
echo ""
echo "移除定时任务:"
echo "  ./install_cron.sh --remove"

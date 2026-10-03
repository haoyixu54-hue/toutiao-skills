#!/bin/bash
# 今日头条写作 Skill 安装脚本 (macOS/Linux)
set -e

SKILL_DIR="$HOME/.claude/skills/writing"
REPO_URL="https://github.com/haoyixu54-hue/toutiao-writing-skill.git"

echo "正在安装今日头条写作 Skill..."

if [ -d "$SKILL_DIR" ]; then
    echo "已存在，正在更新..."
    cd "$SKILL_DIR" && git pull
else
    git clone "$REPO_URL" "$SKILL_DIR"
fi

pip install -r "$SKILL_DIR/requirements.txt"

mkdir -p "$HOME/Desktop/今日头条"

echo "安装完成！重启 Claude Code 后输入 /writing 即可使用。"

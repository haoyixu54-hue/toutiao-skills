# 今日头条写作 Skill 安装脚本 (Windows PowerShell)
$ErrorActionPreference = "Stop"

$SkillDir = "$env:USERPROFILE\.claude\skills\writing"
$RepoUrl = "https://github.com/haoyixu54-hue/toutiao-writing-skill.git"

Write-Host "正在安装今日头条写作 Skill..."

if (Test-Path $SkillDir) {
    Write-Host "已存在，正在更新..."
    cd $SkillDir
    git pull
} else {
    git clone $RepoUrl $SkillDir
}

pip install -r "$SkillDir\requirements.txt"

$Desktop = [Environment]::GetFolderPath("Desktop")
New-Item -ItemType Directory -Force -Path "$Desktop\今日头条" | Out-Null

Write-Host "安装完成！重启 Claude Code 后输入 /writing 即可使用。"

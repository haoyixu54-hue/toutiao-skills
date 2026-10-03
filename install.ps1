# ============================================================
# 批量安装两个 Claude Code Skill 到 ~/.claude/skills/
#   writing           -> ~/.claude/skills/writing
#   content-analytics -> ~/.claude/skills/content-analytics
# ============================================================
$ErrorActionPreference = "Stop"

$skillsDir = Join-Path $env:USERPROFILE ".claude\skills"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

foreach ($name in @("writing", "content-analytics")) {
    $src = Join-Path $root $name
    $dst = Join-Path $skillsDir $name

    if (-not (Test-Path $src)) {
        Write-Host "[跳过] 源目录不存在：$src" -ForegroundColor Yellow
        continue
    }
    if (Test-Path $dst) {
        Write-Host "[跳过] 已存在，不覆盖：$dst（如需重装请先手动删除）" -ForegroundColor Yellow
        continue
    }
    Copy-Item -Path $src -Destination $dst -Recurse
    Write-Host "[完成] $name -> $dst" -ForegroundColor Green
}

Write-Host ""
Write-Host "全部完成。现在可以在 Claude Code 里说："
Write-Host "  写作：/writing <事件或关键词>"
Write-Host "  采集：采集最新数据"
Write-Host "  复盘：复盘最近的数据 / 完整复盘"

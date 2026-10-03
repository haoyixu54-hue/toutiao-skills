# Toutiao Content Skills（今日头条内容生产 + 数据分析）

两个 Claude Code Skill，覆盖「内容生产 → 数据采集 → 数据分析 → 复盘 → 策略沉淀」的完整闭环。

## 目录结构

```
toutiao-skills/
├── writing/              # ① 写作 Skill（选题/标题/正文/Writing QA）
│   ├── SKILL.md
│   ├── references/       # 规则与提示词（含 qa-rubric.md、future-strategy.md）
│   ├── scripts/          # 抓取/配图/查重脚本
│   └── tests/            # Writing QA 测试稿
├── content-analytics/    # ② 数据分析 Skill（采集/分析/复盘/策略）
│   ├── SKILL.md
│   └── code/             # 采集与分析代码（run_agent.py 统一入口 + analysis/）
│       └── strategy/     # 策略库（hypotheses/experiments/validated_rules/avoid_patterns）
├── install.ps1           # 批量安装两个 skill
└── .gitignore
```

## 安装（批量）

在 Windows 上，右键「以管理员身份打开 PowerShell」进入本仓库目录，运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

或直接双击 `install.ps1`（若被策略拦截，用上面的命令）。脚本会把两个 skill 复制到 `~/.claude/skills/`。

## 使用

装好后，在 Claude Code 里直接说：

| 想做什么 | 口令 |
|---|---|
| 写一篇娱乐八卦文章 | `/writing 要写的事件或关键词`，或「写一篇 XXX 的娱乐文章」 |
| 采集最新数据 | 「采集最新数据」 |
| 复盘最近的数据 | 「复盘最近的数据」或「复盘最近50篇」 |
| 完整复盘 | 「完整复盘」 |

## 环境要求

- Python 3.12 + `playwright` + `openpyxl`（`pip install -r` 对应 requirements.txt）
- Windows 自带 Chrome（采集器用 `channel=chrome`，无需额外装 Chromium）
- 采集需手动登录今日头条创作者后台（程序不自动输入账号密码、不碰验证码）

## 数据目录

Content Analytics 默认把数据写到 `content-analytics/code/data/`。
若要指定其它目录（例如本机已有的 `E:/toutiao_data`），设置环境变量：

```powershell
setx TOUTIAO_DATA_DIR "E:/toutiao_data"
```

## 说明

- 两个 skill 职责分离：writing 负责**生产**，content-analytics 负责**评价生产结果**。
- content-analytics 的 `strategy/validated_rules.md` 只接受经真实数据验证的规则，AI 不能凭一次复盘就把猜测写成规则。

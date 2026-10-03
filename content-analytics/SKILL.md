---
name: content-analytics
description: >
  当用户要求「采集最新数据」「复盘最近的数据/最近50篇」「完整复盘」「分析头条作品数据」
  「看下最近表现」等时使用。负责今日头条作品数据的数据采集、数据质量检查、统计分析、
  四象限分析、标题表现分析、AI 复盘与策略沉淀（hypotheses/experiments/validated_rules/avoid_patterns）。
  与 writing skill 职责分离：writing 负责生产，content-analytics 负责评价生产结果。
argument-hint: "[采集最新数据 | 复盘最近的数据 | 完整复盘]"
---

# Content Analytics（内容数据分析）

本 Skill 是独立的**数据复盘**入口，与 Writing Skill 平级、职责分离：

- **Writing Skill**：负责生产内容（选题/标题/正文/QA）。
- **Content Analytics**：负责评价生产结果（采集→清洗→统计→四象限→标题分析→AI 复盘→策略沉淀）。

**本 Skill 不修改 Writing Skill、不修改 Writing QA、不自动把 AI 推测变成 validated_rules。**

---

## 代码位置与运行约定（先读）

- 本 skill 的代码在 `code/` 子目录（即 `~/.claude/skills/content-analytics/code/`），运行前先进入该目录。
- 用 `python` 运行（若 Windows 上裸 `python` 是「应用商店别名」导致静默失败，改用完整 Python 路径，例如 `C:\...\Python312\python.exe`）。
- 数据目录默认是 `code/data/`；若要指定其它目录，设环境变量 `TOUTIAO_DATA_DIR`（详见 `code/paths.py`）。
- 采集需要**手动登录**：程序会弹出 Chrome 窗口，由用户扫码/验证码登录；程序**绝不**自动输入账号密码、**绝不**碰验证码。

---

## 三种任务（自然语言 → 命令）

### 任务 1：「采集最新数据」

```
cd code
python run_agent.py collect
```

实际发生的事情：
1. 调用采集器 `run_batch.py`（复用，不重写），输出到统一数据目录（默认 `code/data/`）
2. 自动翻页 + 去重续传（已采过的 article_id 自动跳过）
3. 采集后做数据质量检查，打印**采集摘要**：文章总数 / 成功 / 部分成功 / 失败 / 重复 article_id / 关键字段缺失

### 任务 2：「复盘最近的数据」（含「复盘最近50篇」）

```
cd code
python run_agent.py review
```

实际发生的事情：
1. 读取统一数据目录里的 `batch_result.xlsx`（若文件不存在，明确报错并提示先采集，**不假装正常分析**）
2. 数据质检 → 基础统计 → 表现分层 → 对比组 → 标题分析 → 高级分析（样本门槛 + 四象限）
3. 生成 `content_review.md`（13 章节主报告，纯动态，无历史硬编码）
4. 生成 `ai_prompt.md`（AI 复盘提示词，**不调用任何 API**）
5. 中间 JSON 落盘到 `analysis/`
6. 确保 `strategy/` 的 4 个骨架文件存在

### 任务 3：「完整复盘」

```
cd code
python run_agent.py full
```

实际发生的事情：先执行「采集最新数据」，再执行「复盘最近的数据」。

---

## 复盘之后：Claude Code 就是复盘 AI（重要）

`run_agent.py review` 只负责算数字、出报告、出提示词，**不调用 Anthropic / DeepSeek API**。

复盘 AI = **当前 Claude Code 会话（也就是你）**。生成 `ai_prompt.md` 后，请按下面步骤完成策略沉淀：

1. 读取 `ai_prompt.md` 和 `content_review.md`
2. 从数据中提炼**假设**，写入 `strategy/hypotheses.md`（编号 H01/H02…，每条写：依据 + 证据强度(低/中/高) + 需要什么实验验证）
3. 为值得验证的假设设计**实验**，写入 `strategy/experiments.md`（编号 E01…，写：目的/对照组/实验组/指标/样本量/成功标准）
4. 把已确认需谨慎的写法写入 `avoid_patterns.md`

**严格红线（必须遵守）：**

- `validated_rules.md` **只允许**写入经过真实数据/多次实验/足够样本验证的规则。
- **绝对禁止**仅凭一次复盘就把 AI 推测写进 `validated_rules.md`。
- 相关关系 ≠ 因果关系：不要写「标题带数字导致 CTR 提高」，只能写「该特征与较高 CTR 同时出现，值得实验验证」。
- 不要自动修改 Writing Skill / SKILL.md / Writing QA 的任何文件。

---

## 数据质量红线

正式分析前至少检查：数据文件是否存在、是否为空、article_id 是否重复、核心字段是否缺失、reads/impressions 是否存在、是否有异常值。

若发现明显问题，**不要生成"看起来正常"的分析报告**，应在报告里明确给出数据质量警告（`content_review.md` 第 2、10 节已自动承载）。

---

## 样本分层（务必遵守）

| 分层 | 门槛 | 用途 |
|---|---|---|
| 主分析 | reads >= 30 | 进入主要四象限结论 |
| 辅助观察 | 10 <= reads < 30 | 仅辅助证据，不作强结论 |
| 观察数据 | reads < 10 | 保留原始数据，不进主要结论 |

**不能因为某篇 reads=1 却出现 100% 完成率，就把它判为高完成率优质文章。**

---

## 数据闭环（未来）

```
采集 → 分析 → AI 复盘 → hypotheses/experiments → 实验验证 → validated_rules →（未来）Writing Skill 读取
```

当前阶段：产出到 `strategy/` 即止，**不自动回写 Writing Skill**。

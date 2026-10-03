# -*- coding: utf-8 -*-
"""
================================================================================
Content Analytics Agent —— 统一入口（V0.5）

子命令：
  collect   只采集：调用现有采集器 -> 数据质量检查 -> 输出采集摘要
  review    只复盘：读取统一数据目录的 batch_result.xlsx -> 清洗/统计/四象限/标题
            -> 生成 content_review.md + ai_prompt.md + 中间 JSON
  full      完整复盘：先 collect，再 review

设计原则：
  - 复用现有 collector / analysis，不改底层统计逻辑
  - 不额外调用 Anthropic / DeepSeek API；AI 复盘由「当前 Claude Code 会话」完成：
    review 生成 ai_prompt.md 后，由 Claude 读取并写入 strategy/*.md
  - 统一数据目录见 paths.py（采集输出 = 分析输入 = E:/toutiao_data）

运行方式（在 toutiao_tool 目录下，用完整 Python 路径）：
    python run_agent.py collect
    python run_agent.py review
    python run_agent.py full
================================================================================
"""

import os
import sys
import json
import argparse
import subprocess

# 控制台 UTF-8，避免中文乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import paths
from analysis.data_quality import check_quality, render_quality_report
from analysis.metrics import compute_metrics, interaction_rate, impression_efficiency
from analysis.tiering import tier_articles
from analysis.compare import extract_groups
from analysis.title_features import extract_all, summarize
from analysis.advanced import (
    qualified_top, high_impression_low_click, four_quadrant,
    qualified_high_click_low_completion,
)
from analysis.ai_review import build_prompt
from analysis.content_review import generate_content_review, split_pools
from analysis.utils import load_records

# 核心字段（采集摘要里要单独统计缺失）
CORE_FIELDS = ["article_id", "title", "publish_time", "impressions", "reads"]

# strategy 文件骨架（首次运行时生成，之后只追加不覆盖）
STRATEGY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strategy")
STRATEGY_TEMPLATES = {
    "hypotheses.md": """# Hypotheses（待验证假设）

> 这里是 AI 根据数据提出的**尚未验证**的规律。
> 只能作为「猜测」，**不能当作规则**，更不能直接写进 validated_rules.md。

## 规则
- 每条假设必须有编号（H01 / H02 / ...）
- 必须写明：依据（哪些数据支持）+ 证据强度（低/中/高）+ 需要什么实验验证
- 相关关系 ≠ 因果关系

---

（暂无假设）
""",
    "experiments.md": """# Experiments（实验记录）

> 针对 hypothesis 设计的实验。记录目的 / 样本 / 对照组 / 实验组 / 指标 / 结果 / 结论。

## 模板
- 实验编号：E01
- 实验目的：
- A组（对照组）：
- B组（实验组）：
- 主要指标：CTR / 阅读完成率 / 阅读时长 等
- 样本量要求：
- 结果：
- 结论：

---

（暂无实验）
""",
    "validated_rules.md": """# Validated Rules（已验证规则）

> ⚠️ 只有经过**真实数据 / 多次实验 / 足够样本**验证后，才能写入这里。
> **绝对禁止** AI 仅凭少量数据或一次复盘就把猜测写成规则。

---

（暂无已验证规则）
""",
    "avoid_patterns.md": """# Avoid Patterns（需谨慎 / 避免的模式）

> 记录经过数据支持、应当谨慎使用或避免的写法。
> 同样**不能仅凭一次 AI 主观判断**就升级为长期规则。

---

（暂无）
""",
}


def _ensure_strategy_files():
    """确保 strategy/ 目录与 4 个骨架文件存在（只创建，不覆盖已有内容）。"""
    os.makedirs(STRATEGY_DIR, exist_ok=True)
    for name, content in STRATEGY_TEMPLATES.items():
        path = os.path.join(STRATEGY_DIR, name)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)


def _save(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def _save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)
    return path


# ======================================================================
# collect：只采集
# ======================================================================

def collect(data_dir):
    """调用现有 run_batch.py 采集，然后做数据质量检查并输出采集摘要。"""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_batch.py")
    cmd = [sys.executable, script, "--output-dir", data_dir]
    print("=" * 60)
    print("Content Analytics：采集最新数据")
    print(f"统一数据目录：{data_dir}")
    print("运行采集器：", " ".join(cmd))
    print("=" * 60)
    subprocess.run(cmd, check=False)  # 采集器内部已处理登录/单篇失败，不因单篇失败中断

    # 采集后读取结果，输出摘要
    batch_json = os.path.join(data_dir, "batch_result.json")
    if not os.path.exists(batch_json):
        print("\n⚠️ 未找到采集结果文件，可能本次未采集到新数据。")
        return

    records = load_records(batch_json)
    quality = check_quality(records)
    status_count = {}
    for r in records:
        st = r.get("collection_status") or "unknown"
        status_count[st] = status_count.get(st, 0) + 1

    # 关键字段缺失（核心字段里至少一项为 None 的文章数）
    core_missing = sum(
        1 for r in records
        if any(r.get(f) is None for f in CORE_FIELDS)
    )

    print("\n" + "=" * 60)
    print("采集摘要")
    print("=" * 60)
    print(f"文章总数（累计）：{len(records)}")
    print(f"成功：{status_count.get('success', 0)}")
    print(f"部分成功：{status_count.get('partial', 0)}")
    print(f"失败：{status_count.get('failed', 0)}")
    print(f"重复 article_id：{len(quality.get('duplicate_ids', {}))}")
    print(f"关键字段缺失：{core_missing} 篇")
    print(f"输出文件：{os.path.join(data_dir, 'batch_result.xlsx')}")
    print("=" * 60)


# ======================================================================
# review：只复盘
# ======================================================================

def review(data_dir):
    """读取 batch_result.xlsx，跑完整分析，生成 content_review.md + ai_prompt.md + 中间 JSON。"""
    data_file = os.path.join(data_dir, "batch_result.xlsx")
    out_dir = os.path.join(data_dir, "analysis")

    print("=" * 60)
    print("Content Analytics：复盘最近的数据")
    print(f"数据文件：{data_file}")
    print(f"输出目录：{out_dir}")
    print("=" * 60)

    # ---- 数据质量闸门：文件存在 / 空 ----
    if not os.path.exists(data_file):
        print(f"❌ 数据文件不存在：{data_file}")
        print("   请先运行「采集最新数据」（run_agent.py collect），或把数据放到该路径。")
        return
    records = load_records(data_file)
    if not records:
        print(f"❌ 数据为空：{data_file}")
        return
    print(f"读取到 {len(records)} 条记录。")

    _ensure_strategy_files()

    # ---- 1. 数据质检 ----
    quality = check_quality(records)
    qr_path = _save(os.path.join(out_dir, "data_quality_report.md"),
                    render_quality_report(records, quality))
    print(f"[1/7] 数据质检 -> {qr_path}（结论：{quality['status']}）")

    # ---- 2. 基础指标 ----
    metrics = compute_metrics(records)
    m_path = _save_json(os.path.join(out_dir, "metrics.json"), metrics)
    print(f"[2/7] 基础指标 -> {m_path}")

    # ---- 3. 表现分层 + 衍生字段 ----
    tiered, tier_info = tier_articles(records)
    for r in tiered:
        r["interaction_rate"] = interaction_rate(r)
        r["impression_efficiency"] = impression_efficiency(r)
    t_path = _save_json(os.path.join(out_dir, "tiering.json"), {
        "info": tier_info, "records": tiered,
    })
    print(f"[3/7] 表现分层 -> {t_path}")

    # ---- 4. 对比组 ----
    groups, k = extract_groups(records)
    _save_json(os.path.join(out_dir, "comparison.json"), groups)
    print(f"[4/7] 对比组（Top/Bottom 10%，每组 {k} 篇）")

    # ---- 5. 标题分析 ----
    feat_recs, _ = extract_all(records)
    title_summary = summarize(records)
    _save_json(os.path.join(out_dir, "title_features.json"), feat_recs)
    _save_json(os.path.join(out_dir, "title_summary.json"), title_summary)
    print(f"[5/7] 标题分析（特征 {len(feat_recs)} 篇）")

    # ---- 5.6 高级分析（样本门槛 / 高展现低点击 / 四象限）----
    pools = split_pools(records)
    advanced = {}
    qc_rows, qc_th = qualified_top(tiered, lambda r: r.get("completion_rate"))
    advanced["qualified_completion"] = (qc_rows, qc_th)
    qi_rows, qi_th = qualified_top(tiered, lambda r: r.get("interaction_rate"))
    advanced["qualified_interaction"] = (qi_rows, qi_th)
    advanced["high_impression_low_click"] = high_impression_low_click(tiered)
    hclc_rows, hclc_th = qualified_high_click_low_completion(tiered)
    advanced["high_click_low_completion"] = (hclc_rows, hclc_th)
    # 四象限：主分析（reads>=30）+ 辅助观察（10<=reads<30）分别算
    advanced["quadrant_main"] = four_quadrant(pools["main"])
    advanced["quadrant_aux"] = four_quadrant(pools["aux"])
    _save_json(os.path.join(out_dir, "advanced.json"), {
        "qualified_completion": {"threshold": qc_th, "records": qc_rows},
        "qualified_interaction": {"threshold": qi_th, "records": qi_rows},
        "high_impression_low_click": advanced["high_impression_low_click"],
        "high_click_low_completion": {"threshold": hclc_th, "records": hclc_rows},
        "quadrant_main": advanced["quadrant_main"],
        "quadrant_aux": advanced["quadrant_aux"],
    })
    print(f"[5.6/7] 高级分析（完成率门槛={qc_th}，互动率门槛={qi_th}；四象限主分析 {len(pools['main'])} 篇 / 辅助 {len(pools['aux'])} 篇）")

    # ---- 6. AI 复盘提示词（不调 API，交给 Claude Code 会话）----
    prompt = build_prompt(metrics, quality, groups, title_summary, records)
    prompt_path = _save(os.path.join(data_dir, "ai_prompt.md"), prompt)
    print(f"[6/7] AI 复盘提示词 -> {prompt_path}（由 Claude Code 会话读取后写 strategy/*.md）")

    # ---- 7. 主复盘报告 ----
    review_md = generate_content_review(records, quality, metrics, pools, groups, title_summary, advanced)
    review_path = _save(os.path.join(data_dir, "content_review.md"), review_md)
    print(f"[7/7] 复盘报告 -> {review_path}")

    print("=" * 60)
    print("完成。输出文件：")
    print(f"  {review_path}")
    print(f"  {prompt_path}")
    print(f"  {os.path.join(out_dir, 'data_quality_report.md')}")
    print(f"  {os.path.join(out_dir, 'metrics.json / tiering.json / title_features.json / title_summary.json / advanced.json')}")
    print(f"  {STRATEGY_DIR}\\hypotheses.md / experiments.md / validated_rules.md / avoid_patterns.md")
    print("=" * 60)
    print("下一步：让 Claude Code 会话读取 ai_prompt.md，把 hypotheses / experiments 写入 strategy/*.md。")


# ======================================================================
# 入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(description="Content Analytics Agent（采集 / 复盘 / 完整复盘）")
    parser.add_argument("task", choices=["collect", "review", "full"],
                        help="collect=只采集；review=只复盘；full=完整复盘（先采集后复盘）")
    parser.add_argument("--data-dir", type=str, default=paths.DATA_DIR,
                        help=f"统一数据目录（默认 {paths.DATA_DIR}）")
    args = parser.parse_args()

    data_dir = args.data_dir

    if args.task == "collect":
        collect(data_dir)
    elif args.task == "review":
        review(data_dir)
    elif args.task == "full":
        collect(data_dir)
        review(data_dir)


if __name__ == "__main__":
    main()

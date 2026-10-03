# -*- coding: utf-8 -*-
"""
================================================================================
V0.3 入口 —— AI 内容数据复盘

读取采集结果（默认 E:/toutiao_data/batch_result.xlsx），依次执行：
  1. 数据质检        -> data_quality_report.md
  2. 基础指标        -> metrics.json
  3. 表现分层        -> tiering.json
  4. 对比数据        -> comparison.md / comparison.json
  5. 标题分析        -> title_features.json / title_summary.json
  6. AI 复盘提示词   -> ai_prompt.md（可选：有 ANTHROPIC_API_KEY 时直接调用 AI）
  7. 复盘报告        -> 复盘报告.md

运行方式（在 toutiao_tool 目录下）：
    python run_analysis.py                       # 用默认数据路径
    python run_analysis.py --data E:/toutiao_data/batch_result.xlsx
    python run_analysis.py --out E:/toutiao_data/analysis
================================================================================
"""

import os
import sys
import json
import argparse

# 控制台 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from analysis.data_quality import check_quality, render_quality_report
from analysis.metrics import compute_metrics, interaction_rate, impression_efficiency
from analysis.tiering import tier_articles
from analysis.compare import extract_groups, render_groups
from analysis.title_features import extract_all, summarize, render_summary
from analysis.ai_review import build_prompt, call_ai
from analysis.report import generate_report
from analysis.advanced import (
    qualified_top, high_impression_low_click, four_quadrant,
    qualified_high_click_low_completion,
)
from analysis.utils import load_records

import paths

DEFAULT_DATA = paths.DATA_DIR + "/batch_result.xlsx"
DEFAULT_OUT = paths.ANALYSIS_DIR


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


def main():
    parser = argparse.ArgumentParser(description="AI 内容数据复盘（V0.3）")
    parser.add_argument("--data", type=str, default=DEFAULT_DATA, help="采集结果文件路径（.xlsx/.json/.csv）")
    parser.add_argument("--out", type=str, default=DEFAULT_OUT, help="分析结果输出目录")
    args = parser.parse_args()

    print("=" * 60)
    print("V0.3 AI 内容数据复盘 开始")
    print(f"数据文件：{args.data}")
    print(f"输出目录：{args.out}")
    print("=" * 60)

    # ---- 读取 ----
    records = load_records(args.data)
    print(f"读取到 {len(records)} 条记录。")
    if not records:
        print("没有数据，退出。")
        return

    # ---- 1. 数据质检 ----
    quality = check_quality(records)
    qr_path = _save(os.path.join(args.out, "data_quality_report.md"),
                    render_quality_report(records, quality))
    print(f"[1/7] 数据质检完成 -> {qr_path}（结论：{quality['status']}）")

    # ---- 2. 基础指标 ----
    metrics = compute_metrics(records)
    m_path = _save_json(os.path.join(args.out, "metrics.json"), metrics)
    print(f"[2/7] 基础指标完成 -> {m_path}")

    # ---- 3. 表现分层 ----
    tiered, tier_info = tier_articles(records)
    t_path = _save_json(os.path.join(args.out, "tiering.json"), {
        "info": tier_info,
        "records": tiered,
    })
    print(f"[3/7] 表现分层完成 -> {t_path}")

    # ---- 4. 对比数据 ----
    groups, k = extract_groups(records)
    cmp_path = _save(os.path.join(args.out, "comparison.md"),
                     f"# 对比数据（Top/Bottom 10%，每组 {k} 篇）\n" + render_groups(groups))
    _save_json(os.path.join(args.out, "comparison.json"), groups)
    print(f"[4/7] 对比数据完成 -> {cmp_path}")

    # ---- 5. 标题分析 ----
    feat_recs, _ = extract_all(records)
    ts = summarize(records)
    _save_json(os.path.join(args.out, "title_features.json"), feat_recs)
    _save_json(os.path.join(args.out, "title_summary.json"), ts)
    print(f"[5/7] 标题分析完成 -> 特征 {len(feat_recs)} 篇")

    # ---- 5.5 为每篇补充衍生字段（互动率 / 转化效率）----
    for r in tiered:
        r["interaction_rate"] = interaction_rate(r)
        r["impression_efficiency"] = impression_efficiency(r)

    # ---- 5.6 高级分析（V0.3.1：样本门槛 / 高展现低点击 / 四象限）----
    advanced = {}
    qc_rows, qc_th = qualified_top(tiered, lambda r: r.get("completion_rate"))
    advanced["qualified_completion"] = (qc_rows, qc_th)
    qi_rows, qi_th = qualified_top(tiered, lambda r: r.get("interaction_rate"))
    advanced["qualified_interaction"] = (qi_rows, qi_th)
    advanced["high_impression_low_click"] = high_impression_low_click(tiered)
    hclc_rows, hclc_th = qualified_high_click_low_completion(tiered)
    advanced["high_click_low_completion"] = (hclc_rows, hclc_th)
    advanced["quadrant"] = four_quadrant(tiered)
    _save_json(os.path.join(args.out, "advanced.json"), {
        "qualified_completion": {"threshold": qc_th, "records": qc_rows},
        "qualified_interaction": {"threshold": qi_th, "records": qi_rows},
        "high_impression_low_click": advanced["high_impression_low_click"],
        "high_click_low_completion": {"threshold": hclc_th, "records": hclc_rows},
        "quadrant": advanced["quadrant"],
    })
    print(f"[5.6/7] 高级分析完成（完成率门槛={qc_th}，互动率门槛={qi_th}，高点击低完成门槛={hclc_th}）")

    # ---- 6. AI 复盘 ----
    prompt = build_prompt(metrics, quality, groups, ts, records)
    prompt_path = _save(os.path.join(args.out, "ai_prompt.md"), prompt)
    ai_output = call_ai(prompt)
    if ai_output:
        ai_path = _save(os.path.join(args.out, "ai_output.md"), ai_output)
        print(f"[6/7] AI 复盘完成 -> {ai_path}")
    else:
        print(f"[6/7] 未检测到 ANTHROPIC_API_KEY，AI 提示词已保存 -> {prompt_path}（可手动粘贴给任意 AI）")

    # ---- 7. 复盘报告 ----
    report_md = generate_report(metrics, quality, tiered, groups, ts, advanced, ai_output, tier_info)
    report_path = _save(os.path.join(args.out, "复盘报告.md"), report_md)
    print(f"[7/7] 复盘报告生成 -> {report_path}")

    print("=" * 60)
    print("完成。输出文件：")
    for fn in ["data_quality_report.md", "metrics.json", "tiering.json", "comparison.md",
               "title_features.json", "title_summary.json", "ai_prompt.md", "复盘报告.md"]:
        print(f"  {os.path.join(args.out, fn)}")
    print("=" * 60)


if __name__ == "__main__":
    main()

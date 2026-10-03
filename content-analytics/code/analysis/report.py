# -*- coding: utf-8 -*-
"""
第七部分：生成复盘报告（Markdown）—— V0.3.1 版

章节（相比 V0.3 新增「四象限分析」，并在各表标注「数据置信度」）：
  1. 数据概况
  2. 整体表现
  3. Top 文章
  4. Bottom 文章
  5. 高点击文章分析
  6. 高完成率文章分析（含阅读量 + 样本门槛）
  7. 高互动文章分析（含样本门槛）
  8. 标题特征分析
  9. 高展现低点击问题（新逻辑）
  10. 高点击低完成问题（含样本门槛）
  11. 四象限内容分析（新增）
  12. 当前阶段值得验证的内容规律
  13. 下一轮内容实验建议
  14. 数据质量与局限性（含数据置信度说明）
"""

from .utils import percentile, fmt_num
from .metrics import sample_level


def _n(x):
    return "—" if x is None else f"{x:,}"


def _p(x):
    return "—" if x is None else f"{x:.1f}%"


def _m(x):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:,.2f}"
    return f"{x:,}"


def _basic_table(rows, extra_eff=False):
    """基础对比表（标题/时间/展现/阅读/点击率/完成率/时长/互动）。"""
    if not rows:
        return "（无数据）"
    head = "| 标题 | 发布时间 | 展现 | 阅读 | 点击率 | 完成率 | 阅读时长 | 点赞 | 评论 | 分享 | 收藏 |"
    sep = "|---|---|---|---|---|---|---|---|---|---|---|"
    lines = [head, sep]
    for r in rows:
        lines.append(
            f"| {r.get('title') or '—'} | {r.get('publish_time') or '—'} "
            f"| {_n(r.get('impressions'))} | {_n(r.get('reads'))} "
            f"| {_p(r.get('click_rate'))} | {_p(r.get('completion_rate'))} "
            f"| {r.get('avg_read_time') or '—'} "
            f"| {_n(r.get('likes'))} | {_n(r.get('comments'))} | {_n(r.get('shares'))} | {_n(r.get('favorites'))} |"
        )
    return "\n".join(lines)


def _level_table(rows, show_interaction=False, show_eff=False):
    """带「数据置信度」的表。"""
    if not rows:
        return "（无数据）"
    head = "| 标题 | 阅读 | 点击率 | 完成率 | 阅读时长"
    if show_interaction:
        head += " | 互动率"
    if show_eff:
        head += " | 转化效率"
    head += " | 置信度 |"
    sep = "|" + "---|" * (head.count("|") - 1)
    lines = [head, sep]
    for r in rows:
        row = (f"| {r.get('title') or '—'} | {_n(r.get('reads'))} "
               f"| {_p(r.get('click_rate'))} | {_p(r.get('completion_rate'))} "
               f"| {r.get('avg_read_time') or '—'}")
        if show_interaction:
            row += f" | {_r(r.get('interaction_rate'))}"
        if show_eff:
            row += f" | {_p(r.get('impression_efficiency'))}"
        row += f" | {sample_level(r.get('reads'))} |"
        lines.append(row)
    return "\n".join(lines)


def _r(x):
    return "—" if x is None else f"{x:.3f}"


def generate_report(metrics, quality, tiered_records, groups, title_summary,
                    advanced=None, ai_output=None, tier_info=None):
    advanced = advanced or {}
    L = []
    n = metrics.get("article_count", len(tiered_records))

    # ============ 1. 数据概况 ============
    L.append("# 今日头条内容数据复盘（V0.3.1）\n")
    L.append("> 样本量 49 篇（小样本）。严格区分【数据事实】【观察】【推测】【下一步实验】，")
    L.append("> 不把相关关系当因果关系；极低样本（reads<10）不进入主要规律判断。\n")
    L.append("## 1. 数据概况\n")
    L.append(f"- 样本文章数：**{n}** 篇")
    L.append(f"- 阅读量为 0 的文章：**{metrics.get('zero_reads_count', 0)}** 篇")
    ct = [r.get("collect_time") for r in tiered_records if r.get("collect_time")]
    if ct:
        L.append(f"- 采集时间：{min(ct)} ~ {max(ct)}")
    L.append("")

    # ============ 2. 整体表现 ============
    L.append("## 2. 整体表现\n")
    L.append("> 流量数据高度右偏，以中位数代表「大多数文章的水平」。\n")
    L.append("| 指标 | count | mean | median | P75 | P90 | max |")
    L.append("|---|---|---|---|---|---|---|")
    for key, label in [
        ("impressions", "展现量"), ("reads", "阅读量"), ("click_rate", "点击率(%)"),
        ("completion_rate", "完成率(%)"), ("interaction_rate", "互动率"),
        ("follow_rate", "涨粉率"),
    ]:
        d = metrics.get(key, {})
        L.append(f"| {label} | {d.get('count')} | {_m(d.get('mean'))} | {_m(d.get('median'))} "
                 f"| {_m(d.get('p75'))} | {_m(d.get('p90'))} | {_m(d.get('max'))} |")
    L.append("")

    # ============ 3/4. Top / Bottom ============
    L.append("## 3. Top 文章\n")
    L.append("### 3.1 高展现文章（Top 10%）\n")
    L.append(_basic_table(groups.get("top_impressions", [])))
    L.append("\n### 3.2 高阅读文章（Top 10%）\n")
    L.append(_basic_table(groups.get("top_reads", [])))
    L.append("")

    L.append("## 4. Bottom 文章\n")
    L.append("### 4.1 低展现文章（Bottom 10%）\n")
    L.append(_basic_table(groups.get("bottom_impressions", [])))
    L.append("\n### 4.2 低点击率文章（Bottom 10%）\n")
    L.append(_basic_table(groups.get("bottom_click_rate", [])))
    L.append("")

    # ============ 5. 高点击 ============
    L.append("## 5. 高点击文章分析\n")
    L.append("### 事实：Top 10% 高点击率文章\n")
    L.append(_basic_table(groups.get("top_click_rate", [])))
    L.append(_ai_block("高点击"))

    # ============ 6. 高完成率（含阅读量 + 样本门槛） ============
    qc = advanced.get("qualified_completion")
    L.append("## 6. 高完成率文章分析\n")
    if qc:
        rows, th = qc
        L.append(f"> 样本门槛：只统计 **reads >= {th}** 的文章（低于此门槛的完成率是噪声）。\n")
        L.append("### 事实：达标文章里完成率最高（完成率 + 阅读量 + 时长联合）\n")
        L.append(_level_table(rows))
    else:
        L.append("（无达标文章）")
    L.append(_ai_block("高完成率"))

    # ============ 7. 高互动（含样本门槛） ============
    qi = advanced.get("qualified_interaction")
    L.append("## 7. 高互动文章分析\n")
    if qi:
        rows, th = qi
        L.append(f"> 样本门槛：只统计 **reads >= {th}** 的文章（互动率同样会被极低阅读量污染）。\n")
        L.append("### 事实：达标文章里互动率最高\n")
        L.append(_level_table(rows, show_interaction=True))
    else:
        L.append("（无达标文章）")
    L.append(_ai_block("高互动"))

    # ============ 8. 标题特征 ============
    L.append("## 8. 标题特征分析\n")
    L.append("> 标题特征只是观察变量，只能描述相关现象，不能推出因果关系。\n")
    L.append(_title_table(title_summary))
    L.append("")

    # ============ 9. 高展现低点击（新逻辑） ============
    hilc = advanced.get("high_impression_low_click", {})
    L.append("## 9. 高展现低点击问题\n")
    L.append(f"### 事实：展现 >= {hilc.get('min_impressions', 1000):,} 的文章中，点击率最低的 {len(hilc.get('lowest_click', []))} 篇\n")
    L.append(_low_click_table(hilc.get("lowest_click", [])))
    L.append("")
    L.append(f"### 事实：高展现 + 低点击（展现>=P50={_n(hilc.get('imp_p50'))} 且 点击率<=P25非零={_p(hilc.get('p25_nonzero'))}）\n")
    L.append(_low_click_table(hilc.get("high_impression_low_click", [])))
    L.append("")
    L.append(f"### 异常样本：高展现 + 0 点击（{len(hilc.get('high_impression_zero_click', []))} 篇）\n")
    L.append(_low_click_table(hilc.get("high_impression_zero_click", [])))
    L.append(_ai_block("高展现低点击"))

    # ============ 10. 高点击低完成（含样本门槛） ============
    L.append("## 10. 高点击低完成问题\n")
    hclc = advanced.get("high_click_low_completion")
    if hclc:
        rows, th = hclc
        L.append(f"> 样本门槛：只统计 **reads >= {th}** 的文章。\n")
        L.append(f"### 事实：达标文章里「点击率较高但完成率较低」的 {len(rows)} 篇\n")
        L.append(_level_table(rows))
    else:
        L.append("（无达标文章）")
    L.append(_ai_block("高点击低完成"))

    # ============ 11. 四象限（新增） ============
    L.append("## 11. 四象限内容分析\n")
    L.append(_quadrant_section(advanced.get("quadrant")))
    L.append("")

    # ============ 12/13. 规律与建议 ============
    L.append("## 12. 当前阶段值得验证的内容规律\n")
    L.append(_ai_block("规律"))

    L.append("## 13. 下一轮内容实验建议\n")
    L.append(_ai_block("实验建议"))

    # ============ 14. 数据质量与局限性 ============
    L.append("## 14. 数据质量与局限性\n")
    L.append("- 样本量仅 49 篇，且被 1 篇爆款（陈露篇）主导，任何「高表现共同特征」都可能只是单篇的特征。")
    L.append("- **数据置信度分级**：reads<10 为「极低」、10~30「较低」、30~100「中等」、>=100「较高」。极低样本（含 reads=1）不进入主要规律判断。")
    L.append("- 完成率/互动率只在 reads 达标的文章上分析（默认>=30，不足 5 篇降到>=10）。")
    L.append("- publish_time 缺年份；0 阅读文章无完成率/时长/互动率/涨粉率，属平台未提供，用 null 区分而非填 0。")
    L.append("- 人物姓名识别依赖内置姓名库；反问/冲突等为启发式判定，存在误判。")
    L.append("- 缺正文内容（`article_content` 已预留，V1.0 补充）。")
    L.append("")

    return "\n".join(L)


def _low_click_table(rows):
    """高展现低点击专用表：强调转化效率。"""
    if not rows:
        return "（无数据）"
    head = "| 标题 | 展现 | 阅读 | 点击率 | 完成率 | 置信度 |"
    sep = "|---|---|---|---|---|---|"
    lines = [head, sep]
    for r in rows:
        lines.append(
            f"| {r.get('title') or '—'} | {_n(r.get('impressions'))} | {_n(r.get('reads'))} "
            f"| {_p(r.get('click_rate'))} | {_p(r.get('completion_rate'))} "
            f"| {sample_level(r.get('reads'))} |"
        )
    return "\n".join(lines)


def _quadrant_section(q):
    """渲染四象限分析。"""
    if not q:
        return "（无数据）"
    L = []
    L.append(f"> 横轴=点击率，纵轴=完成率，第三维=展现量。")
    L.append(f"> 阈值：点击率中位数={_p(q.get('click_median'))}，完成率中位数={_p(q.get('completion_median'))}，展现中位数={_n(q.get('impressions_p50'))}。")
    L.append(f"> 参与划分的文章：{q.get('valid_n')} 篇（reads>0，有完成率）。\n")

    name_map = {
        "高点击_高完成": "① 高点击 + 高完成",
        "高点击_低完成": "② 高点击 + 低完成",
        "低点击_高完成": "③ 低点击 + 高完成",
        "低点击_低完成": "④ 低点击 + 低完成",
    }
    for key in name_map:
        rows = q["quadrants"].get(key, [])
        L.append(f"### {name_map[key]}（{len(rows)} 篇）\n")
        L.append(_level_table(rows))
        L.append("")

    L.append("### 四类关键样本（结合展现量）\n")
    scenario_map = {
        "A_高展现高点击高完成": "A. 高展现 + 高点击 + 高完成 = 核心优质样本",
        "B_高展现低点击": "B. 高展现 + 低点击 = 标题/封面/选题吸引力值得研究",
        "C_低展现高点击": "C. 低展现 + 高点击 = 内容有吸引力但平台分发不足",
        "D_高点击低完成": "D. 高点击 + 低完成 = 标题承诺与正文承接需检查",
    }
    for key in scenario_map:
        rows = q["scenarios"].get(key, [])
        L.append(f"#### {scenario_map[key]}（{len(rows)} 篇）\n")
        L.append(_level_table(rows))
        L.append("")
    return "\n".join(L)


def _title_table(summary):
    if not summary:
        return "（无数据）"
    lines = ["| 特征 | 全样本占比 | 高阅读占比 | 低阅读占比 |", "|---|---|---|---|"]
    for k, v in summary.items():
        if k in ("n", "read_median", "high_reads_n", "low_reads_n"):
            continue
        if "all_pct" in v:
            lines.append(f"| {k} | {v['all_pct']}% | {v['high_pct']}% | {v['low_pct']}% |")
        elif "mean" in v:
            lines.append(f"| {k}（数值均值） | {v['mean']} | — | — |")
    return "\n".join(lines)


def _ai_block(tag):
    return f"\n> （“{tag}”相关的 AI 复盘结论见 ai_prompt.md 或由 AI 生成。）\n"

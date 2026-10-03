# -*- coding: utf-8 -*-
"""
================================================================================
V0.5 Content Analytics —— 主复盘报告生成器（content_review.md）

动态读取当前数据、动态计算，生成当前复盘报告。
**不依赖任何历史快照**（不出现「49 篇」「陈露篇」之类的硬编码）。

章节：
  1. 数据概况        2. 数据质量        3. 样本分层
  4. 核心指标统计    5. 四象限分析      6. 高表现内容
  7. 低表现内容      8. 标题表现观察    9. 内容表现观察
  10. 异常/注意事项  11. Hypotheses    12. Experiments
  13. 后续建议

样本门槛（只在**本层**做，不改 advanced.py 底层统计能力）：
  主分析    reads >= 30        进入主要四象限结论
  辅助观察  10 <= reads < 30   仅作辅助证据，不作强结论
  观察数据  reads < 10         保留原始数据，不进主要结论
  （reads 缺失的另列为「无阅读数据」）

原则：所有数字从当前数据动态算；标题特征只能描述相关现象，不能下因果结论。
================================================================================
"""

from statistics import mean, median

from .utils import percentile
from .metrics import sample_level, interaction_rate
from .data_quality import parse_read_time


# ======================================================================
# 样本分层（三档 + 无阅读）
# ======================================================================

def split_pools(records):
    """按阅读量把文章分成主分析 / 辅助观察 / 观察数据 / 无阅读四组。"""
    main, aux, observe, no_reads = [], [], [], []
    for r in records:
        rd = r.get("reads")
        if rd is None:
            no_reads.append(r)
        elif rd < 10:
            observe.append(r)
        elif rd < 30:
            aux.append(r)
        else:
            main.append(r)
    return {"main": main, "aux": aux, "observe": observe, "no_reads": no_reads}


# ======================================================================
# 内部小工具
# ======================================================================

def _num(x, nd=0):
    return "—" if x is None else f"{x:,.{nd}f}"


def _pct(x):
    return "—" if x is None else f"{x:.1f}%"


def _series(records, key):
    """某数值字段的升序序列（去掉 None / 非数值）。"""
    return sorted([r.get(key) for r in records
                   if isinstance(r.get(key), (int, float))
                   and not isinstance(r.get(key), bool)])


def _field_stats(records, key, nd=0, transform=None):
    """对某字段算 count/mean/median/p25/p75/p90/max。transform 可先做数值转换（如时长->秒）。"""
    if transform is not None:
        vals = sorted([transform(r.get(key)) for r in records
                       if transform(r.get(key)) is not None])
    else:
        vals = _series(records, key)
    if not vals:
        return None
    return {
        "count": len(vals),
        "mean": round(mean(vals), nd),
        "median": round(median(vals), nd),
        "p25": round(percentile(vals, 25), nd),
        "p75": round(percentile(vals, 75), nd),
        "p90": round(percentile(vals, 90), nd),
        "max": round(max(vals), nd),
    }


def _stat_table(rows):
    """渲染核心指标统计表。rows = [(label, stats_or_None, nd, is_rate), ...]"""
    L = []
    L.append("| 指标 | 样本数 | mean | median | P25 | P75 | P90 | max |")
    L.append("|---|---|---|---|---|---|---|---|")
    for label, st, nd, is_rate in rows:
        if st is None:
            L.append(f"| {label} | 0 | — | — | — | — | — | — |")
            continue
        f = _pct if is_rate else (lambda x: _num(x, nd))
        L.append(f"| {label} | {st['count']} | {f(st['mean'])} | {f(st['median'])} "
                 f"| {f(st['p25'])} | {f(st['p75'])} | {f(st['p90'])} | {f(st['max'])} |")
    return "\n".join(L)


def _level_table(rows, show_interaction=False):
    """带数据置信度的文章表（标题/阅读/点击率/完成率/时长/[互动率]/置信度）。"""
    if not rows:
        return "（无数据）"
    head = "| 标题 | 阅读 | 点击率 | 完成率 | 阅读时长"
    if show_interaction:
        head += " | 互动率"
    head += " | 置信度 |"
    sep = "|" + "---|" * (head.count("|") - 1)
    L = [head, sep]
    for r in rows:
        row = (f"| {r.get('title') or '—'} | {_num(r.get('reads'))} "
               f"| {_pct(r.get('click_rate'))} | {_pct(r.get('completion_rate'))} "
               f"| {r.get('avg_read_time') or '—'}")
        if show_interaction:
            ir = r.get("interaction_rate")
            row += f" | {'—' if ir is None else f'{ir:.3f}'}"
        row += f" | {sample_level(r.get('reads'))} |"
        L.append(row)
    return "\n".join(L)


def _basic_table(rows):
    """基础对比表（标题/时间/展现/阅读/点击率/完成率/时长/点赞/评论/转发/收藏）。"""
    if not rows:
        return "（无数据）"
    head = "| 标题 | 发布时间 | 展现 | 阅读 | 点击率 | 完成率 | 阅读时长 | 点赞 | 评论 | 转发 | 收藏 |"
    sep = "|---|---|---|---|---|---|---|---|---|---|---|"
    L = [head, sep]
    for r in rows:
        L.append(f"| {r.get('title') or '—'} | {r.get('publish_time') or '—'} "
                 f"| {_num(r.get('impressions'))} | {_num(r.get('reads'))} "
                 f"| {_pct(r.get('click_rate'))} | {_pct(r.get('completion_rate'))} "
                 f"| {r.get('avg_read_time') or '—'} | {_num(r.get('likes'))} "
                 f"| {_num(r.get('comments'))} | {_num(r.get('forwards'))} | {_num(r.get('favorites'))} |")
    return "\n".join(L)


def _render_quadrant(q):
    """渲染四象限结果：阈值 + 四象限计数 + 四类关键样本（A/B/C/D）。"""
    if not q or q.get("valid_n") in (None, 0):
        return "（该层无有效样本：需要有完成率、即 reads>0 的文章）"
    L = []
    L.append(f"> 阈值：点击率中位数={_pct(q.get('click_median'))}，完成率中位数={_pct(q.get('completion_median'))}，"
             f"展现中位数={_num(q.get('impressions_p50'))}。参与划分 {q.get('valid_n')} 篇。\n")

    quads = q.get("quadrants", {})
    name_map = {
        "高点击_高完成": "① 高点击 + 高完成",
        "高点击_低完成": "② 高点击 + 低完成",
        "低点击_高完成": "③ 低点击 + 高完成",
        "低点击_低完成": "④ 低点击 + 低完成",
    }
    L.append("| 象限 | 篇数 |")
    L.append("|---|---|")
    for key, name in name_map.items():
        L.append(f"| {name} | {len(quads.get(key, []))} |")
    L.append("")

    scenario_map = {
        "A_高展现高点击高完成": "A. 高展现 + 高点击 + 高完成 = 核心优质样本",
        "B_高展现低点击": "B. 高展现 + 低点击 = 标题/封面/选题吸引力值得研究",
        "C_低展现高点击": "C. 低展现 + 高点击 = 内容有吸引力但平台分发不足",
        "D_高点击低完成": "D. 高点击 + 低完成 = 标题承诺与正文承接需检查",
    }
    for key, name in scenario_map.items():
        rows = q.get("scenarios", {}).get(key, [])
        L.append(f"#### {name}（{len(rows)} 篇）\n")
        L.append(_level_table(rows))
        L.append("")
    return "\n".join(L)


def _title_table(title_summary):
    """渲染标题特征：数值特征均值 + 布尔特征（全样本/高阅读/低阅读占比）。"""
    if not title_summary:
        return "（无数据）"
    L = []
    L.append("| 特征 | 全样本占比 | 高阅读占比 | 低阅读占比 |")
    L.append("|---|---|---|---|")
    for k, v in title_summary.items():
        if k in ("n", "read_median", "high_reads_n", "low_reads_n"):
            continue
        if "all_pct" in v:
            L.append(f"| {k} | {v['all_pct']}% | {v['high_pct']}% | {v['low_pct']}% |")
        elif "mean" in v:
            L.append(f"| {k}（均值） | {v['mean']} | — | — |")
    return "\n".join(L)


def _has_body(records):
    """判断当前数据里是否存在正文数据（article_content / body 字段，或 articles 目录）。"""
    for r in records:
        if r.get("article_content") or r.get("body"):
            return True
    return False


# ======================================================================
# 主报告生成
# ======================================================================

def generate_content_review(records, quality, metrics, pools, groups, title_summary, advanced):
    """
    生成 content_review.md 全文（Markdown 字符串）。

    参数：
      records        全部记录（清洗后）
      quality        analysis.data_quality.check_quality() 的结果
      metrics        analysis.metrics.compute_metrics() 的结果
      pools          content_review.split_pools() 的结果
      groups         analysis.compare.extract_groups() 返回的 (groups, k) 中的 groups
      title_summary  analysis.title_features.summarize() 的结果
      advanced       {"quadrant_main": four_quadrant(main), "quadrant_aux": four_quadrant(aux)}
    """
    L = []
    n = len(records)
    main, aux, observe, no_reads = pools["main"], pools["aux"], pools["observe"], pools["no_reads"]

    # ============ 1. 数据概况 ============
    L.append("# 内容数据复盘（Content Analytics）\n")
    L.append("> 本报告由当前数据动态生成，严格区分【数据事实】【观察】【假设】。")
    L.append("> 相关关系不等于因果关系；reads<10 的样本不进入主要结论。\n")
    L.append("## 1. 数据概况\n")
    L.append(f"- 文章总数：**{n}** 篇")
    L.append(f"- 阅读量为 0 或缺失：**{metrics.get('zero_reads_count', 0)}** 篇")
    ct = [r.get("collect_time") for r in records if r.get("collect_time")]
    if ct:
        L.append(f"- 采集时间范围：{min(ct)} ~ {max(ct)}")
    pt = [r.get("publish_time") for r in records if r.get("publish_time")]
    if pt:
        L.append(f"- 发布时间范围：{min(pt)} ~ {max(pt)}")
    L.append("")

    # ============ 2. 数据质量 ============
    L.append("## 2. 数据质量\n")
    if quality.get("status") == "ok":
        L.append("> ✅ 未发现需要关注的质量问题。\n")
    else:
        L.append("> ⚠️ **数据质量警告**：发现以下问题，下列结论请谨慎对待。\n")
        for issue in quality.get("issues", []):
            L.append(f"- {issue}")
    dup = quality.get("duplicate_ids", {})
    L.append(f"- 重复 article_id：{len(dup)} 组" + (f"（{dup}）" if dup else ""))
    L.append(f"- 核心字段缺失：展现量缺失 {quality['missing'].get('impressions', 0)} 篇、"
             f"阅读量缺失 {quality['missing'].get('reads', 0)} 篇")
    L.append("")

    # ============ 3. 样本分层 ============
    L.append("## 3. 样本分层\n")
    L.append("| 分层 | 门槛 | 篇数 | 用途 |")
    L.append("|---|---|---|---|")
    L.append(f"| 主分析 | reads >= 30 | {len(main)} | 进入主要四象限结论 |")
    L.append(f"| 辅助观察 | 10 <= reads < 30 | {len(aux)} | 仅作辅助证据，不作强结论 |")
    L.append(f"| 观察数据 | reads < 10 | {len(observe)} | 保留原始数据，不进主要结论 |")
    L.append(f"| 无阅读数据 | reads 缺失 | {len(no_reads)} | 不进任何规律判断 |")
    L.append("")
    L.append("> 注意：reads 极低时 CTR / 完读率 / 时长 / 互动率都极不稳定，")
    L.append("> 不能因为某篇 reads=1 却出现 100% 完成率就判为高完成率优质样本。")
    L.append("")

    # ============ 4. 核心指标统计 ============
    L.append("## 4. 核心指标统计\n")
    L.append("> 流量数据高度右偏，以 median / 分位数代表「大多数文章」的水平。\n")
    L.append(_stat_table([
        ("展现量", _field_stats(records, "impressions"), 0, False),
        ("阅读量", _field_stats(records, "reads"), 0, False),
        ("点击率(%)", _field_stats(records, "click_rate"), 2, True),
        ("完成率(%)", _field_stats(records, "completion_rate"), 2, True),
        ("阅读时长(秒)", _field_stats(records, "avg_read_time", nd=1, transform=parse_read_time), 1, False),
        ("点赞", _field_stats(records, "likes"), 0, False),
        ("评论", _field_stats(records, "comments"), 0, False),
        ("转发", _field_stats(records, "forwards"), 0, False),
        ("分享", _field_stats(records, "shares"), 0, False),
        ("收藏", _field_stats(records, "favorites"), 0, False),
        ("涨粉", _field_stats(records, "new_followers"), 0, False),
        ("阅读转粉率(%)", _field_stats(records, "read_to_follow_rate"), 3, True),
    ]))
    L.append("")

    # ============ 5. 四象限分析 ============
    L.append("## 5. 四象限分析\n")
    L.append("> 横轴=点击率，纵轴=完成率，第三维=展现量。\n")
    L.append(f"### 5.1 主分析（reads >= 30，{len(main)} 篇）\n")
    L.append(_render_quadrant(advanced.get("quadrant_main")))
    L.append(f"\n### 5.2 辅助观察（10 <= reads < 30，{len(aux)} 篇）\n")
    L.append(_render_quadrant(advanced.get("quadrant_aux")))
    L.append("")

    # ============ 6. 高表现内容 ============
    L.append("## 6. 高表现内容\n")
    L.append("### 6.1 高展现（Top 10%）\n")
    L.append(_basic_table(groups.get("top_impressions", [])))
    L.append("\n### 6.2 高阅读（Top 10%）\n")
    L.append(_basic_table(groups.get("top_reads", [])))
    L.append("\n### 6.3 高点击率（Top 10%）\n")
    L.append(_basic_table(groups.get("top_click_rate", [])))
    L.append("\n### 6.4 高完成率（含样本门槛）\n")
    qc = advanced.get("qualified_completion")
    if qc:
        qc_rows, qc_th = qc
        L.append(f"> 样本门槛：只统计 reads >= {qc_th} 的文章（低于此门槛的完成率是噪声）。\n")
        L.append(_level_table(qc_rows))
    else:
        L.append("（无达标文章）")
    L.append("\n### 6.5 高互动（含样本门槛）\n")
    qi = advanced.get("qualified_interaction")
    if qi:
        qi_rows, qi_th = qi
        L.append(f"> 样本门槛：只统计 reads >= {qi_th} 的文章（互动率同样会被极低阅读量污染）。\n")
        L.append(_level_table(qi_rows, show_interaction=True))
    else:
        L.append("（无达标文章）")
    L.append("")

    # ============ 7. 低表现内容 ============
    L.append("## 7. 低表现内容\n")
    L.append("### 7.1 低展现（Bottom 10%）\n")
    L.append(_basic_table(groups.get("bottom_impressions", [])))
    L.append("\n### 7.2 低点击率（Bottom 10%）\n")
    L.append(_basic_table(groups.get("bottom_click_rate", [])))
    L.append("")

    # ============ 8. 标题表现观察 ============
    L.append("## 8. 标题表现观察\n")
    L.append("> 标题特征只是观察变量，只能描述「该特征与较高/较低阅读**同时出现**」，")
    L.append("> **不能推出因果关系**（不能说某个特征导致 CTR 提高）。\n")
    L.append(_title_table(title_summary))
    L.append("")

    # ============ 9. 内容表现观察 ============
    L.append("## 9. 内容表现观察\n")
    if _has_body(records):
        L.append("检测到正文数据，正文表现归因见后续分析。")
    else:
        L.append("> **当前没有正文数据，因此本轮不进行正文表现归因。**")
        L.append("> 未来若 articles/ 中存在 article_id + title + body，将按 article_id 关联后分析 Hook / 信息推进 / 信息密度 / 标题兑现 / 结尾 / AI 模板感等。")
    L.append("")

    # ============ 10. 异常/注意事项 ============
    L.append("## 10. 异常 / 注意事项\n")
    outliers = quality.get("outliers", {})
    if outliers:
        L.append("- 异常值（IQR 1.5 倍上界，仅提示不判错）：")
        for f, info in outliers.items():
            L.append(f"  - `{f}` 有 {info['count']} 个值超过上界 {info['upper_bound']:,.0f}，最大 {info['max_value']:,.0f}")
    else:
        L.append("- 未发现明显超过 IQR 上界的异常值。")
    L.append("- publish_time 只有「月-日 时:分」没有年份，跨年文章可能偏差。")
    L.append("- 0 阅读文章无完成率 / 时长 / 互动率 / 涨粉率，属平台未提供，用 null 区分而非填 0。")
    L.append("- 人物姓名识别依赖内置姓名库；反问 / 冲突为启发式判定，存在误判。")
    L.append(f"- 样本量仅 {n} 篇，任何「高表现共同特征」都只是观察，需通过实验验证后才可能成为规则。")
    L.append("")

    # ============ 11/12/13. 策略沉淀（由复盘 AI 写入 strategy/）============
    L.append("## 11. Hypotheses\n")
    L.append("> 待验证假设由复盘 AI 写入 `strategy/hypotheses.md`，本报告不直接下结论。\n")
    L.append("## 12. Experiments\n")
    L.append("> 实验设计由复盘 AI 写入 `strategy/experiments.md`。\n")
    L.append("## 13. 后续建议\n")
    L.append("> 见 `ai_prompt.md`（复盘提示词）与 `strategy/` 各文件；")
    L.append("> 建议优先积累 reads >= 30 的样本，使四象限与标题观察具备统计意义。\n")

    return "\n".join(L)

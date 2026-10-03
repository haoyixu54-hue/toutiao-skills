# -*- coding: utf-8 -*-
"""
第三部分：文章表现分层

不按「绝对阅读量」一刀切，而是按分位数把文章分成 5 档：
  Top 10%  /  Top 25%  /  Middle  /  Bottom 25%  /  Bottom 10%

分层维度：
  A. 展现表现   -> impressions
  B. 点击表现   -> click_rate（点击率，去掉展现量级的干扰）
  C. 阅读表现   -> reads
  D. 完读表现   -> completion_rate（0 阅读的文章没有完读率 -> 无数据）
  E. 互动表现   -> interaction_rate（0 阅读 -> 无数据）

综合表现：不设主观权重，改用「各维度百分位排名的算术平均」，
这是一个透明、可解释的做法，不是拍脑袋的加权。
"""

from .metrics import interaction_rate
from .utils import percentile, pct_rank

# 5 档标签（从高到低）
TIERS = ["Top 10%", "Top 25%", "Middle", "Bottom 25%", "Bottom 10%"]


def _tier(value, sorted_vals, th):
    """根据阈值给单个值分层。th = {p10,p25,p75,p90}。None -> 无数据。"""
    if value is None:
        return "无数据"
    if th["p90"] is not None and value >= th["p90"]:
        return "Top 10%"
    if th["p75"] is not None and value >= th["p75"]:
        return "Top 25%"
    if th["p10"] is not None and value < th["p10"]:
        return "Bottom 10%"
    if th["p25"] is not None and value < th["p25"]:
        return "Bottom 25%"
    return "Middle"


def _thresholds(sorted_vals):
    """计算 p10/p25/p75/p90 阈值。"""
    return {
        "p10": percentile(sorted_vals, 10),
        "p25": percentile(sorted_vals, 25),
        "p75": percentile(sorted_vals, 75),
        "p90": percentile(sorted_vals, 90),
    }


def tier_articles(records):
    """
    给每篇文章打分层标签，返回 (记录副本, 分层说明)。

    在记录上新增字段：
      tier_impressions / tier_click / tier_reads / tier_completion / tier_interaction
      composite_score（0~100 的百分位均值）、tier_composite
    """
    recs = [dict(r) for r in records]

    # 各维度的值序列（升序）
    dims = {
        "impressions": "impressions",
        "click": "click_rate",
        "reads": "reads",
        "completion": "completion_rate",
        "interaction": None,  # 特殊：用 interaction_rate
    }

    # 先算每篇的互动率（临时挂在 rec 上）
    for r in recs:
        r["_interaction_rate"] = interaction_rate(r)

    series = {}
    for dim, key in dims.items():
        if dim == "interaction":
            vals = sorted([r["_interaction_rate"] for r in recs
                           if r["_interaction_rate"] is not None])
        else:
            vals = sorted([r.get(key) for r in recs
                           if isinstance(r.get(key), (int, float))
                           and not isinstance(r.get(key), bool)])
        series[dim] = vals

    # 阈值
    ths = {dim: _thresholds(vals) for dim, vals in series.items()}

    # 打标签
    for r in recs:
        r["tier_impressions"] = _tier(r.get("impressions"), series["impressions"], ths["impressions"])
        r["tier_click"] = _tier(r.get("click_rate"), series["click"], ths["click"])
        r["tier_reads"] = _tier(r.get("reads"), series["reads"], ths["reads"])
        r["tier_completion"] = _tier(r.get("completion_rate"), series["completion"], ths["completion"])
        r["tier_interaction"] = _tier(r["_interaction_rate"], series["interaction"], ths["interaction"])

        # 综合分：各维度百分位排名的算术平均（缺的维度跳过）
        ranks = []
        ranks.append(pct_rank(r.get("impressions"), series["impressions"]))
        ranks.append(pct_rank(r.get("click_rate"), series["click"]))
        ranks.append(pct_rank(r.get("reads"), series["reads"]))
        ranks.append(pct_rank(r.get("completion_rate"), series["completion"]))
        ranks.append(pct_rank(r["_interaction_rate"], series["interaction"]))
        ranks = [x for x in ranks if x is not None]
        r["composite_score"] = round(sum(ranks) / len(ranks), 1) if ranks else None

    # 综合分层（用综合分的阈值）
    comp_vals = sorted([r["composite_score"] for r in recs if r["composite_score"] is not None])
    comp_th = _thresholds(comp_vals)
    for r in recs:
        r["tier_composite"] = _tier(r["composite_score"], comp_vals, comp_th)
        # 清理临时字段
        r.pop("_interaction_rate", None)

    info = {
        "tiers": TIERS,
        "thresholds": {dim: ths[dim] for dim in ths},
        "note": "综合表现 = 各维度百分位排名的算术平均（无主观权重）",
    }
    return recs, info

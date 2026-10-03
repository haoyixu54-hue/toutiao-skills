# -*- coding: utf-8 -*-
"""
第二部分：建立基础指标

注意：这里「不用平均值当唯一标准」，而是同时给出 mean / median / 分位数，
因为流量数据（展现、阅读）高度右偏，中位数和分位数更能代表「大多数文章」。

额外计算两个派生指标：
  interaction_rate = (点赞+评论+分享+转发+收藏) / 阅读量   （阅读量为 0 -> None）
  follow_rate      = new_followers / 阅读量                  （阅读量为 0 -> None）
"""

from statistics import mean, median

from .utils import percentile


def sample_level(reads):
    """
    数据置信度等级（基于阅读量）。
      reads < 10            极低
      10 <= reads < 30      较低
      30 <= reads < 100     中等
      reads >= 100          较高
    极低样本不进入主要规律判断。
    """
    if reads is None or reads < 10:
        return "极低"
    if reads < 30:
        return "较低"
    if reads < 100:
        return "中等"
    return "较高"


def impression_efficiency(rec):
    """
    展现转化效率 = reads / impressions（业务视角命名，数值上等于点击率）。
    impressions 为 0 或 reads 缺失时返回 None。
    """
    imp = rec.get("impressions")
    rd = rec.get("reads")
    if not imp or rd is None:
        return None
    return rd / imp


def _series(records, key):
    """提取某字段的数值序列（升序，去掉 None）。"""
    return sorted([r.get(key) for r in records
                   if isinstance(r.get(key), (int, float))
                   and not isinstance(r.get(key), bool)])


def interaction_rate(rec):
    """互动率 = (点赞+评论+分享+转发+收藏) / 阅读量。阅读量为 0 返回 None。"""
    reads = rec.get("reads")
    if not reads:  # 0 或 None 都不计算
        return None
    inter = sum(rec.get(k) or 0 for k in ("likes", "comments", "shares", "forwards", "favorites"))
    return inter / reads


def follow_rate(rec):
    """涨粉率 = new_followers / 阅读量。阅读量为 0 返回 None。"""
    reads = rec.get("reads")
    if not reads:
        return None
    nf = rec.get("new_followers") or 0
    return nf / reads


def compute_metrics(records):
    """
    计算全部基础指标，返回 dict。
    每个字段的指标是 dict：{mean, median, p25, p75, p90, max, count}（按需）。
    """
    m = {}

    # ---- 1. 文章数量 ----
    m["article_count"] = len(records)

    # ---- 2. 展现量 ----
    imp = _series(records, "impressions")
    m["impressions"] = {
        "count": len(imp),
        "mean": mean(imp) if imp else None,
        "median": median(imp) if imp else None,
        "p25": percentile(imp, 25),
        "p75": percentile(imp, 75),
        "p90": percentile(imp, 90),
        "max": max(imp) if imp else None,
    }

    # ---- 3. 阅读量 ----
    rd = _series(records, "reads")
    m["reads"] = {
        "count": len(rd),
        "mean": mean(rd) if rd else None,
        "median": median(rd) if rd else None,
        "p75": percentile(rd, 75),
        "p90": percentile(rd, 90),
        "max": max(rd) if rd else None,
    }

    # ---- 4. 点击率 ----
    cr = _series(records, "click_rate")
    m["click_rate"] = {
        "count": len(cr),
        "mean": mean(cr) if cr else None,
        "median": median(cr) if cr else None,
        "p75": percentile(cr, 75),
        "p90": percentile(cr, 90),
    }

    # ---- 5. 完成率 ----
    comp = _series(records, "completion_rate")
    m["completion_rate"] = {
        "count": len(comp),
        "mean": mean(comp) if comp else None,
        "median": median(comp) if comp else None,
        "p75": percentile(comp, 75),
        "p90": percentile(comp, 90),
    }

    # ---- 6. 互动率 ----
    ir = sorted([interaction_rate(r) for r in records
                 if interaction_rate(r) is not None])
    m["interaction_rate"] = {
        "count": len(ir),
        "mean": mean(ir) if ir else None,
        "median": median(ir) if ir else None,
        "p75": percentile(ir, 75),
        "p90": percentile(ir, 90),
        "max": max(ir) if ir else None,
    }

    # ---- 7. 涨粉率 ----
    fr = sorted([follow_rate(r) for r in records if follow_rate(r) is not None])
    m["follow_rate"] = {
        "count": len(fr),
        "mean": mean(fr) if fr else None,
        "median": median(fr) if fr else None,
        "p75": percentile(fr, 75),
        "p90": percentile(fr, 90),
        "max": max(fr) if fr else None,
    }

    # 附加：阅读量为 0 的文章数（用于解释完读率/时长缺失）
    m["zero_reads_count"] = sum(1 for r in records if r.get("reads") == 0)
    return m

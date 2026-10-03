# -*- coding: utf-8 -*-
"""
V0.3.1 高级分析（修正低样本失真 + 四象限 + 数据置信度）

解决的问题：
  1. 低样本率指标失真 —— 互动率/完成率默认只对 reads >= 30 的文章排名，
     不足 5 篇则降到 reads >= 10，并在报告中说明。reads=1 的文章绝不进「优秀」。
  2. 高展现低点击筛选失效 —— 改为：先过滤 impressions >= 1000，再按 click_rate
     升序取最低 10 篇（优先展示高展现）；另算 P25_nonzero；单独列出「高展现+0点击」异常。
  3. 完成率必须结合阅读量 —— 三指标联合（completion_rate + reads + avg_read_time）。

新增：
  - 四象限内容分析（横轴 click_rate，纵轴 completion_rate，第三维展现量）
  - sample_level 数据置信度标注
"""

from statistics import median

from .metrics import interaction_rate, sample_level, impression_efficiency
from .utils import percentile


# ======================================================================
# 样本门槛
# ======================================================================

def qualified_pool(records, min_reads=30, fallback_reads=10, need=5):
    """
    选出「样本量达标」的文章用于排名。
    默认 reads >= min_reads；若达标文章不足 need 篇，则降到 reads >= fallback_reads。
    返回 (达标文章列表, 实际使用的门槛)。
    """
    q = [r for r in records if (r.get("reads") or 0) >= min_reads]
    if len(q) >= need:
        return q, min_reads
    q2 = [r for r in records if (r.get("reads") or 0) >= fallback_reads]
    return q2, fallback_reads


def qualified_top(records, key_func, min_reads=30, fallback_reads=10, need=5, top_n=5):
    """
    在达标样本里按 key_func 降序取前 top_n 篇。
    返回 (文章列表, 使用的门槛)。
    """
    pool, th = qualified_pool(records, min_reads, fallback_reads, need)
    scored = sorted(
        pool,
        key=lambda r: (key_func(r) if key_func(r) is not None else float("-inf")),
        reverse=True,
    )
    return scored[:top_n], th


# ======================================================================
# 问题2：高展现低点击（新逻辑）
# ======================================================================

def high_impression_low_click(records, min_impressions=1000, top_n=10):
    """
    高展现低点击分析。

    1) 过滤 impressions >= min_impressions（默认 1000）
    2) 按 click_rate 升序（最低点击率在前），同点击率按展现降序（优先展示高展现）
    3) 输出最低点击率的 top_n 篇
    4) 定义「高展现+低点击」：impressions >= P50 且 click_rate <= P25_nonzero
    5) 单独列出「高展现+0点击」异常样本

    返回 dict。
    """
    pool = [r for r in records if (r.get("impressions") or 0) >= min_impressions]
    # 低点击率优先，同点击率时展现高的排前
    pool_sorted = sorted(
        pool,
        key=lambda r: (
            r.get("click_rate") if r.get("click_rate") is not None else 9999.0,
            -(r.get("impressions") or 0),
        ),
    )
    lowest = pool_sorted[:top_n]

    # 阈值
    imp_vals = sorted([r.get("impressions") for r in records
                       if r.get("impressions") is not None])
    imp_p50 = percentile(imp_vals, 50)
    nonzero_click = sorted([r.get("click_rate") for r in records
                            if (r.get("click_rate") or 0) > 0])
    p25_nonzero = percentile(nonzero_click, 25) if nonzero_click else 0.0

    # 高展现+低点击（P50 展现 + P25_nonzero 点击）
    hilo = [r for r in records
            if (r.get("impressions") or 0) >= (imp_p50 or 0)
            and (r.get("click_rate") or 0) <= p25_nonzero
            and (r.get("click_rate") or 0) > 0]  # 排除 0 点击（0 点击单列）

    # 高展现+0点击 异常样本
    zero_click = [r for r in records
                  if (r.get("click_rate") == 0)
                  and (r.get("impressions") or 0) >= (imp_p50 or 0)]
    zero_click.sort(key=lambda r: -(r.get("impressions") or 0))

    return {
        "min_impressions": min_impressions,
        "pool_size": len(pool),
        "lowest_click": lowest,
        "imp_p50": imp_p50,
        "p25_nonzero": p25_nonzero,
        "high_impression_low_click": hilo,
        "high_impression_zero_click": zero_click,
    }


# ======================================================================
# 问题3 + 高点击低完成：结合阅读量的联合分析
# ======================================================================

def qualified_high_click_low_completion(records, min_reads=30, fallback_reads=10, need=5):
    """
    在达标样本里找「点击率较高但完成率较低」的文章（标题承诺与正文承接需检查）。
    返回 (文章列表, 使用的门槛)。
    """
    pool, th = qualified_pool(records, min_reads, fallback_reads, need)
    valid = [r for r in pool
             if r.get("completion_rate") is not None and r.get("click_rate") is not None]
    if not valid:
        return [], th
    click_med = median([r["click_rate"] for r in valid])
    comp_med = median([r["completion_rate"] for r in valid])
    out = [r for r in valid
           if r["click_rate"] >= click_med and r["completion_rate"] <= comp_med]
    out.sort(key=lambda r: -(r.get("click_rate") or 0))
    return out, th


# ======================================================================
# 新增：四象限内容分析
# ======================================================================

def four_quadrant(records):
    """
    四象限：横轴 = click_rate，纵轴 = completion_rate，第三维 = 展现量。

    只在有 completion_rate（即 reads > 0）的文章里划分。
    高/低用中位数切分。
    返回 dict：四个象限 + 阈值 + 四类关键样本（A/B/C/D）。
    """
    valid = [r for r in records if r.get("completion_rate") is not None]

    click_vals = sorted([r.get("click_rate") for r in valid
                         if r.get("click_rate") is not None])
    comp_vals = sorted([r.get("completion_rate") for r in valid
                        if r.get("completion_rate") is not None])
    click_med = median(click_vals) if click_vals else None
    comp_med = median(comp_vals) if comp_vals else None

    imp_vals = sorted([r.get("impressions") for r in records
                       if r.get("impressions") is not None])
    imp_p50 = percentile(imp_vals, 50)

    quad = {"高点击_高完成": [], "高点击_低完成": [],
            "低点击_高完成": [], "低点击_低完成": []}

    for r in valid:
        cr, cp = r.get("click_rate"), r.get("completion_rate")
        if cr is None or cp is None or click_med is None or comp_med is None:
            continue
        x = "高点击" if cr >= click_med else "低点击"
        y = "高完成" if cp >= comp_med else "低完成"
        quad[f"{x}_{y}"].append(r)

    # 四类关键样本（结合展现量第三维）
    def _pick(pred, key="impressions"):
        out = [r for r in valid if pred(r)]
        out.sort(key=lambda r: -(r.get(key) or 0))
        return out

    scenarios = {
        # A. 高展现 + 高点击 + 高完成 = 核心优质样本
        "A_高展现高点击高完成": _pick(
            lambda r: (r.get("impressions") or 0) >= (imp_p50 or 0)
            and r.get("click_rate") >= click_med and r.get("completion_rate") >= comp_med),
        # B. 高展现 + 低点击 = 标题/封面/选题吸引力值得研究
        "B_高展现低点击": _pick(
            lambda r: (r.get("impressions") or 0) >= (imp_p50 or 0)
            and r.get("click_rate") < click_med),
        # C. 低展现 + 高点击 = 内容有吸引力但分发不足
        "C_低展现高点击": _pick(
            lambda r: (r.get("impressions") or 0) < (imp_p50 or 0)
            and r.get("click_rate") >= click_med),
        # D. 高点击 + 低完成 = 标题承诺与正文承接需检查
        "D_高点击低完成": _pick(
            lambda r: r.get("click_rate") >= click_med
            and r.get("completion_rate") < comp_med),
    }

    return {
        "valid_n": len(valid),
        "click_median": click_med,
        "completion_median": comp_med,
        "impressions_p50": imp_p50,
        "quadrants": quad,
        "scenarios": scenarios,
    }

# -*- coding: utf-8 -*-
"""
第四部分：生成对比数据

分别提取 Top 10% 和 Bottom 10% 文章组：
  高展现 / 高阅读 / 高点击率 / 高完成率 / 高互动
  低展现 / 低点击率

每组输出统一字段：标题、发布时间、展现、阅读、点击率、完成率、
阅读时长、点赞、评论、分享、收藏。
"""

import math

from .metrics import interaction_rate

# 对比组输出的统一字段
GROUP_FIELDS = [
    "title", "publish_time", "impressions", "reads", "click_rate",
    "completion_rate", "avg_read_time", "likes", "comments", "shares", "favorites",
]


def _top_n(records, key_func, n, reverse=True):
    """
    按 key_func 排序取前 n 篇。
    None 值总是排到最末（用 ±inf 实现），保证「0 阅读 / 无完读率」的文章
    不会因为 None 的排序问题混进 Top/Bottom 组。
    """
    scored = [(key_func(r), r) for r in records]
    if reverse:
        scored.sort(key=lambda x: (x[0] if x[0] is not None else float("-inf")), reverse=True)
    else:
        scored.sort(key=lambda x: (x[0] if x[0] is not None else float("inf")))
    return [r for _, r in scored[:n]]


def extract_groups(records, top_pct=0.10):
    """
    提取各 Top/Bottom 组。返回 dict：组名 -> 文章列表（带所选指标）。

    高互动 / 高完成率 只对「有阅读 / 有完读率」的文章排序，
    0 阅读的文章天然无法进入这些组。
    """
    n = len(records)
    k = max(1, math.ceil(n * top_pct))  # Top/Bottom 10% 的篇数

    groups = {}

    def _pick(name, key_func, reverse=True):
        rows = _top_n(records, key_func, k, reverse)
        groups[name] = [dict(r) for r in rows]

    # Top 10%
    _pick("top_impressions", lambda r: r.get("impressions"))
    _pick("top_reads", lambda r: r.get("reads"))
    _pick("top_click_rate", lambda r: r.get("click_rate"))
    _pick("top_completion_rate", lambda r: r.get("completion_rate"))
    # 高互动：用互动率（0 阅读自动排到末位，进不了 Top）
    _pick("top_interaction", lambda r: interaction_rate(r))

    # Bottom 10%
    _pick("bottom_impressions", lambda r: r.get("impressions"), reverse=False)
    _pick("bottom_click_rate", lambda r: r.get("click_rate"), reverse=False)

    return groups, k


def render_groups(groups):
    """把对比组渲染成 Markdown 表格。"""
    title_map = {
        "top_impressions": "Top 10% 高展现文章",
        "top_reads": "Top 10% 高阅读文章",
        "top_click_rate": "Top 10% 高点击率文章",
        "top_completion_rate": "Top 10% 高完成率文章",
        "top_interaction": "Top 10% 高互动文章",
        "bottom_impressions": "Bottom 10% 低展现文章",
        "bottom_click_rate": "Bottom 10% 低点击率文章",
    }
    L = []
    for name in title_map:
        rows = groups.get(name, [])
        L.append(f"\n### {title_map[name]}\n")
        if not rows:
            L.append("（无数据）\n")
            continue
        L.append("| 标题 | 发布时间 | 展现 | 阅读 | 点击率 | 完成率 | 阅读时长 | 点赞 | 评论 | 分享 | 收藏 |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            L.append(
                f"| {r.get('title') or '—'} | {r.get('publish_time') or '—'} "
                f"| {_n(r.get('impressions'))} | {_n(r.get('reads'))} "
                f"| {_p(r.get('click_rate'))} | {_p(r.get('completion_rate'))} "
                f"| {r.get('avg_read_time') or '—'} "
                f"| {_n(r.get('likes'))} | {_n(r.get('comments'))} | {_n(r.get('shares'))} | {_n(r.get('favorites'))} |"
            )
    return "\n".join(L)


def _n(x):
    return "—" if x is None else f"{x:,}"


def _p(x):
    return "—" if x is None else f"{x:.1f}%"

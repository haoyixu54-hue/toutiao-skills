# -*- coding: utf-8 -*-
"""
================================================================================
字段定义（单一数据源 / Single Source of Truth）
================================================================================

所有要采集的字段：英文 key、中文标签、提取方式、清洗方式，都集中在这里定义。

以后要新增字段，只需要两步：
  1. 在 DRAWER_FIELDS 里加一行（指定 key / 中文标签 / kind / ctype）
  2. 如果 kind 是新的类型，在 collector/detail_page.py 里补一个对应的提取函数

kind（提取方式）说明：
  "num"       —— 按中文标签找 .primary / .second / .inter-item 元素，取里面的 .num（最常见）
  "read_time" —— 平均阅读时长（「分」「秒」拆在两个 .num 里，需要拼接）
  "up"        —— 涨粉（结构特殊：.fan-change .up .num）
  "down"      —— 掉粉（结构特殊：.fan-change .down .num）
  "extra"     —— 对比信息（"超过 X% 同类作品"，在 .extra-data 里）

ctype（清洗方式，供 data_cleaning 使用）说明：
  "int"    —— 转成整数（自动处理 "2,376"、"13.0万" 这类写法）
  "float"  —— 转成浮点数
  "rate"   —— 百分比，去掉 % 转成浮点数（"4.0%" -> 4.0）
  "text"   —— 保持字符串（只做去空白处理）
================================================================================
"""

# ============ 详情抽屉里要采集的字段 ============
DRAWER_FIELDS = [
    # ---- 流量 ----
    {"key": "impressions",         "label": "展现量",         "kind": "num",       "ctype": "int"},
    {"key": "fan_impressions",     "label": "粉丝展现量",     "kind": "num",       "ctype": "int"},
    {"key": "reads",               "label": "阅读量",         "kind": "num",       "ctype": "int"},
    {"key": "fan_reads",           "label": "粉丝阅读量",     "kind": "num",       "ctype": "int"},
    {"key": "click_rate",          "label": "点击率",         "kind": "num",       "ctype": "rate"},
    {"key": "completion_rate",     "label": "平均阅读完成率", "kind": "num",       "ctype": "rate"},
    {"key": "avg_read_time",       "label": "平均阅读时长",   "kind": "read_time", "ctype": "text"},
    # ---- 收益（额外保留，方便以后扩展）----
    {"key": "revenue",             "label": "创作收益",       "kind": "num",       "ctype": "float"},
    # ---- 粉丝 ----
    {"key": "fan_change",          "label": "粉丝变化",       "kind": "num",       "ctype": "int"},
    {"key": "new_followers",       "label": "涨粉",           "kind": "up",        "ctype": "int"},
    {"key": "unfollow",            "label": "掉粉",           "kind": "down",      "ctype": "int"},
    {"key": "read_to_follow_rate", "label": "阅读转粉率",     "kind": "num",       "ctype": "rate"},
    # ---- 互动 ----
    {"key": "comments",            "label": "评论",           "kind": "num",       "ctype": "int"},
    {"key": "likes",               "label": "点赞",           "kind": "num",       "ctype": "int"},
    {"key": "forwards",            "label": "转发",           "kind": "num",       "ctype": "int"},
    {"key": "shares",              "label": "分享",           "kind": "num",       "ctype": "int"},
    {"key": "favorites",           "label": "收藏",           "kind": "num",       "ctype": "int"},
    # ---- 对比信息 ----
    {"key": "click_rate_compare",      "label": "点击率",         "kind": "extra", "ctype": "text"},
    {"key": "completion_rate_compare", "label": "平均阅读完成率", "kind": "extra", "ctype": "text"},
]


# ============ 输出字段的固定顺序（保证 JSON 可读、CSV/Excel 列顺序一致） ============
# 前面是「基本信息 + 第三阶段指定的核心字段」，后面是额外字段和元信息。
FIELD_ORDER = [
    # 基本信息
    "article_id",
    "title",
    "publish_time",
    "collect_time",
    # 核心表现数据（对应第三阶段字段清单）
    "impressions",
    "reads",
    "likes",
    "comments",
    "shares",
    "forwards",
    "favorites",
    "fan_impressions",
    "fan_reads",
    "click_rate",
    "completion_rate",
    "avg_read_time",
    "fan_change",
    "new_followers",
    "unfollow",
    "read_to_follow_rate",
    # 额外字段
    "revenue",
    "click_rate_compare",
    "completion_rate_compare",
    # 元信息
    "source_url",
    "collection_status",
    "error_message",
]

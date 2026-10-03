# -*- coding: utf-8 -*-
"""
数据清洗

采集器返回的是页面上的「原始文本」，例如 "2,376"、"13.0万"、"0%"、"0分14秒"。
这里把它们转换成适合后续 AI 分析的干净数值：

  clean_int   "2,376"   -> 2376      "13.0万" -> 130000
  clean_float "0 元"    -> 0.0
  clean_rate  "4.0%"    -> 4.0
  clean_text  "  x  "   -> "x"（去空白，空串 -> None）

原则：取不到 / 解析不了 -> None，绝不编造 0 之类的假数据。
"""

import field_spec


def clean_text(raw):
    """字符串字段：去首尾空白，空串/None 返回 None。"""
    if raw is None:
        return None
    s = str(raw).strip()
    return s if s else None


def clean_int(raw):
    """整数：处理千分位逗号、中文「万」「亿」。解析失败返回 None。"""
    if raw is None:
        return None
    s = str(raw).strip().replace(",", "").replace("，", "")
    if not s:
        return None

    multiplier = 1
    if s.endswith("万"):
        multiplier = 10000
        s = s[:-1]
    elif s.endswith("亿"):
        multiplier = 100000000
        s = s[:-1]

    try:
        return int(float(s) * multiplier)
    except (ValueError, TypeError):
        return None


def clean_float(raw):
    """浮点数：去逗号、去「元」等多余字符。解析失败返回 None。"""
    if raw is None:
        return None
    s = str(raw).strip().replace(",", "").replace("，", "").replace("元", "")
    if not s:
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def clean_rate(raw):
    """百分比：去掉 % 转成浮点数（"4.0%" -> 4.0）。解析失败返回 None。"""
    if raw is None:
        return None
    s = str(raw).strip().replace("%", "").replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def clean_record(raw: dict) -> dict:
    """
    对一条记录做整体清洗，返回新 dict。
    依据 field_spec.DRAWER_FIELDS 里每个字段的 ctype 决定清洗方式；
    文本字段（title 等）统一走 clean_text。
    """
    cleaned = dict(raw)

    # 详情字段：按 ctype 清洗
    for field in field_spec.DRAWER_FIELDS:
        key = field["key"]
        ctype = field.get("ctype", "text")
        val = cleaned.get(key)

        if ctype == "int":
            cleaned[key] = clean_int(val)
        elif ctype == "float":
            cleaned[key] = clean_float(val)
        elif ctype == "rate":
            cleaned[key] = clean_rate(val)
        else:  # text
            cleaned[key] = clean_text(val)

    # 文本类基本字段：去空白
    for k in ("title", "publish_time", "article_id", "source_url",
              "collect_time", "collection_status", "error_message"):
        cleaned[k] = clean_text(cleaned.get(k))

    return cleaned

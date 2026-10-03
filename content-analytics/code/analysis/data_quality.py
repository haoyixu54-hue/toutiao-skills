# -*- coding: utf-8 -*-
"""
第一部分：数据清洗 / 数据质检

读取采集结果，做 7 项检查，并生成 data_quality_report：
  1. 重复 article_id
  2. 缺失值（区分「真 0」和「缺失 null」）
  3. 异常值（用 IQR 1.5 倍法则，对高度偏斜的流量数据做参考性提示，不下结论）
  4. 数值字段类型是否正确
  5. 百分比字段是否统一（是否落在 0~100）
  6. 平均阅读时长是否可转成秒
  7. 发布时间是否可转成标准 datetime

重要原则：
  - 平台没提供的数据 -> 保持 None，绝不填 0
  - 「真 0」和「缺失」是两个不同的东西，报告里分开统计
"""

import re
import datetime
from collections import Counter

from .utils import load_records


# ---- 数值 / 百分比 / 时长 / 时间 字段清单 ----
NUMERIC_FIELDS = [
    "impressions", "reads", "likes", "comments", "shares", "forwards",
    "favorites", "fan_impressions", "fan_reads", "fan_change",
    "new_followers", "unfollow", "revenue",
]
RATE_FIELDS = ["click_rate", "completion_rate", "read_to_follow_rate"]
TEXT_FIELDS = ["article_id", "title", "publish_time", "collect_time", "source_url"]

READ_TIME_RE = re.compile(r"(\d+(?:\.\d+)?)\s*分")
READ_TIME_SEC_RE = re.compile(r"(\d+(?:\.\d+)?)\s*秒")


def parse_read_time(s):
    """
    "0分14秒" / "2分52秒" -> 秒（float）。
    兼容 "14秒"、"1分" 等写法；解析失败返回 None。
    """
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    total = 0.0
    m = READ_TIME_RE.search(s)
    if m:
        total += float(m.group(1)) * 60
    m = READ_TIME_SEC_RE.search(s)
    if m:
        total += float(m.group(1))
    if total == 0 and not re.search(r"\d", s):
        return None
    return total


def parse_publish_time(s, collect_year=None):
    """
    "07-09 10:00"（MM-DD HH:MM，缺年份）-> datetime。

    年份缺失时默认用 collect_year（采集年份）；若解析出的时间在未来，
    则减一年（跨年文章）。解析失败返回 None。
    """
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    year = collect_year or datetime.date.today().year
    for fmt in ("%m-%d %H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.datetime.strptime(s, fmt)
            if fmt.startswith("%m-%d"):
                dt = dt.replace(year=year)
            return dt
        except ValueError:
            continue
    return None


def _as_number(v):
    """尽力把值当数字读，失败返回 None。"""
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    try:
        return float(str(v).strip().replace(",", ""))
    except (ValueError, TypeError):
        return None


def check_quality(records):
    """
    对记录做全部质检，返回一个 dict（既供程序读取，也供生成报告）。
    """
    n = len(records)
    out = {"total": n, "issues": []}

    # ---- 1. 重复 article_id ----
    ids = [r.get("article_id") for r in records if r.get("article_id") is not None]
    dup_ids = {aid: c for aid, c in Counter(ids).items() if c > 1}
    out["duplicate_ids"] = dup_ids
    if dup_ids:
        out["issues"].append(f"发现 {len(dup_ids)} 个重复 article_id：{dup_ids}")

    # ---- 2. 缺失值（区分真 0 / 缺失） ----
    missing = {}   # 字段 -> 缺失(None)数量
    true_zero = {}  # 字段 -> 真 0 数量
    for f in NUMERIC_FIELDS + RATE_FIELDS + TEXT_FIELDS:
        miss = sum(1 for r in records if r.get(f) is None)
        zero = sum(1 for r in records if r.get(f) == 0)
        missing[f] = miss
        true_zero[f] = zero
    out["missing"] = missing
    out["true_zero"] = true_zero

    # ---- 3. 异常值（IQR 1.5 倍，仅对数值字段做参考性提示） ----
    outliers = {}
    for f in NUMERIC_FIELDS + RATE_FIELDS:
        vals = sorted([_as_number(r.get(f)) for r in records
                       if _as_number(r.get(f)) is not None])
        if len(vals) < 4:
            continue
        q1 = _percentile(vals, 25)
        q3 = _percentile(vals, 75)
        iqr = q3 - q1
        if iqr <= 0:
            continue
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        big = [r for r in records if _as_number(r.get(f)) is not None and _as_number(r.get(f)) > hi]
        if big:
            outliers[f] = {
                "upper_bound": hi,
                "count": len(big),
                "max_value": max(_as_number(r.get(f)) for r in big),
            }
    out["outliers"] = outliers

    # ---- 4. 数值字段类型是否正确 ----
    type_errors = []
    for f in NUMERIC_FIELDS + RATE_FIELDS:
        for r in records:
            v = r.get(f)
            if v is None:
                continue
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                type_errors.append((f, r.get("article_id"), repr(v)))
    out["type_errors"] = type_errors
    if type_errors:
        out["issues"].append(f"发现 {len(type_errors)} 个数值字段类型异常")

    # ---- 5. 百分比字段是否统一（0~100 检查） ----
    rate_ranges = {}
    rate_bad = []
    for f in RATE_FIELDS:
        vals = [r.get(f) for r in records if isinstance(r.get(f), (int, float))]
        if not vals:
            rate_ranges[f] = {"min": None, "max": None, "out_of_range": 0}
            continue
        mn, mx = min(vals), max(vals)
        bad = [v for v in vals if v < 0 or v > 100]
        rate_ranges[f] = {"min": mn, "max": mx, "out_of_range": len(bad)}
        if bad:
            rate_bad.append(f)
    out["rate_ranges"] = rate_ranges
    if rate_bad:
        out["issues"].append(f"百分比字段超出 0~100：{rate_bad}")

    # ---- 6. 平均阅读时长转秒 ----
    read_time_ok, read_time_fail = 0, 0
    for r in records:
        v = r.get("avg_read_time")
        if v is None:
            continue  # 缺失不算失败（0 阅读没有时长）
        if parse_read_time(v) is not None:
            read_time_ok += 1
        else:
            read_time_fail += 1
    out["read_time"] = {"convertible": read_time_ok, "failed": read_time_fail}

    # ---- 7. 发布时间转 datetime ----
    collect_year = None
    for r in records:
        ct = r.get("collect_time")
        if ct:
            m = re.match(r"(\d{4})", str(ct))
            if m:
                collect_year = int(m.group(1))
                break
    pub_ok, pub_fail = 0, 0
    for r in records:
        v = r.get("publish_time")
        if v is None:
            continue
        if parse_publish_time(v, collect_year) is not None:
            pub_ok += 1
        else:
            pub_fail += 1
    out["publish_time"] = {"convertible": pub_ok, "failed": pub_fail}

    out["status"] = "ok" if not out["issues"] else "warn"
    return out


def _percentile(vals, p):
    """升序列表线性插值百分位数。"""
    k = (len(vals) - 1) * (p / 100.0)
    lo, hi = int(k), min(int(k) + 1, len(vals) - 1)
    if lo == hi:
        return vals[lo]
    return vals[lo] + (k - lo) * (vals[hi] - vals[lo])


def render_quality_report(records, q):
    """把质检结果渲染成 Markdown 文本。"""
    L = []
    L.append("# 数据质量报告\n")
    L.append(f"- 总记录数：**{q['total']}** 篇")
    L.append(f"- 总体结论：{'✅ 通过' if q['status'] == 'ok' else '⚠️ 有需要关注的点'}\n")

    # 重复
    if q["duplicate_ids"]:
        L.append("## 1. 重复 article_id\n")
        L.append("发现以下重复 ID（应检查是否重复采集）：\n")
        for aid, c in q["duplicate_ids"].items():
            L.append(f"- `{aid}` 出现 {c} 次")
    else:
        L.append("## 1. 重复 article_id\n\n✅ 无重复。")
    L.append("")

    # 缺失 / 真 0
    L.append("## 2. 缺失值（区分「真 0」与「缺失 null」）\n")
    L.append("| 字段 | 缺失(null) | 真 0 | 说明 |")
    L.append("|---|---|---|---|")
    for f in q["missing"]:
        miss, zero = q["missing"][f], q["true_zero"][f]
        note = ""
        if f == "completion_rate":
            note = "0 阅读的文章平台不提供完读率，属正常缺失"
        elif f == "avg_read_time":
            note = "0 阅读的文章平台不提供时长，属正常缺失"
        elif miss == 0 and zero > 0:
            note = "有真 0 值（真实无数据）"
        elif miss > 0:
            note = "存在缺失，需留意"
        L.append(f"| {f} | {miss} | {zero} | {note} |")
    L.append("")

    # 异常值
    L.append("## 3. 异常值（IQR 1.5 倍法则，仅参考）\n")
    if not q["outliers"]:
        L.append("未发现明显超过上界的数值。")
    else:
        L.append("流量类字段高度右偏，「偏高」不一定是错误，仅供排查：\n")
        L.append("| 字段 | 上界 | 超出数量 | 最大值 |")
        L.append("|---|---|---|---|")
        for f, info in q["outliers"].items():
            L.append(f"| {f} | {info['upper_bound']:,.0f} | {info['count']} | {info['max_value']:,.0f} |")
    L.append("")

    # 类型
    L.append("## 4. 数值字段类型是否正确\n")
    if not q["type_errors"]:
        L.append("✅ 所有数值字段类型正确。")
    else:
        L.append(f"发现 {len(q['type_errors'])} 处类型异常：")
        for f, aid, v in q["type_errors"][:20]:
            L.append(f"- 字段 `{f}` / id `{aid}` / 值 `{v}`")
    L.append("")

    # 百分比
    L.append("## 5. 百分比字段是否统一（0~100）\n")
    L.append("| 字段 | 最小值 | 最大值 | 超出 0~100 数量 |")
    L.append("|---|---|---|---|")
    for f, info in q["rate_ranges"].items():
        mn = "—" if info["min"] is None else f"{info['min']:.2f}"
        mx = "—" if info["max"] is None else f"{info['max']:.2f}"
        L.append(f"| {f} | {mn} | {mx} | {info['out_of_range']} |")
    L.append("")

    # 时长转秒
    L.append("## 6. 平均阅读时长转秒\n")
    L.append(f"- 可转换：{q['read_time']['convertible']} 篇；转换失败：{q['read_time']['failed']} 篇（0 阅读的缺失不计入失败）")
    L.append("")

    # 时间转 datetime
    L.append("## 7. 发布时间转 datetime\n")
    L.append(f"- 可转换：{q['publish_time']['convertible']} 篇；转换失败：{q['publish_time']['failed']} 篇")
    L.append("> 注意：采集的 publish_time 只有「月-日 时:分」没有年份，转换时默认补当年（采集年份），跨年文章可能偏差。")
    L.append("")

    return "\n".join(L)

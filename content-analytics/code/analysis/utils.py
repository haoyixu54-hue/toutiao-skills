# -*- coding: utf-8 -*-
"""
分析模块共享工具

这里只放「纯函数」小工具，被 analysis 里其它模块复用：
  - percentile    线性插值百分位数（不依赖 numpy/pandas，纯 Python）
  - fmt_num       数字千分位格式化
  - fmt_rate      百分比格式化
  - load_records  读取采集结果（支持 .xlsx / .json / .csv）
"""

import os
import json
import csv


def percentile(sorted_values, p):
    """
    线性插值百分位数。p 取值 0~100。

    sorted_values 必须是已排序的数值列表（升序）。
    返回 None 当列表为空或含 None。
    """
    vals = [v for v in sorted_values if v is not None]
    if not vals:
        return None
    k = (len(vals) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(vals) - 1)
    if lo == hi:
        return float(vals[lo])
    frac = k - lo
    return vals[lo] + frac * (vals[hi] - vals[lo])


def pct_rank(value, sorted_values):
    """
    某个数值在有序列表里的「百分位排名」（0~100）。
    用于综合表现时把不同量纲的指标归一化到同一尺度。
    value 为 None 时返回 None。
    """
    vals = [v for v in sorted_values if v is not None]
    if value is None or not vals:
        return None
    # 小于等于 value 的数量 / 总数
    le = sum(1 for v in vals if v <= value)
    return le / len(vals) * 100.0


def fmt_num(x, nd=None):
    """数字千分位格式化；None 返回 '—'。"""
    if x is None:
        return "—"
    if isinstance(x, float):
        if nd is not None:
            return f"{x:,.{nd}f}"
        return f"{x:,.2f}"
    return f"{x:,}"


def fmt_rate(x):
    """百分数格式化（数值已是 0~100 的百分比）。None 返回 '—'。"""
    if x is None:
        return "—"
    return f"{x:.1f}%"


def load_records(path):
    """
    读取采集结果文件，返回 list[dict]。

    支持 .xlsx（openpyxl）/ .json / .csv。
    统一约定：空单元格 / 空字符串 -> None（区别于真 0）。
    """
    path = os.path.abspath(path)
    ext = os.path.splitext(path)[1].lower()

    if ext == ".xlsx":
        from openpyxl import load_workbook
        wb = load_workbook(path, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(h).strip() if h is not None else "" for h in rows[0]]
        records = []
        for r in rows[1:]:
            rec = {}
            for h, v in zip(headers, r):
                # 空单元格 / 空字符串 -> None（保留「真 0」）
                if v is None or (isinstance(v, str) and v.strip() == ""):
                    rec[h] = None
                else:
                    rec[h] = v
            records.append(rec)
        return records

    if ext == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []

    if ext == ".csv":
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            records = []
            for row in reader:
                rec = {}
                for k, v in row.items():
                    if v is None or v.strip() == "":
                        rec[k] = None
                    else:
                        # 尝试还原数字类型（CSV 会丢失类型）
                        rec[k] = _coerce_number(v)
                records.append(rec)
            return records

    raise ValueError(f"不支持的文件类型：{ext}（只支持 .xlsx / .json / .csv）")


def _coerce_number(s):
    """把 CSV 里的字符串尝试还原为 int / float，失败则原样返回字符串。"""
    s = s.strip()
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s

# -*- coding: utf-8 -*-
"""
数据存储

把采集到的记录（list of dict）保存成：
  - JSON   （结构化，保留 null，方便程序/AI 读取）
  - CSV    （通用表格，方便快速查看）
  - Excel  （.xlsx，方便你手动检查）

所有文件统一用 UTF-8 编码，避免中文乱码。
"""

import json
import csv
import os

import field_spec


def save_json(rows, path):
    """保存 JSON。ensure_ascii=False 让中文正常显示。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    return path


def save_csv(rows, path, fieldnames=None):
    """保存 CSV。None 值写成空字符串。"""
    fieldnames = fieldnames or field_spec.FIELD_ORDER
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for rec in rows:
            # None -> 空字符串，避免写出 "None"
            row = {k: ("" if rec.get(k) is None else rec.get(k)) for k in fieldnames}
            writer.writerow(row)
    return path


def save_excel(rows, path, fieldnames=None):
    """保存 Excel（.xlsx）。None 值写成空单元格。"""
    fieldnames = fieldnames or field_spec.FIELD_ORDER
    os.makedirs(os.path.dirname(path), exist_ok=True)

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "作品数据"

    # 表头
    ws.append(fieldnames)
    # 数据行
    for rec in rows:
        ws.append([rec.get(k) for k in fieldnames])

    wb.save(path)
    return path


def save_all(rows, out_dir, prefix="result"):
    """
    一次性保存 JSON / CSV / Excel 三种格式。
    返回三个文件路径。
    """
    json_path = os.path.join(out_dir, f"{prefix}.json")
    csv_path = os.path.join(out_dir, f"{prefix}.csv")
    xlsx_path = os.path.join(out_dir, f"{prefix}.xlsx")
    save_json(rows, json_path)
    save_csv(rows, csv_path)
    save_excel(rows, xlsx_path)
    return json_path, csv_path, xlsx_path

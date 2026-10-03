# -*- coding: utf-8 -*-
"""
================================================================================
V0.2 第二阶段 —— 批量采集

流程：
  作品1 -> 查看数据 -> 采集 -> 关闭
  -> 作品2 -> 查看数据 -> 采集 -> 关闭
  -> ...（自动翻页，直到没有下一页或达到限制）

特性：
  - 单篇失败不影响整体（错误记录在该篇 error_message 里）
  - 不重复采集已采集过的文章（支持跨运行续传：重新运行会接着上次继续）
  - 支持翻页
  - 输出 JSON / CSV / Excel

运行方式（在 toutiao_tool 目录下）：
    python run_batch.py                 # 采集全部（自动翻页）
    python run_batch.py --limit 10      # 只采集 10 篇（用于测试）
    python run_batch.py --max-pages 2   # 最多翻 2 页
    python run_batch.py --fresh         # 忽略已有结果，重新采集
================================================================================
"""

import os
import sys
import json
import argparse

# 控制台 UTF-8，避免中文乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import field_spec
import paths
from collector.browser import start_browser, stop_browser, log
from collector.collector import collect_all
from data_cleaning.cleaning import clean_record
from data_storage.storage import save_all

# 默认输出目录：统一数据目录（采集输出 = 分析输入 = E:/toutiao_data）。
# 旧的 toutiao_tool/output/ 属于历史/测试路径，仍可通过 --output-dir 使用。
OUTPUT_DIR = paths.DATA_DIR
BATCH_JSON = os.path.join(OUTPUT_DIR, "batch_result.json")


def load_existing(path) -> list:
    """加载之前保存的采集结果（用于去重/续传）。"""
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def merge_records(existing, new) -> list:
    """按 article_id 去重合并，新数据覆盖旧数据。"""
    by_id = {}
    for r in existing:
        if r.get("article_id"):
            by_id[r["article_id"]] = r
    for r in new:
        if r.get("article_id"):
            by_id[r["article_id"]] = r
    return list(by_id.values())


def main():
    parser = argparse.ArgumentParser(description="今日头条作品数据批量采集")
    parser.add_argument("--limit", type=int, default=None, help="最多采集多少篇（默认全部）")
    parser.add_argument("--max-pages", type=int, default=None, help="最多翻几页（默认全部）")
    parser.add_argument("--fresh", action="store_true", help="忽略已有结果，重新采集")
    parser.add_argument("--output-dir", type=str, default=None, help="输出目录（默认脚本目录下的 output）")
    args = parser.parse_args()

    # 输出目录：默认统一数据目录（paths.DATA_DIR），可用 --output-dir 覆盖
    output_dir = args.output_dir or OUTPUT_DIR
    batch_json = os.path.join(output_dir, "batch_result.json")
    os.makedirs(output_dir, exist_ok=True)

    # 加载已有结果，构建去重集合（失败的不算已采集，下次会重试）
    existing = [] if args.fresh else load_existing(batch_json)
    seen_ids = {
        r["article_id"]
        for r in existing
        if r.get("article_id") and r.get("collection_status") in ("success", "partial")
    }
    log(f"已有结果 {len(existing)} 篇，其中可去重 {len(seen_ids)} 篇。")

    # 启动浏览器并批量采集
    p, context, page = start_browser()
    new_raw = []
    try:
        new_raw = collect_all(
            page,
            limit=args.limit,
            max_pages=args.max_pages,
            seen_ids=seen_ids,
            log=log,
        )
    finally:
        stop_browser(p, context)

    # 清洗本次新数据
    new_clean = [clean_record(r) for r in new_raw]

    # 合并并保存
    merged = merge_records(existing, new_clean)
    paths = save_all(merged, output_dir, prefix="batch_result")

    # 汇总
    status_count = {}
    for r in new_clean:
        st = r.get("collection_status") or "unknown"
        status_count[st] = status_count.get(st, 0) + 1

    log("=" * 60)
    log(f"本次新采集 {len(new_clean)} 篇，累计 {len(merged)} 篇。")
    log(f"状态统计：{status_count}")
    log("输出文件：")
    for path in paths:
        log(f"  {path}")
    log("=" * 60)


if __name__ == "__main__":
    main()

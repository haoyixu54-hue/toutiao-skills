# -*- coding: utf-8 -*-
"""
================================================================================
V0.2 第一阶段 —— 单篇采集测试

流程：
  1. 打开今日头条创作者后台（手动登录，登录状态可复用）
  2. 进入作品管理页面
  3. 找到第一篇文章
  4. 读取列表页基本信息（标题 / 发布时间）+ 列表快捷指标（展现/阅读/点赞/评论）
  5. 点击「查看数据」
  6. 采集详情抽屉里的所有字段
  7. 关闭抽屉
  8. 清洗数据，保存成 JSON / CSV / Excel，并打印结果供你核对

运行方式（在 toutiao_tool 目录下）：
    python run_single.py
================================================================================
"""

import os
import sys

# 让控制台输出统一用 UTF-8，避免中文乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import field_spec
from collector.browser import start_browser, stop_browser, log
from collector import list_page
from collector.collector import collect_one_article
from data_cleaning.cleaning import clean_record
from data_storage.storage import save_all

# 输出目录
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def print_result(record, quick):
    """把采集结果打印成易读的对照表。"""
    print("\n" + "=" * 60)
    print("采集结果（列表快捷指标 vs 详情抽屉）")
    print("=" * 60)

    # 基本信息
    print(f"  标题        : {record.get('title')}")
    print(f"  发布时间    : {record.get('publish_time')}")
    print(f"  article_id  : {record.get('article_id')}")
    print(f"  采集时间    : {record.get('collect_time')}")
    print(f"  采集状态    : {record.get('collection_status')}")
    if record.get("error_message"):
        print(f"  错误信息    : {record.get('error_message')}")

    # 交叉核对：列表页快捷指标 vs 抽屉
    print("\n  ── 交叉核对 ───────────────────────────")
    print(f"  展现：列表 {quick.get('展现')}  |  抽屉 {record.get('impressions')}")
    print(f"  阅读：列表 {quick.get('阅读')}  |  抽屉 {record.get('reads')}")
    print(f"  点赞：列表 {quick.get('点赞')}  |  抽屉 {record.get('likes')}")
    print(f"  评论：列表 {quick.get('评论')}  |  抽屉 {record.get('comments')}")

    # 详情字段
    print("\n  ── 详情抽屉字段 ───────────────────────")
    for field in field_spec.DRAWER_FIELDS:
        key = field["key"]
        label = field["label"]
        print(f"  {label:12s} ({key}) = {record.get(key)}")

    print("=" * 60)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    p, context, page = start_browser()
    try:
        # 找到文章卡片
        cards = list_page.get_article_cards(page)
        total = cards.count()
        log(f"页面共找到 {total} 篇文章。")

        if total == 0:
            log("没有找到任何文章，请确认列表页已加载。")
            return

        first_card = cards.first
        log("开始采集第一篇文章……")

        # 列表页快捷指标（用于交叉核对）
        quick = list_page.extract_card_quick(first_card)

        # 采集一篇（列表基本信息 + 详情抽屉）
        raw = collect_one_article(page, first_card)

        # 清洗
        record = clean_record(raw)

        # 保存
        paths = save_all([record], OUTPUT_DIR, prefix="single_article")

        # 打印结果
        print_result(record, quick)

        log("采集完成！输出文件：")
        for path in paths:
            log(f"  {path}")

    finally:
        stop_browser(p, context)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
采集编排

把「列表解析 + 详情抽屉解析」串起来，产出一条完整的文章记录。
单篇采集和批量采集都会复用这里的 collect_one_article()。
"""

import datetime
from . import list_page
from . import detail_page


def _empty_record() -> dict:
    """生成一条空白记录，包含所有输出字段，初始为 None。"""
    import field_spec
    rec = {key: None for key in field_spec.FIELD_ORDER}
    rec["collect_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rec["collection_status"] = "success"
    return rec


def collect_one_article(page, card) -> dict:
    """
    采集一篇文章的完整流程：
      基本信息（列表卡片）-> 打开详情 -> 采集详情字段 -> 关闭详情

    返回完整记录 dict（原始文本值，未清洗）。清洗交给 data_cleaning 模块。

    状态约定：
      "success"  —— 全部成功
      "partial"  —— 详情已打开，但部分字段采集出错
      "failed"   —— 详情都没打开成功（比如按钮找不到）
    """
    record = _empty_record()
    opened = False

    try:
        # 1. 列表页基本信息（标题 / 时间 / id / 原文链接）
        basic = list_page.extract_card_basic(card)
        record.update(basic)

        # 2. 打开详情抽屉
        detail_page.open_detail(page, card)
        opened = True

        # 3. 采集详情字段
        fields = detail_page.collect_detail_fields(page)
        record.update(fields)

    except Exception as e:
        record["collection_status"] = "partial" if opened else "failed"
        record["error_message"] = str(e)

    finally:
        # 4. 无论成功失败，都尝试关闭抽屉，避免影响下一篇
        try:
            detail_page.close_detail(page)
        except Exception:
            pass

    return record


def collect_all(page, limit=None, max_pages=None, seen_ids=None, log=print) -> list:
    """
    批量采集：逐篇「查看数据 -> 采集 -> 关闭」，自动翻页。

    参数：
      limit      最多采集多少篇（None = 不限）
      max_pages  最多翻几页（None = 不限，翻到没有下一页为止）
      seen_ids   已经采集过的 article_id 集合，用于去重（可跨运行续传）

    返回：本次运行新采集到的记录列表（原始值，未清洗）。
    保证：单篇失败不会中断整个流程，失败信息记录在该篇的 error_message 里。
    """
    seen_ids = seen_ids or set()
    results = []
    collected = 0  # 本次实际采集（非跳过）的数量
    page_num = 1

    while True:
        if max_pages is not None and page_num > max_pages:
            log(f"达到最大页数 {max_pages}，停止。")
            break

        cards = list_page.get_article_cards(page)
        n = cards.count()
        if n == 0:
            log("当前页没有文章，采集结束。")
            break

        log(f"===== 第 {page_num} 页，共 {n} 篇 =====")

        for i in range(n):
            # 每次重新获取卡片，避免 DOM 变化导致 locator 失效
            card = list_page.get_article_cards(page).nth(i)

            # 先读基本信息，用于去重判断和日志
            try:
                basic = list_page.extract_card_basic(card)
            except Exception as e:
                basic = {}
                log(f"  [{i+1}/{n}] 读取基本信息失败：{e}")

            aid = basic.get("article_id")
            if aid and aid in seen_ids:
                log(f"  [{i+1}/{n}] 跳过（已采集）：{basic.get('title') or aid}")
                continue

            title = basic.get("title") or aid or "未知"
            log(f"  [{i+1}/{n}] 采集中：{title}")
            record = collect_one_article(page, card)

            # 成功或部分成功都算「已采集」，下次跳过；彻底失败的下次重试
            if record.get("article_id") and record.get("collection_status") != "failed":
                seen_ids.add(record["article_id"])

            results.append(record)
            collected += 1

            st = record.get("collection_status")
            if st != "success":
                log(f"      状态={st}，错误={record.get('error_message')}")

            if limit is not None and collected >= limit:
                log(f"达到采集上限 {limit} 篇，停止。")
                return results

        # 翻页
        if not list_page.has_next_page(page):
            log("没有下一页，采集结束。")
            break
        list_page.go_next_page(page)
        page_num += 1

    return results

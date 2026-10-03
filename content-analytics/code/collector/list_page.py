# -*- coding: utf-8 -*-
"""
作品列表页解析

从「作品管理」列表页提取每篇文章卡片的信息。
（不点开详情，只读列表本身）
"""

import re


def get_article_cards(page):
    """返回作品列表中所有文章卡片（按页面顺序）。"""
    return page.locator(".article-card")


def extract_card_basic(card) -> dict:
    """
    从一张文章卡片里提取基本信息。
    返回 dict：title / publish_time / article_id / source_url
    其中 article_id 是从标题链接 href 里的 /item/xxx/ 解析出来的。
    """
    info = {"title": None, "publish_time": None, "article_id": None, "source_url": None}

    # 标题（a.title），href 里带文章 id 和原文链接
    title_el = card.locator("a.title")
    if title_el.count() > 0:
        info["title"] = title_el.first.inner_text().strip()
        href = title_el.first.get_attribute("href") or ""
        info["source_url"] = href
        m = re.search(r"/item/(\d+)", href)
        if m:
            info["article_id"] = m.group(1)

    # 发布时间（span.label.create-time）
    time_el = card.locator("span.label.create-time")
    if time_el.count() > 0:
        info["publish_time"] = time_el.first.inner_text().strip()

    return info


def extract_card_quick(card) -> dict:
    """
    从卡片读取列表页的 4 个快捷指标：展现 / 阅读 / 点赞 / 评论（纯文本，不转换）。
    用途：和详情抽屉里的数值做交叉核对。
    """
    quick = {"展现": None, "阅读": None, "点赞": None, "评论": None}
    lis = card.locator("ul.count li")
    for i in range(lis.count()):
        txt = lis.nth(i).inner_text().strip()
        # txt 形如 "展现  2376"、"阅读  1"
        for key in quick:
            if txt.startswith(key):
                quick[key] = txt[len(key):].strip()
                break
    return quick


# ----------------------------------------------------------------------
# 翻页（来自 DOM 侦察：翻页组件是 fake-pagination，上一页/下一页是图标 li）
# ----------------------------------------------------------------------

def _first_title(page):
    """取当前列表第一篇文章的标题（用于判断翻页后列表是否已更新）。"""
    a = page.locator(".article-card a.title").first
    if a.count() > 0:
        return a.inner_text().strip()
    return None


def has_next_page(page) -> bool:
    """
    是否还有下一页。
    下一页箭头是「最后一个」fake-pagination-item-icon，disabled 表示已经是最后一页。
    """
    nxt = page.locator(".content-pagination li.fake-pagination-item-icon").last
    if nxt.count() == 0:
        return False
    cls = nxt.get_attribute("class") or ""
    return "disabled" not in cls


def go_next_page(page, timeout=15000):
    """
    点击下一页，并等待列表更新完成（以第一篇文章标题变化为信号）。
    """
    old_title = _first_title(page)
    nxt = page.locator(".content-pagination li.fake-pagination-item-icon").last
    nxt.click()

    if old_title is not None:
        try:
            page.wait_for_function(
                "old => { const a = document.querySelector('.article-card a.title'); "
                "return a && a.textContent.trim() !== old; }",
                arg=old_title,
                timeout=timeout,
            )
        except Exception:
            page.wait_for_timeout(3000)
    else:
        page.wait_for_timeout(3000)
    # 等剩余卡片渲染稳定
    page.wait_for_timeout(1500)

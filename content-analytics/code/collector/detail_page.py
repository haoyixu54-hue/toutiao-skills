# -*- coding: utf-8 -*-
"""
数据详情抽屉（Drawer）解析

点「查看数据」后，右侧滑出的抽屉。这里负责：
  1. 打开抽屉并等待数据加载完成
  2. 按 field_spec.DRAWER_FIELDS 提取每个字段
  3. 关闭抽屉

字段提取的核心规律（来自 DOM 侦察）：
  标签文字在 .primary / .second / .inter-item 元素里，
  数值在它们内部的 <span class="num"> 里。
  对比信息（"超过 X% 同类作品"）在 .extra-data 里。
"""

import field_spec

# 抽屉 / 关键元素的选择器
DRAWER_SELECTOR = ".byte-drawer.single-data-drawer"
CLOSE_BUTTON_SELECTOR = ".byte-drawer-close-icon"
BOARD_GROUP_SELECTOR = ".single-data-board-group"


# ----------------------------------------------------------------------
# 打开 / 关闭
# ----------------------------------------------------------------------

def open_detail(page, card, timeout=15000):
    """
    点击某篇文章卡片上的「查看数据」，等待抽屉和数据加载完成。
    """
    btn = card.get_by_text("查看数据", exact=True).first
    btn.click()

    # 等待抽屉出现
    page.wait_for_selector(DRAWER_SELECTOR, state="visible", timeout=timeout)
    # 等待数据卡片区出现
    page.wait_for_selector(BOARD_GROUP_SELECTOR, state="visible", timeout=timeout)
    # 数据可能是异步请求回来的，多等一会儿再取
    page.wait_for_timeout(2000)


def close_detail(page):
    """点击关闭按钮，等待抽屉消失。"""
    close_btn = page.locator(CLOSE_BUTTON_SELECTOR)
    if close_btn.count() > 0:
        close_btn.first.click()
    try:
        page.locator(DRAWER_SELECTOR).wait_for(state="hidden", timeout=8000)
    except Exception:
        # 有些情况下抽屉直接从 DOM 移除，wait_for 会抛异常，忽略即可
        page.wait_for_timeout(2000)


# ----------------------------------------------------------------------
# 字段提取（底层工具函数，用 JS 在浏览器里执行，鲁棒性好）
# ----------------------------------------------------------------------

def _get_num_by_label(page, label):
    """
    在抽屉里按「中文标签」找字段，返回 .num 里的数值文本（找不到返回 None）。
    匹配规则：遍历 .primary / .second / .inter-item，取它们的第一个直接文本节点
    作为标签（排除掉 .num 里的数字），与传入的 label 精确比较。
    """
    return page.evaluate(
        """
        (label) => {
            const els = document.querySelectorAll(
                '.single-data-drawer .primary, ' +
                '.single-data-drawer .second, ' +
                '.single-data-drawer .inter-item'
            );
            for (const el of els) {
                // 结构固定是「标签 + 数值」，所以标签一定是元素文本的开头。
                // 用整个 textContent 判断，避免被空文本节点干扰。
                const text = (el.textContent || '').trim();
                if (text.startsWith(label)) {
                    const num = el.querySelector('.num');
                    return num ? num.textContent.trim() : null;
                }
            }
            return null;
        }
        """,
        label,
    )


def _get_read_time(page):
    """
    提取「平均阅读时长」。
    结构特殊：分钟和秒是两个独立的 .num（分在 .num，秒在 .time.num）。
    返回拼接结果，例如 "0分14秒"；取不到返回 None。
    """
    return page.evaluate(
        """
        () => {
            const els = document.querySelectorAll('.single-data-drawer .second');
            for (const el of els) {
                const text = (el.textContent || '').trim();
                if (text.startsWith('平均阅读时长')) {
                    const min = el.querySelector('.num');
                    const sec = el.querySelector('.time.num');
                    const m = min ? min.textContent.trim() : '';
                    const s = sec ? sec.textContent.trim() : '';
                    if (m === '' && s === '') return null;
                    return m + '分' + s + '秒';
                }
            }
            return null;
        }
        """
    )


def _get_fan_up_down(page):
    """
    提取「涨粉」「掉粉」。结构特殊：嵌套在 .fan-change .up / .down 里。
    返回 (涨粉文本, 掉粉文本)。
    """
    return page.evaluate(
        """
        () => {
            const up = document.querySelector('.single-data-drawer .fan-change .up .num');
            const down = document.querySelector('.single-data-drawer .fan-change .down .num');
            return {
                up: up ? up.textContent.trim() : null,
                down: down ? down.textContent.trim() : null,
            };
        }
        """
    )


def _get_extra_by_label(page, label):
    """
    提取对比信息（"超过 X% 同类作品"）。
    先按标签找到 .primary / .second 元素，再取其所在 .item 里的 .extra-data。
    """
    return page.evaluate(
        """
        (label) => {
            const els = document.querySelectorAll(
                '.single-data-drawer .primary, .single-data-drawer .second'
            );
            for (const el of els) {
                const text = (el.textContent || '').trim();
                if (text.startsWith(label)) {
                    const item = el.closest('.item');
                    const extra = item ? item.querySelector('.extra-data') : null;
                    return extra ? extra.textContent.trim() : null;
                }
            }
            return null;
        }
        """,
        label,
    )


# ----------------------------------------------------------------------
# 汇总采集
# ----------------------------------------------------------------------

def collect_detail_fields(page) -> dict:
    """
    按 field_spec.DRAWER_FIELDS 逐字段采集，返回 {key: 原始文本或 None}。
    某个字段不存在/取不到时，值为 None（不编造数据）。
    """
    result = {}

    # 涨粉/掉粉只算一次（两个字段共用一个 DOM 查询结果）
    up_down_cache = None

    for field in field_spec.DRAWER_FIELDS:
        key = field["key"]
        label = field["label"]
        kind = field["kind"]

        try:
            if kind == "num":
                result[key] = _get_num_by_label(page, label)
            elif kind == "read_time":
                result[key] = _get_read_time(page)
            elif kind in ("up", "down"):
                if up_down_cache is None:
                    up_down_cache = _get_fan_up_down(page)
                result[key] = up_down_cache["up"] if kind == "up" else up_down_cache["down"]
            elif kind == "extra":
                result[key] = _get_extra_by_label(page, label)
            else:
                result[key] = None
        except Exception:
            # 单个字段失败不影响整体，记 None
            result[key] = None

    return result

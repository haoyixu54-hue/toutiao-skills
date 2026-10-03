# -*- coding: utf-8 -*-
"""
================================================================================
今日头条创作者后台 —— DOM 侦察脚本（第一步）

作用（只做侦察，不采集正式数据）：
    1. 打开「作品管理」页面
    2. 如果未登录，等待你在弹出的浏览器窗口里手动登录（扫码 / 手机验证码）
    3. 分析作品列表的 DOM 结构（标题、发布时间、「查看数据」按钮）
    4. 点击第一篇文章的「查看数据」按钮
    5. 把数据详情弹窗的 DOM 结构导出来

产出的文件（都在 dump 目录里）：
    1_list_page.html        作品列表页的完整 HTML（用于分析列表结构）
    2_first_card_analysis.txt 第一篇文章卡片的结构分析
    3_after_click.html       点击「查看数据」后的完整 HTML（用于分析弹窗结构）
    4_modal_text.txt         弹窗里的可见文字（用于确认采集到了哪些字段）

为什么要这样做：
    今日头条后台是 React 单页应用，class 名是动态生成的，直接猜选择器很容易猜错。
    所以第一步先「导出真实的 DOM」，看清楚结构之后，再写稳定的选择器。
================================================================================
"""

import os
import sys
from playwright.sync_api import sync_playwright

# 让控制台输出统一使用 UTF-8，避免中文乱码（尤其在被重定向/捕获时）
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ============================ 配置区 ============================

# 作品管理页面地址
TARGET_URL = "https://mp.toutiao.com/profile_v4/manage/content/all"

# 浏览器登录状态保存目录。
# 使用「持久化浏览器上下文」：你登录一次后，登录状态会保存下来，下次运行免登录。
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profile")

# DOM 导出目录
DUMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dump")

# 等待手动登录的最长时间（秒）。给足时间扫码 / 输验证码。
LOGIN_TIMEOUT = 1800

# 系统 Chrome 的路径（用你电脑里已装好的 Chrome，省去下载 Chromium）
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def log(msg: str):
    """带时间戳的打印，方便看进度。flush=True 让日志实时输出。"""
    import datetime
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def is_logged_in(page) -> bool:
    """
    判断当前是否已经登录并成功进入作品列表页。

    判断逻辑：
      1. 如果网址里出现 login / auth / sso，说明被重定向到登录页了 -> 未登录
      2. 如果页面上能找到「查看数据」按钮，说明列表已经加载出来 -> 已登录
    """
    url = page.url
    if any(k in url for k in ("login", "auth", "sso")):
        return False
    try:
        # 「查看数据」是每篇文章都有的按钮，出现它 = 列表加载成功
        if page.get_by_text("查看数据").count() > 0:
            return True
    except Exception:
        pass
    return False


def wait_until_logged_in(page):
    """
    轮询等待用户手动登录完成。
    每 2 秒检查一次，直到检测到已登录（作品列表出现）。
    """
    log("等待登录中……（请在弹出的 Chrome 窗口里扫码或输验证码登录）")
    waited = 0
    while waited < LOGIN_TIMEOUT:
        if is_logged_in(page):
            return
        page.wait_for_timeout(2000)
        waited += 2
        # 每 60 秒提醒一次，避免你以为程序卡住了
        if waited % 60 == 0:
            log(f"  仍在等待登录…… 已等待 {waited} 秒（超时上限 {LOGIN_TIMEOUT} 秒）")
    log(f"等待登录超时（超过 {LOGIN_TIMEOUT} 秒），程序退出。")
    sys.exit(1)


def save_html(page, filename: str):
    """把当前页面完整 HTML 保存到 dump 目录，返回文件路径。"""
    path = os.path.join(DUMP_DIR, filename)
    html = page.content()
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    size_kb = len(html) / 1024
    log(f"  已保存 HTML：{filename}（{size_kb:.0f} KB）")
    return path


def analyze_list(page, fout):
    """
    分析作品列表：统计「查看数据」按钮数量，并解剖第一篇文章卡片的 DOM 结构。
    结构信息写入 fout（analysis 文件），同时打印到控制台。
    """
    fout.write("=" * 70 + "\n")
    fout.write("第一部分：作品列表结构分析\n")
    fout.write("=" * 70 + "\n\n")

    # 1. 统计「查看数据」按钮数量（约等于文章数量）
    buttons = page.get_by_text("查看数据")
    count = buttons.count()
    log(f"  找到「查看数据」按钮 {count} 个（约等于文章数量）")
    fout.write(f"「查看数据」按钮数量：{count}\n\n")

    if count == 0:
        fout.write("（没找到任何「查看数据」按钮，可能列表还在加载或页面结构有变）\n")
        return None

    # 2. 取第一个按钮，向上逐层解剖它的祖先元素
    first_btn = buttons.first
    fout.write("第一个「查看数据」按钮的 HTML：\n")
    fout.write("-" * 70 + "\n")
    fout.write(_outer_html(first_btn, limit=2000) + "\n\n")

    # 逐层向上打印祖先元素（最多 6 层），帮助我们看清卡片层级
    fout.write("向上逐层看祖先元素（tag.class）：\n")
    fout.write("-" * 70 + "\n")
    node = first_btn
    for level in range(1, 7):
        try:
            # 用 JS 取父元素，避免 Playwright 的 element handle 越界问题
            parent = node.evaluate_handle("el => el.parentElement")
            if parent is None or parent.as_element() is None:
                break
            el = parent.as_element()
            tag = el.evaluate("el => el.tagName.toLowerCase()")
            cls = el.evaluate("el => el.className")
            # className 可能是 SVGAnimatedString 等，统一转成 str 处理
            if not isinstance(cls, str):
                cls = getattr(cls, "baseVal", str(cls))
            cls = str(cls)[:120]
            fout.write(f"  第 {level} 层祖先: <{tag} class='{cls}'>\n")
            node = el
        except Exception as e:
            fout.write(f"  第 {level} 层祖先: 读取失败 ({e})\n")
            break
    fout.write("\n")

    # 3. 把「往上第 3 层」的祖先 HTML 也导出来（通常这一层就是整篇文章卡片）
    fout.write("第一篇文章卡片（推测，往上第 3 层祖先）的 HTML：\n")
    fout.write("-" * 70 + "\n")
    try:
        card = first_btn
        for _ in range(3):
            card = card.evaluate_handle("el => el.parentElement").as_element()
            if card is None:
                break
        if card is not None:
            fout.write(_outer_html(card, limit=6000) + "\n")
        else:
            fout.write("（未能定位到第 3 层祖先）\n")
    except Exception as e:
        fout.write(f"（定位卡片失败：{e}）\n")
    fout.write("\n")

    return first_btn


def analyze_modal(page, fout):
    """
    点击「查看数据」之后，分析弹窗结构。
    把弹窗可见文字写入 fout，并尝试识别弹窗容器。
    """
    fout.write("\n" + "=" * 70 + "\n")
    fout.write("第二部分：数据详情弹窗结构分析\n")
    fout.write("=" * 70 + "\n\n")

    # 等待弹窗加载（数据可能是异步请求回来的，多等几秒）
    page.wait_for_timeout(5000)

    # 导出点击后的完整 HTML
    save_html(page, "3_after_click.html")

    # 尝试用常见选择器找到弹窗容器（写文件里，供后续参考）
    fout.write("尝试用常见选择器定位弹窗容器（命中数量）：\n")
    fout.write("-" * 70 + "\n")
    candidate_selectors = [
        '[role="dialog"]',
        '[class*="dialog"]',
        '[class*="Dialog"]',
        '[class*="modal"]',
        '[class*="Modal"]',
        '[class*="drawer"]',
        '[class*="Drawer"]',
        '[class*="popup"]',
        '[class*="Popup"]',
        '[class*="layer"]',
        '[class*="Layer"]',
        '[class*="mask"]',
    ]
    for sel in candidate_selectors:
        try:
            n = page.locator(sel).count()
            fout.write(f"  {sel:30s} -> {n} 个\n")
        except Exception as e:
            fout.write(f"  {sel:30s} -> 报错 {e}\n")
    fout.write("\n")

    # 把弹窗（或整个页面）的可见文字抓出来，确认采集到了哪些字段
    body_text = page.inner_text("body")
    fout.write("点击「查看数据」后页面可见文字：\n")
    fout.write("-" * 70 + "\n")
    fout.write(body_text + "\n")

    # 同时单独存一份弹窗文字，方便快速查看
    text_path = os.path.join(DUMP_DIR, "4_modal_text.txt")
    with open(text_path, "w", encoding="utf-8") as tf:
        tf.write(body_text)
    log(f"  已保存弹窗文字：4_modal_text.txt（{len(body_text)} 字符）")
    return body_text


def _outer_html(locator, limit: int) -> str:
    """取某个元素的 outerHTML，截断到 limit 长度，方便阅读。"""
    try:
        html = locator.evaluate("el => el.outerHTML")
    except Exception as e:
        return f"（读取失败：{e}）"
    if len(html) > limit:
        html = html[:limit] + "\n……（已截断，完整内容见 1_list_page.html）"
    return html


def main():
    os.makedirs(DUMP_DIR, exist_ok=True)

    # analysis 文件：记录所有结构分析结果（纯文本，便于阅读）
    analysis_path = os.path.join(DUMP_DIR, "2_first_card_analysis.txt")
    fout = open(analysis_path, "w", encoding="utf-8")

    try:
        with sync_playwright() as p:
            # ---- 启动浏览器（持久化上下文 + 系统 Chrome）----
            log("正在启动 Chrome……")
            context = p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,   # 保存登录状态
                channel="chrome",            # 使用系统 Chrome（等价于指定 executable_path）
                headless=False,              # 必须显示窗口，方便你手动登录
                viewport={"width": 1440, "height": 900},
                args=["--start-maximized"],
            )
            page = context.new_page()

            # ---- 打开目标页面 ----
            log("正在打开作品管理页面……")
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            # ---- 登录检测 ----
            if is_logged_in(page):
                log("检测到已登录，跳过登录步骤。")
            else:
                log("检测到未登录。请在弹出的 Chrome 窗口里手动登录。")
                wait_until_logged_in(page)
                log("登录成功！开始分析页面。")

            # 等列表稳定
            page.wait_for_timeout(3000)

            # ---- 保存列表页完整 HTML ----
            log("开始导出作品列表 DOM ……")
            save_html(page, "1_list_page.html")

            # ---- 分析列表结构 ----
            first_btn = analyze_list(page, fout)

            # ---- 点击第一篇文章的「查看数据」----
            if first_btn is not None:
                log("点击第一篇文章的「查看数据」按钮……")
                try:
                    first_btn.click()
                except Exception as e:
                    log(f"  普通点击失败（{e}），改用 JS 强制点击……")
                    first_btn.evaluate("el => el.click()")

                # ---- 分析弹窗结构 ----
                analyze_modal(page, fout)
            else:
                fout.write("（未找到「查看数据」按钮，跳过弹窗分析）\n")
                log("未找到「查看数据」按钮，无法点击。")

            # ---- 关闭浏览器 ----
            context.close()

    finally:
        fout.close()

    # 输出提示
    log("=" * 60)
    log("侦察完成！请查看 dump 目录下的文件：")
    log("  1_list_page.html        作品列表完整 HTML")
    log("  2_first_card_analysis.txt 第一篇文章卡片结构分析")
    log("  3_after_click.html       点击「查看数据」后的完整 HTML")
    log("  4_modal_text.txt         弹窗可见文字")
    log("下一步：把这些文件发给 Claude，让它据此设计稳定的选择器。")
    log("=" * 60)


if __name__ == "__main__":
    main()

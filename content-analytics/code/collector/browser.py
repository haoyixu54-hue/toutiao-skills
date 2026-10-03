# -*- coding: utf-8 -*-
"""
浏览器启动 + 登录检测

职责：
  1. 用「持久化浏览器上下文」启动系统 Chrome（登录状态保存在 browser_profile 目录，免重复登录）
  2. 打开作品管理页面
  3. 如果未登录，等待用户手动登录（扫码 / 手机验证码）
"""

import os
import sys
import datetime
from playwright.sync_api import sync_playwright

# 作品管理页面地址
TARGET_URL = "https://mp.toutiao.com/profile_v4/manage/content/all"

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 浏览器登录状态保存目录
PROFILE_DIR = os.path.join(BASE_DIR, "browser_profile")

# 等待手动登录的最长时间（秒）
LOGIN_TIMEOUT = 1800


def log(msg: str):
    """带时间戳的打印。"""
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def _is_logged_in(page) -> bool:
    """
    判断当前是否已登录并成功进入作品列表页。
    1. 网址里出现 login / auth / sso -> 被重定向到登录页，视为未登录
    2. 页面上能找到「查看数据」按钮 -> 列表已加载，视为已登录
    """
    url = page.url
    if any(k in url for k in ("login", "auth", "sso")):
        return False
    try:
        if page.get_by_text("查看数据").count() > 0:
            return True
    except Exception:
        pass
    return False


def _wait_until_logged_in(page):
    """轮询等待用户手动登录完成，每 2 秒检查一次。"""
    log("等待登录中……（请在弹出的 Chrome 窗口里扫码或输验证码登录）")
    waited = 0
    while waited < LOGIN_TIMEOUT:
        if _is_logged_in(page):
            return
        page.wait_for_timeout(2000)
        waited += 2
        if waited % 60 == 0:
            log(f"  仍在等待登录…… 已等待 {waited} 秒")
    log(f"等待登录超时（超过 {LOGIN_TIMEOUT} 秒），程序退出。")
    sys.exit(1)


def start_browser():
    """
    启动浏览器并返回 (playwright, context, page)。
    调用方负责在结束时调用 stop_browser()。
    """
    p = sync_playwright().start()

    log("正在启动 Chrome……")
    context = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,  # 保存登录状态
        channel="chrome",           # 使用系统已安装的 Chrome（省去下载 Chromium）
        headless=False,             # 必须显示窗口，方便手动登录
        viewport={"width": 1440, "height": 900},
        args=["--start-maximized"],
    )
    page = context.new_page()

    log("正在打开作品管理页面……")
    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)

    if _is_logged_in(page):
        log("检测到已登录，跳过登录步骤。")
    else:
        log("检测到未登录。请在弹出的 Chrome 窗口里手动登录。")
        _wait_until_logged_in(page)
        log("登录成功！")

    # 等列表稳定
    page.wait_for_timeout(3000)
    return p, context, page


def stop_browser(p, context):
    """关闭浏览器并释放资源。"""
    try:
        context.close()
    except Exception:
        pass
    try:
        p.stop()
    except Exception:
        pass

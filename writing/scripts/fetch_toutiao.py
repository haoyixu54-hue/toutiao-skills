"""抓取今日头条文章内容（需要JS渲染，使用系统Edge浏览器）"""
import sys, json, time, os, io
from pathlib import Path
from playwright.sync_api import sync_playwright

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Output path: skill output dir
SKILL_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = SKILL_DIR / "output" / "toutiao_article.json"

def fetch(url: str, channel: str = "msedge") -> dict:
    """
    Fetch Toutiao article using system Edge browser (no extra install needed).
    Falls back to chrome if Edge unavailable.
    """
    with sync_playwright() as p:
        # Try Edge first (Windows自带), then Chrome, then default
        browser = None
        for ch in [channel, "chrome", None]:
            try:
                if ch:
                    browser = p.chromium.launch(channel=ch, headless=True)
                else:
                    browser = p.chromium.launch(headless=True)
                break
            except Exception:
                continue

        if browser is None:
            raise RuntimeError(
                "No browser found. Install Edge or Chrome, or run: playwright install chromium"
            )

        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(3)

        title = page.title() or ""

        # Try multiple selectors for article body
        body_text = ""
        selectors = [
            "article",
            "[class*='article-content']",
            ".article-content",
            ".content",
            "[class*='detail']",
        ]
        for sel in selectors:
            try:
                els = page.locator(sel).all()
                for el in els:
                    txt = el.inner_text()
                    if len(txt) > len(body_text):
                        body_text = txt
            except Exception:
                continue

        if not body_text:
            body_text = page.inner_text("body")

        browser.close()

    return {
        "title": title.replace(" - 今日头条", "").strip(),
        "content": body_text,
        "url": url,
    }


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else input("请输入头条文章链接: ")
    print(f"Fetching: {url}")
    result = fetch(url)

    # Save JSON
    os.makedirs(OUTPUT_PATH.parent, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Saved: {OUTPUT_PATH}")
    print(f"Title: {result['title']}")
    print(f"Content: {len(result['content'])} chars")
    print("=" * 60)
    print(result["content"][:3000])
    if len(result["content"]) > 3000:
        print(f"\n... (全文共 {len(result['content'])} 字符，已截断)")

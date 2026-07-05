"""Browser-assisted content filling for Source2Launch.

Opens a real browser, navigates to the platform's posting page,
and fills in the promotional content automatically — simulating
human-like typing. The user only needs to review and click "Publish".

Requirements: pip install playwright && playwright install chromium

Supported platforms:
  xhs / xiaohongshu  - 小红书创作者平台
  zhihu              - 知乎写文章
  wechat             - 微信公众号草稿箱
  twitter            - Twitter/X 发推
  linkedin           - LinkedIn 发文

Usage:
    source2launch fill xhs
    source2launch fill zhihu --assets-dir ./launch-assets
    source2launch fill twitter --content "直接传入内容"
"""
from __future__ import annotations

import os
import random
import sys
import time
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Playwright availability check
# ---------------------------------------------------------------------------

def _require_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        print(
            "source2launch: browser filling requires Playwright.\n"
            "Install it with:\n"
            "  pip install playwright\n"
            "  playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Human-like typing helper
# ---------------------------------------------------------------------------

def _human_type(page, selector: str, text: str, delay_ms: tuple = (30, 80)) -> None:
    """Type text into an element character by character with random delays."""
    el = page.locator(selector).first
    el.click()
    for char in text:
        el.type(char)
        time.sleep(random.uniform(delay_ms[0], delay_ms[1]) / 1000)


def _fill_rich_editor(page, selector: str, text: str) -> None:
    """Fill a rich-text editor (Quill, Draft.js, Slate, etc.) with content."""
    el = page.locator(selector).first
    el.click()
    # Try to clear first
    page.keyboard.press("Control+A")
    page.keyboard.press("Delete")
    time.sleep(0.3)
    # Paste content (faster than typing)
    page.evaluate(
        """(args) => {
            const [sel, txt] = args;
            const el = document.querySelector(sel);
            if (el) {
                // Try execCommand paste
                const event = new InputEvent('beforeinput', {inputType: 'insertText', data: txt, bubbles: true});
                el.dispatchEvent(event);
            }
        }""",
        [selector, text],
    )
    # Fallback: use clipboard paste
    try:
        page.evaluate(f"navigator.clipboard.writeText({text!r})")
        el.press("Control+V")
    except Exception:  # noqa: BLE001
        # If clipboard not available, type slowly
        for line in text.split("\n"):
            el.type(line)
            page.keyboard.press("Enter")
    time.sleep(0.5)


# ---------------------------------------------------------------------------
# Platform-specific fillers
# ---------------------------------------------------------------------------

class XiaohongshuFiller:
    """小红书创作者平台 — 自动填写标题、正文和标签。"""
    name = "小红书"
    url = "https://creator.xiaohongshu.com/creator/post"
    persist_dir = ".s2l-browser/xhs"

    def fill(self, page, content: str, title: str = "", tags: list[str] | None = None) -> None:
        # Parse content for title/body/tags if not provided separately
        lines = content.strip().split("\n")
        if not title and lines:
            # Use first non-empty line as title (strip markdown #)
            title = lines[0].lstrip("#").strip()[:50]
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else content

        print("  填写标题…", file=sys.stderr)
        try:
            title_sel = 'input[placeholder*="标题"], .title-input, #title'
            page.locator(title_sel).first.fill(title)
        except Exception:  # noqa: BLE001
            print("  ⚠ 未找到标题输入框，请手动填写", file=sys.stderr)

        print("  填写正文…", file=sys.stderr)
        time.sleep(0.5)
        try:
            # XHS uses a rich text editor (similar to Quill)
            editor_sel = '.ql-editor, [contenteditable=true], .note-editor'
            _fill_rich_editor(page, editor_sel, body)
        except Exception:  # noqa: BLE001
            print("  ⚠ 未找到正文编辑器，请手动填写", file=sys.stderr)

        # Fill tags
        if tags:
            print("  填写标签…", file=sys.stderr)
            time.sleep(0.3)
            for tag in tags[:5]:
                try:
                    tag_input = page.locator('input[placeholder*="标签"], .tag-input').first
                    tag_input.fill(f"#{tag.lstrip('#')}")
                    page.keyboard.press("Enter")
                    time.sleep(0.2)
                except Exception:  # noqa: BLE001
                    break


class ZhihuFiller:
    """知乎 — 自动填写文章标题和正文。"""
    name = "知乎"
    url = "https://www.zhihu.com/write"
    persist_dir = ".s2l-browser/zhihu"

    def fill(self, page, content: str, title: str = "", **kwargs) -> None:
        lines = content.strip().split("\n")
        if not title and lines:
            title = lines[0].lstrip("#").strip()[:100]
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else content

        print("  填写标题…", file=sys.stderr)
        try:
            title_sel = 'input[placeholder*="标题"], .QuestionInput, h1[contenteditable]'
            page.locator(title_sel).first.fill(title)
        except Exception:  # noqa: BLE001
            print("  ⚠ 未找到标题输入框，请手动填写", file=sys.stderr)

        print("  填写正文…", file=sys.stderr)
        time.sleep(0.5)
        try:
            editor_sel = '.DraftEditor-root, .ql-editor, [contenteditable=true]'
            _fill_rich_editor(page, editor_sel, body)
        except Exception:  # noqa: BLE001
            print("  ⚠ 未找到正文编辑器，请手动填写", file=sys.stderr)


class WechatOfficialFiller:
    """微信公众号 — 新建草稿并填写内容。"""
    name = "微信公众号"
    url = "https://mp.weixin.qq.com/"
    persist_dir = ".s2l-browser/wechat"

    def fill(self, page, content: str, title: str = "", **kwargs) -> None:
        lines = content.strip().split("\n")
        if not title and lines:
            title = lines[0].lstrip("#").strip()[:64]
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else content

        # Try to open new article editor
        print("  导航到新建文章…", file=sys.stderr)
        try:
            # Click "写文章" or similar button
            write_btn = page.locator('a:has-text("写文章"), button:has-text("写文章"), .new-article').first
            write_btn.click()
            time.sleep(2)
        except Exception:  # noqa: BLE001
            print("  ⚠ 未找到「写文章」按钮，请手动导航", file=sys.stderr)

        print("  填写标题…", file=sys.stderr)
        try:
            title_sel = '#title, input[id="title"], [placeholder*="标题"]'
            page.locator(title_sel).first.fill(title)
        except Exception:  # noqa: BLE001
            print("  ⚠ 未找到标题输入框，请手动填写", file=sys.stderr)

        print("  填写正文…", file=sys.stderr)
        time.sleep(0.5)
        try:
            editor_sel = '#js_content, .rich_media_content, [contenteditable=true]'
            _fill_rich_editor(page, editor_sel, body)
        except Exception:  # noqa: BLE001
            print("  ⚠ 未找到正文编辑器，请手动填写", file=sys.stderr)


class TwitterBrowserFiller:
    """Twitter/X — 打开发推页面并填写内容。"""
    name = "Twitter / X"
    url = "https://x.com/compose/tweet"
    persist_dir = ".s2l-browser/twitter"

    def fill(self, page, content: str, **kwargs) -> None:
        text = content[:280]
        print("  填写推文…", file=sys.stderr)
        time.sleep(1)
        try:
            editor_sel = '[data-testid="tweetTextarea_0"], .DraftEditor-root, [contenteditable=true]'
            el = page.locator(editor_sel).first
            el.click()
            el.type(text)
        except Exception:  # noqa: BLE001
            print("  ⚠ 未找到推文输入框，请手动填写", file=sys.stderr)


class LinkedInBrowserFiller:
    """LinkedIn — 打开发帖页面并填写内容。"""
    name = "LinkedIn"
    url = "https://www.linkedin.com/feed/"
    persist_dir = ".s2l-browser/linkedin"

    def fill(self, page, content: str, **kwargs) -> None:
        print("  点击「开始发帖」…", file=sys.stderr)
        time.sleep(1)
        try:
            # Click the "Start a post" button
            start_btn = page.locator('button:has-text("开始发帖"), button:has-text("Start a post"), '
                                     '[data-control-name="share.start"]').first
            start_btn.click()
            time.sleep(1)
        except Exception:  # noqa: BLE001
            print("  ⚠ 未找到「开始发帖」按钮，请手动点击", file=sys.stderr)

        print("  填写内容…", file=sys.stderr)
        time.sleep(0.5)
        try:
            editor_sel = '.ql-editor, [contenteditable=true], .share-creation-state__text-editor'
            el = page.locator(editor_sel).first
            el.click()
            el.type(content[:3000])
        except Exception:  # noqa: BLE001
            print("  ⚠ 未找到内容输入框，请手动填写", file=sys.stderr)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_FILLERS: dict[str, type] = {
    "xhs":           XiaohongshuFiller,
    "xiaohongshu":   XiaohongshuFiller,
    "zhihu":         ZhihuFiller,
    "wechat":        WechatOfficialFiller,
    "twitter":       TwitterBrowserFiller,
    "x":             TwitterBrowserFiller,
    "linkedin":      LinkedInBrowserFiller,
}


# ---------------------------------------------------------------------------
# Main fill function
# ---------------------------------------------------------------------------

def fill_platform(
    platform: str,
    content: str,
    *,
    title: str = "",
    tags: list[str] | None = None,
    headless: bool = False,
    pause_message: str = "",
) -> None:
    """Open a browser, navigate to the platform, fill content, then pause for user."""
    _require_playwright()
    from playwright.sync_api import sync_playwright

    filler_cls = _FILLERS.get(platform.lower())
    if not filler_cls:
        print(f"source2launch: unsupported platform '{platform}'", file=sys.stderr)
        print(f"Supported: {', '.join(sorted(set(_FILLERS.values()), key=lambda c: c.name))}", file=sys.stderr)
        return

    filler = filler_cls()

    # Persistent browser context — saves login cookies between sessions
    user_data_dir = Path(filler.persist_dir).resolve()
    user_data_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🌐 打开 {filler.name}…", file=sys.stderr)
    print(f"   如果需要登录，请在浏览器中登录后等待。", file=sys.stderr)

    with sync_playwright() as pw:
        browser = pw.chromium.launch_persistent_context(
            str(user_data_dir),
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_https_errors=True,
        )
        page = browser.new_page() if not browser.pages else browser.pages[0]

        # Navigate
        page.goto(filler.url, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(2)

        # Check if login is needed
        current_url = page.url
        login_indicators = ["login", "signin", "passport", "auth", "sso"]
        if any(ind in current_url.lower() for ind in login_indicators):
            print(f"\n  ⚠ 需要登录 — 请在浏览器中完成登录，然后按回车继续…", file=sys.stderr)
            input()
            page.goto(filler.url, wait_until="domcontentloaded", timeout=30_000)
            time.sleep(2)

        # Fill content
        print(f"\n✍  自动填写内容中…", file=sys.stderr)
        filler.fill(page, content, title=title, tags=tags)

        # Pause for user review
        msg = pause_message or (
            f"\n✅ 内容已填写完成！\n"
            f"   请在浏览器中检查内容，然后点击「发布」按钮。\n"
            f"   完成后按回车关闭浏览器。"
        )
        print(msg, file=sys.stderr)
        input()

        browser.close()
    print("✓ 浏览器已关闭", file=sys.stderr)


def list_supported_platforms() -> list[str]:
    seen = set()
    result = []
    for cls in _FILLERS.values():
        if cls not in seen:
            seen.add(cls)
            result.append(cls.name)
    return result

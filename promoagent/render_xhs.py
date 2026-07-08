"""Render Xiaohongshu (小红书) card images from produce output.

Turns the ``{title, markdown, hashtags, ...}`` dict produced by the pipeline
into a set of 1080×1440 (3:4) PNG cards: a cover, one or more body pages, and
an optional CTA page. Rendering is HTML/CSS + Playwright screenshot — a
deterministic, styleable alternative to AI image generation for text-heavy
note cards (where the cover image carries the post's hook, not a photo).

The split strategy is the only non-trivial logic: markdown is broken into body
pages at ``## `` headings (separator mode) or by accumulated length. Empty
inputs degrade gracefully — a missing title falls back to the first markdown
line, missing markdown yields just a cover.
"""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

try:
    import markdown as _md  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover — exercised when render extra not installed
    _md = None

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None  # type: ignore[assignment]


# 3:4 portrait at 2x dpr for crisp screenshots.
CARD_WIDTH = 1080
CARD_HEIGHT = 1440

_FONT_STACK = "'PingFang SC', 'Noto Sans CJK SC', 'Microsoft YaHei', sans-serif"


# ---------------------------------------------------------------------------
# Content → card list
# ---------------------------------------------------------------------------

def split_into_cards(content: dict[str, Any]) -> list[dict[str, str]]:
    """Split produce output into a list of card dicts: ``{kind, ...}``.

    - cover:   {kind, title, subtitle}
    - body:    {kind, heading, body_html}
    - cta:     {kind, hashtags, notes}
    """
    title = str(content.get("title") or "").strip()
    md = str(content.get("markdown") or "").strip()
    hashtags = content.get("hashtags") or []
    notes = str(content.get("publish_notes") or "").strip()

    if not title:
        # Fall back to the first non-empty markdown line as the title.
        first = next((ln.strip() for ln in md.splitlines() if ln.strip() and not ln.startswith("#")), "")
        title = first or "推荐"

    cards: list[dict[str, str]] = [{"kind": "cover", "title": title, "subtitle": _first_paragraph(md)}]

    for heading, body in _split_markdown_sections(md):
        cards.append({"kind": "body", "heading": heading, "body_html": _md_to_html(body)})

    # If no sections (no ## headings), drop the whole body into one body card.
    if len(cards) == 1 and md:
        cards.append({"kind": "body", "heading": "", "body_html": _md_to_html(md)})

    if hashtags or notes:
        cards.append({"kind": "cta", "hashtags": " ".join(h for h in hashtags if h), "notes": notes})

    return cards


def _first_paragraph(md: str) -> str:
    """Return the first plain-text paragraph of ``md`` for the cover subtitle."""
    for ln in md.splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            # Strip simple markdown emphasis for the subtitle.
            return re.sub(r"[*_`]", "", ln)[:60]
    return ""


def _split_markdown_sections(md: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, body) pairs at ``## `` headings.

    Content before the first ``## `` (if any) is folded into the first section
    as its body with an empty heading.
    """
    if not md:
        return []
    lines = md.splitlines()
    sections: list[tuple[str, str]] = []
    cur_heading = ""
    cur_body: list[str] = []
    for ln in lines:
        if ln.startswith("## "):
            if cur_body or cur_heading:
                sections.append((cur_heading, "\n".join(cur_body).strip()))
            cur_heading = ln[3:].strip()
            cur_body = []
        else:
            cur_body.append(ln)
    if cur_body or cur_heading:
        sections.append((cur_heading, "\n".join(cur_body).strip()))
    return sections


def _md_to_html(md_text: str) -> str:
    """Convert markdown to HTML. Falls back to escaped paragraphs if the
    ``markdown`` package isn't installed (so the renderer degrades, not crashes)."""
    if not md_text:
        return ""
    if _md is not None:
        return _md.markdown(md_text, extensions=["extra"])
    # Minimal fallback: escape and wrap paragraphs.
    escaped = html.escape(md_text)
    return "".join(f"<p>{p}</p>" for p in escaped.split("\n\n") if p.strip())


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def build_card_html(card: dict[str, str]) -> str:
    """Render a single card dict to a full HTML document sized 1080×1440."""
    kind = card.get("kind", "body")
    if kind == "cover":
        return _cover_html(card)
    if kind == "cta":
        return _cta_html(card)
    return _body_html(card)


def _cover_html(card: dict[str, str]) -> str:
    title = html.escape(card.get("title", ""))
    subtitle = html.escape(card.get("subtitle", ""))
    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:{CARD_WIDTH}px; height:{CARD_HEIGHT}px; font-family:{_FONT_STACK};
       background:linear-gradient(160deg,#f5f5f7 0%,#e8e8ed 100%);
       display:flex; flex-direction:column; justify-content:center; padding:120px 90px; }}
.title {{ font-size:88px; font-weight:800; line-height:1.2; color:#1d1d1f; letter-spacing:-1px; }}
.subtitle {{ font-size:40px; font-weight:400; color:#6e6e73; margin-top:36px; line-height:1.5; }}
.bar {{ width:96px; height:8px; background:#1d1d1f; border-radius:4px; margin-bottom:48px; }}
</style></head><body>
<div class="bar"></div>
<div class="title">{title}</div>
{f'<div class="subtitle">{subtitle}</div>' if subtitle else ''}
</body></html>"""


def _body_html(card: dict[str, str]) -> str:
    heading = html.escape(card.get("heading", ""))
    body_html = card.get("body_html", "")
    heading_block = f'<div class="heading">{heading}</div>' if heading else ""
    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:{CARD_WIDTH}px; height:{CARD_HEIGHT}px; font-family:{_FONT_STACK};
       background:#ffffff; padding:110px 90px; display:flex; flex-direction:column; }}
.heading {{ font-size:60px; font-weight:700; color:#1d1d1f; line-height:1.3; margin-bottom:48px; }}
.body {{ font-size:42px; line-height:1.75; color:#333336; }}
.body p {{ margin-bottom:32px; }}
.body ul,.body ol {{ padding-left:48px; margin-bottom:32px; }}
.body li {{ margin-bottom:16px; }}
.body strong {{ color:#1d1d1f; }}
</style></head><body>
{heading_block}
<div class="body">{body_html}</div>
</body></html>"""


def _cta_html(card: dict[str, str]) -> str:
    hashtags = html.escape(card.get("hashtags", ""))
    notes = html.escape(card.get("notes", ""))
    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:{CARD_WIDTH}px; height:{CARD_HEIGHT}px; font-family:{_FONT_STACK};
       background:linear-gradient(160deg,#1d1d1f 0%,#2c2c2e 100%);
       display:flex; flex-direction:column; justify-content:center; align-items:center;
       padding:120px 90px; color:#f5f5f7; }}
.hashtags {{ font-size:44px; font-weight:600; line-height:1.7; text-align:center; color:#0a84ff; }}
.notes {{ font-size:36px; color:#a1a1a6; margin-top:48px; text-align:center; line-height:1.5; }}
</style></head><body>
{f'<div class="hashtags">{hashtags}</div>' if hashtags else ''}
{f'<div class="notes">{notes}</div>' if notes else ''}
</body></html>"""


# ---------------------------------------------------------------------------
# Render → PNG
# ---------------------------------------------------------------------------

def render_xhs_cards(
    content: dict[str, Any],
    output_dir: str | Path,
    *,
    theme: str = "default",
) -> list[dict[str, Any]]:
    """Render Xiaohongshu card PNGs from produce ``content``.

    Returns a list of ``{path, kind}`` dicts. Raises ``RuntimeError`` if
    Playwright is not installed (the ``render`` extra provides it).
    """
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not installed. Install with: pip install 'promoagent[render]'"
        )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    cards = split_into_cards(content)
    results: list[dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for i, card in enumerate(cards):
                html_doc = build_card_html(card)
                page = browser.new_page(viewport={"width": CARD_WIDTH, "height": CARD_HEIGHT})
                page.set_content(html_doc, wait_until="load")
                kind = card["kind"]
                name = "cover.png" if kind == "cover" else (
                    "cta.png" if kind == "cta" else f"card_{i}.png"
                )
                path = out / name
                page.screenshot(path=str(path), full_page=False)
                page.close()
                results.append({"path": str(path), "kind": kind, "provider": "render_xhs"})
        finally:
            browser.close()

    return results

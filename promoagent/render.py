"""Render platform-native card images from produce output.

Turns the ``{title, markdown, hashtags, ...}`` dict produced by the pipeline
into a set of PNG cards via HTML/CSS + Playwright — a deterministic, styleable
alternative to AI image generation for text-heavy note cards.

Each platform is described by a :class:`PlatformRenderSpec` (size + card
strategy). The HTML templates and Playwright screenshot loop are shared across
all platforms; only the spec differs. Platforms that don't need image
rendering (Zhihu, Reddit) are pass-through and return an empty list.

Card strategies:
- ``carousel``: cover + body pages + CTA (Xiaohongshu, LinkedIn)
- ``single``:   one cover image only (Twitter og:image, WeChat 1:1)
- ``pair``:     two covers at different sizes (WeChat 21:9 + 1:1)
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    import markdown as _md  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    _md = None

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None  # type: ignore[assignment]


_FONT_STACK = "'PingFang SC', 'Noto Sans CJK SC', 'Microsoft YaHei', sans-serif"


# ---------------------------------------------------------------------------
# Platform specs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlatformRenderSpec:
    """Describes how to render cards for one platform."""
    key: str
    width: int
    height: int
    cards: str  # "carousel" | "single" | "pair" | "none"
    # For "pair" strategy: the second canvas size (first uses width/height).
    pair_width: int = 0
    pair_height: int = 0


SPECS: dict[str, PlatformRenderSpec] = {
    "xiaohongshu": PlatformRenderSpec("xiaohongshu", 1080, 1440, "carousel"),
    "xhs":         PlatformRenderSpec("xiaohongshu", 1080, 1440, "carousel"),
    "wechat":      PlatformRenderSpec("wechat", 2100, 900, "pair", pair_width=1000, pair_height=1000),
    "linkedin":    PlatformRenderSpec("linkedin", 1080, 1080, "carousel"),
    "twitter":     PlatformRenderSpec("twitter", 1200, 675, "single"),
    "x":           PlatformRenderSpec("twitter", 1200, 675, "single"),
    "producthunt": PlatformRenderSpec("producthunt", 1200, 630, "single"),
    "showhn":      PlatformRenderSpec("showhn", 1200, 675, "single"),
    "weibo":       PlatformRenderSpec("weibo", 1080, 1440, "carousel"),
    "telegram":    PlatformRenderSpec("telegram", 1200, 675, "single"),
    "bluesky":     PlatformRenderSpec("bluesky", 1200, 675, "single"),
    # Pass-through platforms: no image rendering (text-only).
    "zhihu":       PlatformRenderSpec("zhihu", 0, 0, "none"),
    "reddit":      PlatformRenderSpec("reddit", 0, 0, "none"),
}

# Platforms where card rendering is the default for --image-style auto.
_CARD_PLATFORMS = {
    "xiaohongshu", "xhs", "wechat", "linkedin", "twitter", "x",
    "producthunt", "showhn", "weibo", "telegram", "bluesky",
}


def get_spec(platform: str) -> PlatformRenderSpec | None:
    """Return the render spec for a platform, resolving aliases."""
    return SPECS.get(platform.lower().strip())


def is_card_platform(platform: str) -> bool:
    """Whether card rendering applies (vs AI photo for --image-style auto)."""
    return platform.lower().strip() in _CARD_PLATFORMS


# ---------------------------------------------------------------------------
# Content → card list (shared split logic)
# ---------------------------------------------------------------------------

def split_into_cards(content: dict[str, Any], strategy: str = "carousel") -> list[dict[str, Any]]:
    """Split produce output into a list of card dicts.

    ``strategy`` controls how many cards and which kinds:
    - ``carousel``: cover + body pages + optional CTA
    - ``single``:   one cover only
    - ``pair``:     two covers (the caller renders each at its own size)
    - ``none``:     [] (pass-through)
    """
    if strategy == "none":
        return []

    title = str(content.get("title") or "").strip()
    md = str(content.get("markdown") or "").strip()
    hashtags = content.get("hashtags") or []
    notes = str(content.get("publish_notes") or "").strip()

    if not title:
        first = next((ln.strip() for ln in md.splitlines() if ln.strip() and not ln.startswith("#")), "")
        title = first or "推荐"

    cover = {"kind": "cover", "title": title, "subtitle": _first_paragraph(md)}

    if strategy in ("single", "pair"):
        # single → [cover]; pair → [cover, cover] (same content, caller uses diff sizes)
        return [cover] if strategy == "single" else [cover, dict(cover)]

    # carousel
    cards: list[dict[str, Any]] = [cover]
    for heading, body in _split_markdown_sections(md):
        cards.append({"kind": "body", "heading": heading, "body_html": _md_to_html(body)})
    if len(cards) == 1 and md:  # no ## headings → one body card
        cards.append({"kind": "body", "heading": "", "body_html": _md_to_html(md)})
    if hashtags or notes:
        cards.append({"kind": "cta", "hashtags": " ".join(h for h in hashtags if h), "notes": notes})
    return cards


def _first_paragraph(md: str) -> str:
    for ln in md.splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            return re.sub(r"[*_`]", "", ln)[:60]
    return ""


def _split_markdown_sections(md: str) -> list[tuple[str, str]]:
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
    if not md_text:
        return ""
    if _md is not None:
        return _md.markdown(md_text, extensions=["extra"])
    escaped = html.escape(md_text)
    return "".join(f"<p>{p}</p>" for p in escaped.split("\n\n") if p.strip())


# ---------------------------------------------------------------------------
# HTML rendering (size-parameterized)
# ---------------------------------------------------------------------------

def build_card_html(card: dict[str, Any], width: int, height: int) -> str:
    """Render a card dict to a full HTML document at the given size."""
    kind = card.get("kind", "body")
    if kind == "cover":
        return _cover_html(card, width, height)
    if kind == "cta":
        return _cta_html(card, width, height)
    return _body_html(card, width, height)


def _cover_html(card: dict[str, Any], w: int, h: int) -> str:
    title = html.escape(card.get("title", ""))
    subtitle = html.escape(card.get("subtitle", ""))
    # Scale font sizes to canvas size so cards look right at any dimension.
    title_size = int(w * 0.082)
    sub_size = int(w * 0.037)
    bar_w = int(w * 0.089)
    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:{w}px; height:{h}px; font-family:{_FONT_STACK};
       background:linear-gradient(160deg,#f5f5f7 0%,#e8e8ed 100%);
       display:flex; flex-direction:column; justify-content:center; padding:{int(w*0.083)}px {int(w*0.083)}px; }}
.title {{ font-size:{title_size}px; font-weight:800; line-height:1.2; color:#1d1d1f; letter-spacing:-1px; }}
.subtitle {{ font-size:{sub_size}px; font-weight:400; color:#6e6e73; margin-top:{int(h*0.025)}px; line-height:1.5; }}
.bar {{ width:{bar_w}px; height:8px; background:#1d1d1f; border-radius:4px; margin-bottom:{int(h*0.033)}px; }}
</style></head><body>
<div class="bar"></div>
<div class="title">{title}</div>
{f'<div class="subtitle">{subtitle}</div>' if subtitle else ''}
</body></html>"""


def _body_html(card: dict[str, Any], w: int, h: int) -> str:
    heading = html.escape(card.get("heading", ""))
    body_html = card.get("body_html", "")
    heading_block = f'<div class="heading">{heading}</div>' if heading else ""
    h_size = int(w * 0.056)
    b_size = int(w * 0.039)
    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:{w}px; height:{h}px; font-family:{_FONT_STACK};
       background:#ffffff; padding:{int(w*0.083)}px {int(w*0.083)}px; display:flex; flex-direction:column; }}
.heading {{ font-size:{h_size}px; font-weight:700; color:#1d1d1f; line-height:1.3; margin-bottom:{int(h*0.033)}px; }}
.body {{ font-size:{b_size}px; line-height:1.75; color:#333336; }}
.body p {{ margin-bottom:{int(h*0.022)}px; }}
.body ul,.body ol {{ padding-left:{int(w*0.044)}px; margin-bottom:{int(h*0.022)}px; }}
.body li {{ margin-bottom:{int(h*0.011)}px; }}
.body strong {{ color:#1d1d1f; }}
</style></head><body>
{heading_block}
<div class="body">{body_html}</div>
</body></html>"""


def _cta_html(card: dict[str, Any], w: int, h: int) -> str:
    hashtags = html.escape(card.get("hashtags", ""))
    notes = html.escape(card.get("notes", ""))
    tag_size = int(w * 0.041)
    note_size = int(w * 0.033)
    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:{w}px; height:{h}px; font-family:{_FONT_STACK};
       background:linear-gradient(160deg,#1d1d1f 0%,#2c2c2e 100%);
       display:flex; flex-direction:column; justify-content:center; align-items:center;
       padding:{int(w*0.083)}px; color:#f5f5f7; }}
.hashtags {{ font-size:{tag_size}px; font-weight:600; line-height:1.7; text-align:center; color:#0a84ff; }}
.notes {{ font-size:{note_size}px; color:#a1a1a6; margin-top:{int(h*0.033)}px; text-align:center; line-height:1.5; }}
</style></head><body>
{f'<div class="hashtags">{hashtags}</div>' if hashtags else ''}
{f'<div class="notes">{notes}</div>' if notes else ''}
</body></html>"""


# ---------------------------------------------------------------------------
# Render → PNG (shared Playwright loop)
# ---------------------------------------------------------------------------

def _render_cards_to_pngs(
    cards: list[dict[str, Any]],
    sizes: list[tuple[int, int]],
    out: Path,
    prefix: str,
) -> list[dict[str, Any]]:
    """Screenshot each card at its corresponding size. ``sizes[i]`` matches ``cards[i]``."""
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not installed. Install with: pip install 'promoagent[render]'"
        )
    results: list[dict[str, Any]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for i, (card, (w, h)) in enumerate(zip(cards, sizes)):
                html_doc = build_card_html(card, w, h)
                page = browser.new_page(viewport={"width": w, "height": h})
                page.set_content(html_doc, wait_until="load")
                kind = card["kind"]
                name = f"{prefix}-{kind}.png" if kind in ("cover", "cta") else f"{prefix}-card_{i}.png"
                path = out / name
                page.screenshot(path=str(path), full_page=False)
                page.close()
                results.append({"path": str(path), "kind": kind, "provider": "render",
                                "width": w, "height": h})
        finally:
            browser.close()
    return results


def render_platform_cards(
    platform: str,
    content: dict[str, Any],
    output_dir: str | Path,
    *,
    theme: str = "default",
) -> list[dict[str, Any]]:
    """Render card PNGs for a platform from produce ``content``.

    Returns a list of ``{path, kind, provider, width, height}`` dicts.
    Returns ``[]`` for pass-through platforms (zhihu, reddit) or unknown
    platforms. Raises ``RuntimeError`` if Playwright is not installed.
    """
    spec = get_spec(platform)
    if spec is None:
        import logging
        logging.getLogger("promoagent").info("no render spec for platform: %s", platform)
        return []
    if spec.cards == "none":
        return []

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    cards = split_into_cards(content, spec.cards)
    if not cards:
        return []

    # Build the size list: each card gets the spec's size; pair's second card
    # uses the pair_width/pair_height.
    sizes: list[tuple[int, int]] = []
    for i, _ in enumerate(cards):
        if spec.cards == "pair" and i == 1:
            sizes.append((spec.pair_width, spec.pair_height))
        else:
            sizes.append((spec.width, spec.height))

    return _render_cards_to_pngs(cards, sizes, out, prefix=spec.key)

"""Tests for the platform card renderer.

The pure content-splitting and HTML-building functions are tested directly
(``split_into_cards`` / ``build_card_html``). The Playwright screenshot path
is mocked since it needs a real browser.
"""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from promoagent.render import (
    split_into_cards, build_card_html, render_platform_cards,
    get_spec, SPECS, is_card_platform,
    _split_markdown_sections, _first_paragraph,
)


class TestSplitIntoCards(unittest.TestCase):

    def test_full_content_produces_cover_body_cta(self):
        content = {
            "title": "测试标题",
            "markdown": "## 要点1\n内容\n\n## 要点2\n更多",
            "hashtags": ["#tag1", "#tag2"],
            "publish_notes": "晚上发",
        }
        cards = split_into_cards(content)
        self.assertEqual(cards[0]["kind"], "cover")
        self.assertEqual(cards[0]["title"], "测试标题")
        self.assertEqual(cards[1]["kind"], "body")
        self.assertEqual(cards[1]["heading"], "要点1")
        self.assertEqual(cards[2]["kind"], "body")
        self.assertEqual(cards[2]["heading"], "要点2")
        self.assertEqual(cards[-1]["kind"], "cta")
        self.assertIn("#tag1", cards[-1]["hashtags"])

    def test_empty_content_falls_back_to_cover(self):
        cards = split_into_cards({})
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["kind"], "cover")
        self.assertTrue(cards[0]["title"])  # non-empty fallback

    def test_no_title_uses_first_paragraph(self):
        cards = split_into_cards({"markdown": "第一段内容\n\n## 标题\n正文"})
        self.assertEqual(cards[0]["title"], "第一段内容")

    def test_markdown_without_headings_one_body_card(self):
        cards = split_into_cards({"title": "T", "markdown": "整段正文没有标题"})
        # cover + one body (whole markdown) — no cta (no hashtags/notes)
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[1]["kind"], "body")

    def test_cta_omitted_when_no_hashtags_or_notes(self):
        cards = split_into_cards({"title": "T", "markdown": "正文"})
        self.assertNotIn("cta", [c["kind"] for c in cards])

    def test_single_strategy_one_cover(self):
        cards = split_into_cards({"title": "T", "markdown": "## a\nb", "hashtags": ["#x"]}, "single")
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["kind"], "cover")

    def test_pair_strategy_two_covers(self):
        cards = split_into_cards({"title": "T", "markdown": "正文"}, "pair")
        self.assertEqual(len(cards), 2)
        self.assertTrue(all(c["kind"] == "cover" for c in cards))

    def test_none_strategy_empty(self):
        self.assertEqual(split_into_cards({"title": "T"}, "none"), [])


class TestPlatformSpecs(unittest.TestCase):

    def test_xhs_spec_is_carousel_3_4(self):
        spec = get_spec("xhs")
        self.assertEqual(spec.cards, "carousel")
        self.assertEqual((spec.width, spec.height), (1080, 1440))

    def test_wechat_spec_is_pair_with_two_sizes(self):
        spec = get_spec("wechat")
        self.assertEqual(spec.cards, "pair")
        self.assertEqual((spec.width, spec.height), (2100, 900))
        self.assertEqual((spec.pair_width, spec.pair_height), (1000, 1000))

    def test_twitter_spec_is_single_16_9(self):
        spec = get_spec("twitter")
        self.assertEqual(spec.cards, "single")
        self.assertEqual((spec.width, spec.height), (1200, 675))

    def test_linkedin_spec_is_carousel_square(self):
        spec = get_spec("linkedin")
        self.assertEqual(spec.cards, "carousel")
        self.assertEqual((spec.width, spec.height), (1080, 1080))

    def test_zhihu_reddit_are_pass_through(self):
        for plat in ("zhihu", "reddit"):
            self.assertEqual(get_spec(plat).cards, "none")

    def test_new_platforms_have_specs(self):
        """Platforms that were missing specs now have them."""
        for plat in ("producthunt", "showhn", "weibo", "telegram", "bluesky"):
            spec = get_spec(plat)
            self.assertIsNotNone(spec, f"{plat} should have a render spec")
            self.assertNotEqual(spec.cards, "none", f"{plat} should not be pass-through")

    def test_unknown_platform_returns_none(self):
        self.assertIsNone(get_spec("nonexistent"))

    def test_is_card_platform(self):
        self.assertTrue(is_card_platform("xiaohongshu"))
        self.assertTrue(is_card_platform("twitter"))
        self.assertFalse(is_card_platform("zhihu"))
        self.assertFalse(is_card_platform("unknown"))


class TestBuildCardHtml(unittest.TestCase):

    def test_cover_html_contains_title(self):
        html = build_card_html({"kind": "cover", "title": "标题", "subtitle": "副"}, 1080, 1440)
        self.assertIn("标题", html)
        self.assertIn("副", html)
        self.assertIn("1080", html)

    def test_body_html_contains_heading_and_body(self):
        html = build_card_html({"kind": "body", "heading": "要点", "body_html": "<p>内容</p>"}, 1080, 1440)
        self.assertIn("要点", html)
        self.assertIn("<p>内容</p>", html)

    def test_cta_html_contains_hashtags(self):
        html = build_card_html({"kind": "cta", "hashtags": "#a #b", "notes": "提示"}, 1080, 1440)
        self.assertIn("#a #b", html)
        self.assertIn("提示", html)

    def test_html_escapes_title(self):
        html = build_card_html({"kind": "cover", "title": "<script>x</script>", "subtitle": ""}, 1080, 1440)
        self.assertNotIn("<script>", html)


class TestRenderXhsCards(unittest.TestCase):

    def test_render_raises_without_playwright(self):
        """When playwright isn't importable, render_platform_cards raises RuntimeError."""
        with patch("promoagent.render.sync_playwright", None):
            with self.assertRaises(RuntimeError):
                render_platform_cards("xiaohongshu", {"title": "x"}, "/tmp/xhs_test_noplaywright")

    def test_render_calls_playwright_and_returns_paths(self):
        """Mock playwright to verify the render flow produces card metadata."""
        content = {"title": "标题", "markdown": "## 要点\n内容", "hashtags": ["#t"]}
        fake_page = type("P", (), {
            "set_content": lambda self, html, wait_until="load": None,
            "screenshot": lambda self, path=None, full_page=False: Path(path).write_bytes(b"png"),
            "close": lambda self: None,
        })()
        fake_browser = type("B", (), {
            "new_page": lambda self, viewport=None: fake_page,
            "close": lambda self: None,
        })()
        class _FakePlaywright:
            def __enter__(self):
                return type("Pw", (), {"chromium": type("Ch", (), {"launch": lambda s: fake_browser})()})()
            def __exit__(self, *a):
                return None

        import tempfile
        with tempfile.TemporaryDirectory() as tmp, \
                patch("promoagent.render.sync_playwright", lambda: _FakePlaywright()):
            result = render_platform_cards("xiaohongshu", content, tmp)
        # cover + 1 body + cta = 3 cards
        self.assertEqual(len(result), 3)
        kinds = [r["kind"] for r in result]
        self.assertEqual(kinds, ["cover", "body", "cta"])
        for r in result:
            self.assertEqual(r["provider"], "render")
            # Paths are under the output dir (mock screenshot doesn't write a
            # real file, so we check the path string rather than existence).
            self.assertTrue(r["path"].startswith(tmp))

    def test_render_platform_cards_passthrough_returns_empty(self):
        """Zhihu/Reddit (cards="none") return [] without launching playwright."""
        self.assertEqual(render_platform_cards("zhihu", {"title": "x"}, "/tmp/pt"), [])
        self.assertEqual(render_platform_cards("nonexistent", {"title": "x"}, "/tmp/pt"), [])

    def test_render_platform_cards_twitter_single(self):
        """Twitter (single) produces one cover, no body/cta."""
        fake_page = type("P", (), {
            "set_content": lambda self, html, wait_until="load": None,
            "screenshot": lambda self, path=None, full_page=False: Path(path).write_bytes(b"png"),
            "close": lambda self: None,
        })()
        fake_browser = type("B", (), {
            "new_page": lambda self, viewport=None: fake_page,
            "close": lambda self: None,
        })()
        class _FakePlaywright:
            def __enter__(self):
                return type("Pw", (), {"chromium": type("Ch", (), {"launch": lambda s: fake_browser})()})()
            def __exit__(self, *a): return None

        import tempfile
        content = {"title": "T", "markdown": "## a\nb", "hashtags": ["#x"]}
        with tempfile.TemporaryDirectory() as tmp, \
                patch("promoagent.render.sync_playwright", lambda: _FakePlaywright()):
            result = render_platform_cards("twitter", content, tmp)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["kind"], "cover")
        self.assertEqual((result[0]["width"], result[0]["height"]), (1200, 675))


if __name__ == "__main__":
    unittest.main()

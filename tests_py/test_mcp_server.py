"""Tests for the PromoAgent MCP server tool layer.

Tools are tested by calling the ``_impl_*`` pure functions directly (the
``@mcp.tool`` wrappers are thin pass-throughs). ``dispatch_chat`` and
``find_examples`` are mocked so no real network/API calls happen.

State is isolated per test by patching ``mcp_server.PipelineState`` to use a
temporary cache_dir, since the real server persists state to disk by source_id.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import promoagent.mcp_server as mcp_server
import promoagent.pipeline as pipeline
from promoagent.mcp_server import (
    _impl_analyze, _impl_list_platforms, _impl_research, _impl_blueprint,
    _impl_edit_blueprint, _impl_produce, _impl_draft,
    _impl_image_brief, _impl_build_image_prompt, create_server,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests_py" / "fixtures"

RESEARCH_PAYLOAD = {
    "facts": {"core_claim": "测试主张", "gaps": ["目标用户是谁", "价格区间"]},
    "strategy": {
        "recommended_platforms": ["xiaohongshu", "twitter"],
        "positioning": {"one_liner": "定位", "promise": "承诺", "differentiator": "差异"},
        "creative_direction": {"main_hook": "h", "hook_variants": [], "tone": "t", "key_message": "m"},
    },
}
BLUEPRINT_PAYLOAD = {
    "version": "2.0",
    "source": {"project_name": "Test"},
    "positioning": {"one_liner": "定位", "core_promise": "承诺", "key_message": "m"},
    "elements": [
        {"id": "hook-main", "type": "hook", "label": "钩子", "content": "旧钩子",
         "variants": ["v1", "v2", "v3"], "editable": False, "required": True},
    ],
    "structure": {"recommended_order": ["hook-main"], "alternative_structures": []},
    "metrics": {},
}


def _fake_dispatch_factory():
    """Return a dispatch_chat mock that responds by prompt content.

    Branch order matters: produce prompts contain "Blueprint" and "内容元素"
    too, so the platform-content branch is detected by its platform-spec JSON
    / "转换为" cue rather than the shared blueprint keywords.
    """
    def fake_dispatch(messages, config):
        user = messages[-1]["content"]
        if "推广策略" in user or "research" in user.lower():
            return json.dumps(RESEARCH_PAYLOAD, ensure_ascii=False)
        if "转换为" in user or "平台规格" in user:
            return json.dumps({"platform": "x", "markdown": "平台内容", "hashtags": ["#t"]},
                              ensure_ascii=False)
        if "内容元素" in user or "Blueprint" in user:
            return json.dumps(BLUEPRINT_PAYLOAD, ensure_ascii=False)
        return json.dumps({"platform": "x", "markdown": "平台内容", "hashtags": ["#t"]},
                          ensure_ascii=False)
    return fake_dispatch


class _StateIsolationMixin:
    """Patch PipelineState to use a temp cache_dir for the duration of each test."""

    def _patch_state(self, tmp):
        real_init = pipeline.PipelineState.__init__

        def patched_init(self, source_id, cache_dir=None):
            real_init(self, source_id, cache_dir=Path(tmp) / "state")

        return patch.object(pipeline.PipelineState, "__init__", patched_init)


class TestMcpServer(_StateIsolationMixin, unittest.TestCase):

    # ------------------------------------------------------------------
    # No-AI tools
    # ------------------------------------------------------------------

    def test_s2l_list_platforms_serializable(self):
        out = _impl_list_platforms()
        # Shape matches every other tool: _ok(platforms=[...]).
        self.assertTrue(out["ok"])
        plats = out["platforms"]
        keys = [p["key"] for p in plats]
        self.assertIn("xiaohongshu", keys)
        self.assertIn("twitter", keys)
        # Must be JSON serializable (MCP requirement).
        json.dumps(out)

    def test_s2l_analyze_returns_source_id(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp):
            out = _impl_analyze(str(FIXTURES / "healthy-repo"))
        self.assertTrue(out["ok"], out)
        self.assertTrue(out["source_id"])
        self.assertEqual(out["project"]["name"], "repo-pulse")
        self.assertIn("launchRisks", out["evidence"])

    # ------------------------------------------------------------------
    # Research
    # ------------------------------------------------------------------

    def test_s2l_research_returns_facts_and_gaps(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp), \
                patch.object(pipeline, "dispatch_chat", _fake_dispatch_factory()), \
                patch.object(pipeline, "find_examples", lambda r, **kw: []):
            out = _impl_research(str(FIXTURES / "healthy-repo"), search=False)
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["facts"]["core_claim"], "测试主张")
        self.assertEqual(out["facts"]["gaps"], ["目标用户是谁", "价格区间"])
        self.assertTrue(out["source_id"])

    def test_s2l_research_no_search_skips_find(self):
        find_calls = []

        def fake_find(r, **kw):
            find_calls.append(kw)
            return []

        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp), \
                patch.object(pipeline, "dispatch_chat", _fake_dispatch_factory()), \
                patch.object(pipeline, "find_examples", fake_find):
            _impl_research(str(FIXTURES / "healthy-repo"), search=False)
        self.assertEqual(find_calls, [], "search=False must not call find_examples")

    # ------------------------------------------------------------------
    # Blueprint
    # ------------------------------------------------------------------

    def test_s2l_blueprint_from_source_id(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp), \
                patch.object(pipeline, "dispatch_chat", _fake_dispatch_factory()), \
                patch.object(pipeline, "find_examples", lambda r, **kw: []):
            research = _impl_research(str(FIXTURES / "healthy-repo"), search=False)
            out = _impl_blueprint(research["source_id"])
        self.assertTrue(out["ok"], out)
        self.assertEqual(len(out["elements"]), 1)
        self.assertEqual(out["elements"][0]["id"], "hook-main")
        self.assertEqual(out["positioning"]["one_liner"], "定位")

    def test_s2l_blueprint_missing_research_errors(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp):
            out = _impl_blueprint("nonexistent-source-id")
        self.assertFalse(out["ok"])
        self.assertIn("research", out["error"].lower())

    # ------------------------------------------------------------------
    # Edit blueprint
    # ------------------------------------------------------------------

    def test_s2l_edit_blueprint_applies(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp), \
                patch.object(pipeline, "dispatch_chat", _fake_dispatch_factory()), \
                patch.object(pipeline, "find_examples", lambda r, **kw: []):
            sid = _impl_research(str(FIXTURES / "healthy-repo"), search=False)["source_id"]
            _impl_blueprint(sid)
            out = _impl_edit_blueprint(sid, {"hook-main": "新钩子文案"})
        self.assertTrue(out["ok"], out)
        self.assertIn("新钩子文案", out["preview"])
        # The edited element is persisted in state.
        self.assertEqual(out["elements"][0]["content"], "新钩子文案")

    def test_s2l_edit_blueprint_missing_blueprint_errors(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp):
            out = _impl_edit_blueprint("nonexistent-source-id", {"x": "y"})
        self.assertFalse(out["ok"])
        self.assertIn("blueprint", out["error"].lower())

    # ------------------------------------------------------------------
    # Produce
    # ------------------------------------------------------------------

    def test_s2l_produce_from_source_id(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp), \
                patch.object(pipeline, "dispatch_chat", _fake_dispatch_factory()), \
                patch.object(pipeline, "find_examples", lambda r, **kw: []):
            sid = _impl_research(str(FIXTURES / "healthy-repo"), search=False)["source_id"]
            _impl_blueprint(sid)
            out = _impl_produce(sid)
        self.assertTrue(out["ok"], out)
        self.assertIn("xiaohongshu", out["produce"])
        self.assertEqual(out["produce"]["xiaohongshu"]["markdown"], "平台内容")

    def test_s2l_produce_passes_quality_mode(self):
        """The quality argument is threaded into options['quality_mode']."""
        captured = {}

        def fake_stage_produce(blueprint, research, state, options=None, **kw):
            captured["quality_mode"] = (options or {}).get("quality_mode")
            return {"data": {}, "platforms": []}

        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp), \
                patch.object(pipeline, "dispatch_chat", _fake_dispatch_factory()), \
                patch.object(pipeline, "find_examples", lambda r, **kw: []), \
                patch.object(mcp_server, "stage_produce", fake_stage_produce):
            sid = _impl_research(str(FIXTURES / "healthy-repo"), search=False)["source_id"]
            _impl_blueprint(sid)
            _impl_produce(sid, quality="polished")
        self.assertEqual(captured["quality_mode"], "polished")

    def test_s2l_produce_passes_result_for_backflow(self):
        """s2l_produce threads `result` from state so polished backflow can rerun research."""
        captured = {}

        def fake_stage_produce(blueprint, research, state, options=None, **kw):
            captured["result"] = kw.get("result")
            return {"data": {}, "platforms": []}

        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp), \
                patch.object(pipeline, "dispatch_chat", _fake_dispatch_factory()), \
                patch.object(pipeline, "find_examples", lambda r, **kw: []), \
                patch.object(mcp_server, "stage_produce", fake_stage_produce):
            sid = _impl_research(str(FIXTURES / "healthy-repo"), search=False)["source_id"]
            _impl_blueprint(sid)
            _impl_produce(sid, quality="polished")
        # result was cached by s2l_research → s2l_produce must forward it.
        self.assertIsNotNone(captured["result"])
        self.assertEqual(captured["result"].get("project", {}).get("name"), "repo-pulse")

    def test_s2l_draft_passes_quality_mode(self):
        captured = {}

        def fake_run_pipeline(result, options=None, **kw):
            captured["quality_mode"] = (options or {}).get("quality_mode")
            return {"research": {"data": {}}, "produce": {"data": {}}}

        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp), \
                patch.object(pipeline, "find_examples", lambda r, **kw: []), \
                patch.object(mcp_server, "run_pipeline", fake_run_pipeline):
            _impl_draft(str(FIXTURES / "healthy-repo"), search=False, quality="balanced")
        self.assertEqual(captured["quality_mode"], "balanced")

    def test_s2l_produce_missing_blueprint_errors(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp):
            out = _impl_produce("nonexistent-source-id")
        self.assertFalse(out["ok"])

    # ------------------------------------------------------------------
    # Image prompt tools
    # ------------------------------------------------------------------

    def test_s2l_image_brief_returns_fields(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp):
            sid = _impl_analyze(str(FIXTURES / "healthy-repo"))["source_id"]
            out = _impl_image_brief(sid, title="测试标题", cta="立即了解", badges="护眼,金属")
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["brief"]["title"], "测试标题")
        self.assertEqual(out["brief"]["cta"], "立即了解")
        self.assertIn("护眼", out["brief"]["badges"])

    def test_s2l_image_brief_missing_result_errors(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp):
            out = _impl_image_brief("nonexistent-source-id")
        self.assertFalse(out["ok"])

    def test_s2l_build_image_prompt_returns_prompt(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp):
            sid = _impl_analyze(str(FIXTURES / "healthy-repo"))["source_id"]
            # model="dall-e-3" forces the English structured-prompt branch.
            out = _impl_build_image_prompt(sid, platform="xhs", model="dall-e-3")
        self.assertTrue(out["ok"], out)
        self.assertTrue(out["prompt"])
        self.assertIn("3:4", out["prompt"])  # xhs portrait
        self.assertEqual(out["platform"], "xhs")

    def test_s2l_build_image_prompt_chinese_model(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp):
            sid = _impl_analyze(str(FIXTURES / "healthy-repo"))["source_id"]
            out = _impl_build_image_prompt(sid, platform="xhs", model="Qwen/Qwen-Image")
        self.assertTrue(out["ok"], out)
        self.assertIn("小红书封面", out["prompt"])  # Chinese branch
        # Chinese branch now injects full skill schema (English JSON effective for Qwen)
        self.assertIn("PROMO_RENDER_SPEC", out["prompt"])
        self.assertIn("hierarchy", out["prompt"])

    def test_s2l_build_image_prompt_missing_result_errors(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp):
            out = _impl_build_image_prompt("nonexistent-source-id", platform="xhs")
        self.assertFalse(out["ok"])

    # ------------------------------------------------------------------
    # One-shot draft
    # ------------------------------------------------------------------

    def test_s2l_draft_one_shot(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp), \
                patch.object(pipeline, "dispatch_chat", _fake_dispatch_factory()), \
                patch.object(pipeline, "find_examples", lambda r, **kw: []):
            out = _impl_draft(str(FIXTURES / "healthy-repo"), search=False)
        self.assertTrue(out["ok"], out)
        self.assertIn("xiaohongshu", out["produce"])
        self.assertEqual(out["recommended_platforms"], ["xiaohongshu", "twitter"])

    # ------------------------------------------------------------------
    # Error handling & serialization
    # ------------------------------------------------------------------

    def test_s2l_research_dispatch_failure_returns_error(self):
        """When the AI call raises, the tool returns a structured error, not a crash."""
        def boom(messages, config):
            raise RuntimeError("AI provider down")

        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp), \
                patch.object(pipeline, "dispatch_chat", boom), \
                patch.object(pipeline, "find_examples", lambda r, **kw: []):
            out = _impl_research(str(FIXTURES / "healthy-repo"), search=False)
        self.assertFalse(out["ok"])
        self.assertIn("research failed", out["error"])
        # source_id is still returned so the caller can retry/clean up.
        self.assertTrue(out["source_id"])

    def test_impl_returns_are_json_serializable(self):
        """Every _impl_* return value must be JSON-serializable for MCP."""
        with tempfile.TemporaryDirectory() as tmp, self._patch_state(tmp), \
                patch.object(pipeline, "dispatch_chat", _fake_dispatch_factory()), \
                patch.object(pipeline, "find_examples", lambda r, **kw: []):
            payloads = [
                _impl_list_platforms(),
                _impl_analyze(str(FIXTURES / "healthy-repo")),
                _impl_research(str(FIXTURES / "healthy-repo"), search=False),
            ]
            sid = payloads[2]["source_id"]
            payloads.append(_impl_blueprint(sid))
            payloads.append(_impl_edit_blueprint(sid, {"hook-main": "x"}))
            payloads.append(_impl_produce(sid))
            payloads.append(_impl_draft(str(FIXTURES / "healthy-repo"), search=False))
            payloads.append(_impl_image_brief(sid, title="t"))
            payloads.append(_impl_build_image_prompt(sid, platform="xhs", model="dall-e-3"))
        for p in payloads:
            json.dumps(p)  # raises if not serializable

    # ------------------------------------------------------------------
    # Server registration
    # ------------------------------------------------------------------

    def test_create_server_registers_all_tools(self):
        server = create_server()
        tools = sorted(server._tool_manager._tools.keys())
        self.assertEqual(tools, [
            "s2l_analyze", "s2l_blueprint", "s2l_build_image_prompt", "s2l_draft",
            "s2l_edit_blueprint", "s2l_image_brief", "s2l_list_platforms",
            "s2l_produce", "s2l_research",
        ])

    def test_err_truncates_long_messages(self):
        """_err caps message length so upstream API bodies don't leak to clients."""
        from promoagent.mcp_server import _err
        long = "x" * 500
        out = _err(long)
        self.assertFalse(out["ok"])
        self.assertLessEqual(len(out["error"]), 301)  # 300 + ellipsis
        self.assertTrue(out["error"].endswith("…"))

    def test_err_flattens_newlines(self):
        from promoagent.mcp_server import _err
        out = _err("line1\nline2\nline3")
        self.assertNotIn("\n", out["error"])

    def test_main_without_mcp_exits_nonzero(self):
        with patch.object(mcp_server, "_MCP_AVAILABLE", False):
            with self.assertRaises(SystemExit) as ctx:
                mcp_server.main()
        self.assertNotEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()

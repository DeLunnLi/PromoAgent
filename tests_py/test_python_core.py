"""Test suite for PromoAgent v0.4 (draft pipeline) API.

Covers the modules that exist in the current codebase:
- analyzer, cache, logger, publish, optimize (unchanged surface)
- ai (unified dispatch_chat / ai_config / _detect_provider)
- image, image_skills (current image generation)
- examples (detect_category / find_examples)
- platforms (centralized PlatformSpec registry)  [new]
- pipeline (3-stage research -> blueprint -> produce)  [new]

Tests for removed modules (interactive, promo_prompts) and removed ai
helpers (generate_ai_content / refine_content / validate_content /
_chat_*) have been deleted. Tests for the new pipeline and platforms
modules have been added.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

from promoagent.ai import _detect_provider, ai_config, dispatch_chat, parse_json_content
from promoagent import cache
from promoagent.logger import Logger, LogLevel, get_logger, log_duration, LogTimer
from promoagent.publish import (
    BlueskyPublisher, TelegramPublisher, TwitterPublisher,
    available_publishers, publish_content,
)
from promoagent.analyzer import analyze_free_text, analyze_target, parse_github_owner_repo
from promoagent.image import (
    apply_text_overlay, build_image_prompt, fetch_readme_images,
    generate_openai_image, generate_platform_images, image_brief, image_config,
)
from promoagent.examples import detect_category, find_examples
from promoagent.image_skills import list_image_skills, resolve_image_skill
from promoagent.optimize import run_optimize
from promoagent.platforms import (
    PLATFORMS, get_platform, get_primary_platforms, list_platforms, to_prompt_dict,
)
import promoagent.pipeline as pipeline
from promoagent.pipeline import (
    PipelineState, _source_id, stage_research, stage_blueprint, stage_produce,
    edit_blueprint, preview_blueprint, run_pipeline,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests_py" / "fixtures"


def _research_payload() -> dict:
    return {
        "facts": {
            "core_claim": "一句话核心主张",
            "key_facts": ["事实1", "事实2"],
            "unique_angles": ["角度1"],
            "target_users": [{"segment": "开发者", "pain": "推广难", "desire": "省时间"}],
            "use_cases": ["场景1"],
            "evidence_strength": "medium",
            "gaps": ["缺口1"],
            "risks": ["风险1"],
        },
        "strategy": {
            "positioning": {"one_liner": "定位", "promise": "承诺", "differentiator": "差异"},
            "creative_direction": {
                "main_hook": "主推角度", "hook_variants": ["v1", "v2", "v3"],
                "tone": "专业", "key_message": "核心信息",
            },
            "recommended_platforms": ["xiaohongshu", "twitter"],
            "platform_rationale": "理由",
            "content_sequence": ["xiaohongshu", "twitter"],
        },
    }


def _blueprint_payload() -> dict:
    return {
        "version": "2.0",
        "source": {"project_name": "Test", "source_url": ""},
        "positioning": {"one_liner": "定位", "core_promise": "承诺", "key_message": "核心信息"},
        "elements": [
            {
                "id": "hook-main", "type": "hook", "label": "开场钩子",
                "content": "钩子内容", "variants": ["v1", "v2", "v3", "v4"],
                "char_limit": 100, "purpose": "抓注意力", "editable": False, "required": True,
            },
            {
                "id": "cta-main", "type": "cta", "label": "行动号召",
                "content": "立即试用", "variants": ["c1", "c2", "c3"],
                "char_limit": 80, "purpose": "转化", "editable": False, "required": True,
            },
        ],
        "structure": {
            "recommended_order": ["hook-main", "cta-main"],
            "alternative_structures": [
                {"name": "故事型", "order": ["hook-main", "cta-main"]},
            ],
        },
        "metrics": {"estimated_read_time": "30s", "emotion_profile": "neutral", "complexity_score": 3},
    }


class PythonCoreTest(unittest.TestCase):

    # ------------------------------------------------------------------
    # Analyzer
    # ------------------------------------------------------------------

    def test_analyzes_healthy_repo(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        self.assertEqual(result["project"]["name"], "repo-pulse")
        self.assertEqual(result["project"]["installCommand"], "npx repo-pulse .")
        self.assertEqual(result["repository"]["readme"], "README.md")
        self.assertTrue(result["evidence"]["visuals"])

    def test_analyze_free_text_restaurant(self):
        result = analyze_free_text("上海阿强火锅，主打麻辣鲜香，人均80元，位于静安区南京西路")
        self.assertEqual(result["source"], "text")
        self.assertEqual(result["inputType"], "text")
        self.assertIn("阿强火锅", result["project"]["name"])
        self.assertIn("麻辣", result["project"]["description"])
        self.assertEqual(result["evidence"]["opening"], result["project"]["description"])
        self.assertTrue(result["evidence"]["launchRisks"])

    def test_analyze_free_text_software(self):
        result = analyze_free_text("Source2Launch: a CLI tool that reads GitHub repos and generates social media content")
        self.assertEqual(result["source"], "text")
        self.assertIn("Source2Launch", result["project"]["name"])

    def test_analyze_target_routes_free_text(self):
        result = analyze_target("一款专为开发者设计的代码审查 AI 工具，每次 PR 自动生成评审报告")
        self.assertEqual(result["source"], "text")
        self.assertEqual(result["inputType"], "text")

    def test_analyzes_markdown_file_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "paper.md"
            doc.write_text(
                "# Better Launch Notes\n\n"
                "This paper studies how technical projects can turn source evidence into launch content.\n\n"
                "## Method\n\nWe compare README snippets, figures, and platform copy.",
                encoding="utf-8",
            )
            result = analyze_target(str(doc))

        self.assertEqual(result["source"], "file")
        self.assertEqual(result["inputType"], "document")
        self.assertEqual(result["project"]["name"], "Better Launch Notes")
        self.assertTrue(result["evidence"]["documentClips"])

    def test_analyzes_remote_url_reference_without_fetching(self):
        result = analyze_target("https://github.com/example/repo-pulse")
        self.assertIn(result["source"], ("url", "github"))
        self.assertEqual(result["project"]["name"], "repo-pulse")

    def test_parse_github_owner_repo(self):
        self.assertEqual(parse_github_owner_repo("https://github.com/openai/whisper"), ("openai", "whisper"))
        self.assertEqual(parse_github_owner_repo("https://github.com/openai/whisper.git"), ("openai", "whisper"))
        self.assertEqual(parse_github_owner_repo("https://github.com/openai/whisper/tree/main"), ("openai", "whisper"))

    def test_github_url_fetch_with_mock_server(self):
        from promoagent.analyzer import analyze_url_reference

        api_payload = {
            "name": "mock-repo",
            "description": "A mocked GitHub repo for testing",
            "topics": ["ai", "cli", "python"],
            "stargazers_count": 42,
            "default_branch": "main",
            "license": {"spdx_id": "MIT"},
            "homepage": "https://example.com",
        }
        readme_text = "# mock-repo\n\nInstall with `pip install mock-repo`.\n\n![demo](demo.gif)\n"

        server = MockGitHubServer(api_payload, readme_text)
        server.start()
        try:
            result = analyze_url_reference(
                "https://github.com/testuser/mock-repo",
                _github_api_base=server.base_url,
                _github_raw_base=server.base_url,
            )
        finally:
            server.stop()

        self.assertEqual(result["source"], "github")
        self.assertEqual(result["project"]["name"], "mock-repo")
        self.assertIn("pip install mock-repo", result["evidence"]["installCommands"])
        self.assertEqual(result["repository"]["stars"], 42)
        self.assertTrue(result["evidence"]["visuals"])

    # ------------------------------------------------------------------
    # AI (unified dispatch)
    # ------------------------------------------------------------------

    def test_parse_json_content_accepts_fenced_json(self):
        parsed = parse_json_content("```json\n{\"ok\": true}\n```")
        self.assertEqual(parsed, {"ok": True})

    def test_parse_json_content_extracts_embedded_json(self):
        parsed = parse_json_content("Here is the result: {\"a\": 1, \"b\": 2} done.")
        self.assertEqual(parsed, {"a": 1, "b": 2})

    def test_detect_provider_from_anthropic_key(self):
        self.assertEqual(_detect_provider({}, {"ANTHROPIC_API_KEY": "sk-ant-test"}), "anthropic")

    def test_detect_provider_from_gemini_key(self):
        self.assertEqual(_detect_provider({}, {"GOOGLE_API_KEY": "test-key"}), "gemini")

    def test_detect_provider_from_ollama_url(self):
        self.assertEqual(_detect_provider({}, {"OLLAMA_BASE_URL": "http://localhost:11434"}), "ollama")

    def test_detect_provider_from_modelscope_key(self):
        self.assertEqual(_detect_provider({}, {"PROMOAGENT_MODELSCOPE_API_KEY": "ms-test"}), "modelscope")

    def test_detect_provider_from_explicit_override(self):
        env = {"PROMOAGENT_PROVIDER": "anthropic", "OPENAI_API_KEY": "sk-test"}
        self.assertEqual(_detect_provider({}, env), "anthropic")

    def test_detect_provider_from_claude_model_name(self):
        self.assertEqual(_detect_provider({"model": "claude-opus-4-5"}, {}), "anthropic")

    def test_detect_provider_from_gemini_model_name(self):
        self.assertEqual(_detect_provider({"model": "gemini-2.0-flash"}, {}), "gemini")

    def test_detect_provider_defaults_to_openai(self):
        self.assertEqual(_detect_provider({}, {}), "openai")

    def test_ai_config_detects_anthropic_from_key(self):
        cfg = ai_config(options={"api_key": "sk-ant-test"}, env={})
        self.assertEqual(cfg["provider"], "anthropic")
        self.assertEqual(cfg["model"], "claude-haiku-4-5")
        self.assertTrue(cfg["apiKey"])

    def test_ai_config_explicit_provider(self):
        cfg = ai_config(options={"provider": "gemini"}, env={})
        self.assertEqual(cfg["provider"], "gemini")

    def test_ai_config_openai_default_model(self):
        cfg = ai_config(options={}, env={})
        self.assertEqual(cfg["provider"], "openai")
        self.assertEqual(cfg["model"], "gpt-4o-mini")

    def test_dispatch_chat_openai_with_mock_server(self):
        server = MockChatServer({"key": "value"})
        server.start()
        try:
            config = ai_config(options={
                "base_url": server.base_url, "api_key": "test-key",
                "model": "test-model", "provider": "openai",
            })
            content = dispatch_chat(
                [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
                config,
            )
        finally:
            server.stop()
        self.assertEqual(parse_json_content(content), {"key": "value"})

    def test_dispatch_chat_anthropic_with_mock_server(self):
        server = MockAnthropicServer(json.dumps({"key": "value"}))
        server.start()
        try:
            config = {
                "provider": "anthropic", "apiKey": "test-key",
                "baseUrl": server.base_url, "model": "claude-haiku-4-5",
                "maxTokens": 100, "temperature": 0.7, "timeout": 10,
            }
            content = dispatch_chat(
                [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
                config,
            )
        finally:
            server.stop()
        self.assertEqual(parse_json_content(content), {"key": "value"})

    def test_dispatch_chat_gemini_with_mock_server(self):
        server = MockGeminiServer(json.dumps({"gemini": "response"}))
        server.start()
        try:
            config = {
                "provider": "gemini", "apiKey": "test-key",
                "baseUrl": server.base_url, "model": "gemini-flash",
                "maxTokens": 100, "temperature": 0.7, "timeout": 10,
            }
            content = dispatch_chat(
                [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
                config,
            )
        finally:
            server.stop()
        self.assertEqual(parse_json_content(content), {"gemini": "response"})

    def test_dispatch_chat_ollama_uses_openai_compatible_endpoint(self):
        """Ollama is dispatched via the OpenAI-compatible /v1/chat/completions."""
        server = MockChatServer({"ollama": "response"})
        server.start()
        try:
            config = ai_config(options={
                "base_url": server.base_url,  # already ends with /v1
                "model": "llama3.2", "provider": "ollama",
            })
            self.assertEqual(config["provider"], "ollama")
            content = dispatch_chat(
                [{"role": "user", "content": "hi"}], config,
            )
        finally:
            server.stop()
        self.assertEqual(parse_json_content(content), {"ollama": "response"})

    def test_ai_config_ollama_appends_v1_to_bare_host(self):
        cfg = ai_config(options={"provider": "ollama", "base_url": "http://localhost:11434"})
        self.assertEqual(cfg["baseUrl"], "http://localhost:11434/v1")

    def test_ai_config_ollama_keeps_existing_v1(self):
        cfg = ai_config(options={"provider": "ollama", "base_url": "http://localhost:11434/v1"})
        self.assertEqual(cfg["baseUrl"], "http://localhost:11434/v1")

    def test_dispatch_chat_unknown_provider_raises(self):
        with self.assertRaises(ValueError):
            dispatch_chat(
                [{"role": "user", "content": "hi"}],
                {"provider": "unknown", "apiKey": "k"},
            )

    # ------------------------------------------------------------------
    # Platforms (centralized registry)
    # ------------------------------------------------------------------

    def test_get_platform_returns_spec(self):
        spec = get_platform("xiaohongshu")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.name_cn, "小红书")
        self.assertEqual(spec.aspect_ratio, "3:4")

    def test_get_platform_aliases_resolve(self):
        self.assertEqual(get_platform("xhs").key, "xiaohongshu")
        self.assertEqual(get_platform("x").key, "twitter")
        self.assertIsNone(get_platform("does-not-exist"))

    def test_to_prompt_dict_has_expected_keys(self):
        d = to_prompt_dict(get_platform("twitter"))
        self.assertEqual(set(d.keys()), {"format", "style", "length", "emoji", "tone"})

    def test_list_platforms_is_unique(self):
        plats = list_platforms()
        keys = [p.key for p in plats]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertIn("twitter", keys)
        self.assertIn("xiaohongshu", keys)

    def test_get_primary_platforms_excludes_aliases(self):
        primaries = get_primary_platforms()
        self.assertIn("xiaohongshu", primaries)
        self.assertIn("twitter", primaries)
        self.assertNotIn("xhs", primaries)
        self.assertNotIn("x", primaries)

    def test_platforms_registry_has_api_support_flag(self):
        self.assertTrue(get_platform("twitter").api_support)
        self.assertFalse(get_platform("xiaohongshu").api_support)

    # ------------------------------------------------------------------
    # Pipeline: state + source id
    # ------------------------------------------------------------------

    def test_pipeline_state_set_get_has_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("src-1", cache_dir=Path(tmp))
            self.assertFalse(state.has("research"))
            state.set("research", {"data": {"x": 1}})
            self.assertTrue(state.has("research"))
            self.assertEqual(state.get("research")["data"]["x"], 1)
            state.clear()
            self.assertFalse(state.has("research"))

    def test_pipeline_state_persists_across_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            state1 = PipelineState("src-2", cache_dir=Path(tmp))
            state1.set("research", {"data": {"v": 42}})
            state2 = PipelineState("src-2", cache_dir=Path(tmp))
            self.assertTrue(state2.has("research"))
            self.assertEqual(state2.get("research")["data"]["v"], 42)

    def test_pipeline_state_save_is_atomic(self):
        """save() must not leave a .tmp file behind or a truncated state file."""
        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("atomic-src", cache_dir=Path(tmp))
            state.set("research", {"data": {"big": "x" * 10_000}})
            state_file = state.state_file
            # No leftover temp files after save.
            tmp_files = list(state_file.parent.glob("*.tmp"))
            self.assertEqual(tmp_files, [], "atomic save must clean up the temp file")
            # The state file itself is valid JSON (not truncated mid-write).
            saved = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["source_id"], "atomic-src")

    def test_source_id_is_stable_and_distinct(self):
        result_a = {"target": "a", "project": {"name": "A"}}
        result_b = {"target": "b", "project": {"name": "B"}}
        id_a = _source_id(result_a)
        self.assertEqual(_source_id(result_a), id_a)
        self.assertNotEqual(_source_id(result_b), id_a)

    # ------------------------------------------------------------------
    # Pipeline: stage_research
    # ------------------------------------------------------------------

    def test_stage_research_parses_and_caches(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        calls = []

        def fake_dispatch(messages, config):
            calls.append(messages)
            return json.dumps(_research_payload(), ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("research-src", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch), \
                 patch.object(pipeline, "find_examples", lambda result_arg, **kw: []):
                out1 = stage_research(result, state, options={"api_key": "k"})
                out2 = stage_research(result, state)  # should hit cache

        self.assertEqual(out1["stage"], "research")
        self.assertEqual(out1["data"]["facts"]["core_claim"], "一句话核心主张")
        self.assertEqual(out1["data"]["strategy"]["recommended_platforms"], ["xiaohongshu", "twitter"])
        self.assertEqual(out2, out1)
        self.assertEqual(len(calls), 1, "cached second call should not dispatch")

    def test_stage_research_force_bypasses_cache(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        calls = []

        def fake_dispatch(messages, config):
            calls.append(messages)
            return json.dumps(_research_payload(), ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("research-force", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch), \
                 patch.object(pipeline, "find_examples", lambda result_arg, **kw: []):
                stage_research(result, state, options={"api_key": "k"})
                stage_research(result, state, force=True)
        self.assertEqual(len(calls), 2)

    def test_stage_research_injects_references(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        refs = ["【爆款案例】\n这是参考广告内容"]
        captured = {}

        def fake_dispatch(messages, config):
            captured["user_prompt"] = messages[-1]["content"]
            return json.dumps(_research_payload(), ensure_ascii=False)

        def fake_find(result_arg, **kwargs):
            return refs

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("research-refs", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch), \
                 patch.object(pipeline, "find_examples", fake_find):
                out = stage_research(result, state, options={"api_key": "k"})

        self.assertTrue(state.has("references"))
        self.assertEqual(state.get("references")["examples"], refs)
        self.assertEqual(state.get("references")["source"], "search")
        self.assertIn("参考广告/示例", captured["user_prompt"])
        self.assertIn("这是参考广告内容", captured["user_prompt"])

    def test_stage_research_injects_raw_evidence(self):
        """research prompt surfaces proof_points / key_actions / headings from the analyzer."""
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        # Inject extra evidence fields to verify they reach the prompt.
        result["evidence"]["proofPoints"] = ["支持 X 的数据", "Y 案例"]
        result["evidence"]["keyActions"] = ["npm install", "运行 init"]
        result["evidence"]["headings"] = [
            {"level": 2, "text": "Features"}, {"level": 2, "text": "Install"},
        ]
        captured = {}

        def fake_dispatch(messages, config):
            captured["user_prompt"] = messages[-1]["content"]
            return json.dumps(_research_payload(), ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("research-evidence", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch), \
                 patch.object(pipeline, "find_examples", lambda r, **kw: []):
                stage_research(result, state, options={"api_key": "k"})
        # The source_summary JSON in the prompt must carry the raw evidence.
        self.assertIn("proof_points", captured["user_prompt"])
        self.assertIn("支持 X 的数据", captured["user_prompt"])
        self.assertIn("key_actions", captured["user_prompt"])
        self.assertIn("npm install", captured["user_prompt"])
        self.assertIn("Features", captured["user_prompt"])

    def test_stage_research_no_search_skips_find(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        find_calls = []

        def fake_find(result_arg, **kwargs):
            find_calls.append(kwargs)
            return []

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("research-nosearch", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat",
                              lambda m, c: json.dumps(_research_payload(), ensure_ascii=False)), \
                 patch.object(pipeline, "find_examples", fake_find):
                stage_research(result, state, options={"api_key": "k"}, search=False)

        self.assertEqual(find_calls, [], "find_examples must not be called with search=False")
        self.assertEqual(state.get("references")["source"], "disabled")
        self.assertFalse(state.get("references")["searched"])

    def test_stage_research_find_failure_is_silent(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)

        def boom(result_arg, **kwargs):
            raise RuntimeError("network down")

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("research-fail", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat",
                              lambda m, c: json.dumps(_research_payload(), ensure_ascii=False)), \
                 patch.object(pipeline, "find_examples", boom):
                out = stage_research(result, state, options={"api_key": "k"})

        # Research still completes; references empty but recorded.
        self.assertEqual(out["stage"], "research")
        self.assertEqual(state.get("references")["examples"], [])
        self.assertTrue(state.get("references")["searched"])

    def test_stage_research_cache_hit_no_search(self):
        """Cached research must not re-run find_examples."""
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        find_calls = []

        def fake_find(result_arg, **kwargs):
            find_calls.append(kwargs)
            return []

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("research-cache", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat",
                              lambda m, c: json.dumps(_research_payload(), ensure_ascii=False)), \
                 patch.object(pipeline, "find_examples", fake_find):
                stage_research(result, state, options={"api_key": "k"})
                stage_research(result, state)  # cache hit
        self.assertEqual(len(find_calls), 1, "cache hit should not re-search")

    # ------------------------------------------------------------------
    # Pipeline: stage_blueprint
    # ------------------------------------------------------------------

    def test_stage_blueprint_enriches_elements(self):
        research = {"data": _research_payload()}
        result = {"project": {"name": "Test"}}

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("blueprint-src", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat",
                              lambda m, c: json.dumps(_blueprint_payload(), ensure_ascii=False)):
                out = stage_blueprint(research, state, result, options={"api_key": "k"})

        elements = out["data"]["elements"]
        self.assertEqual(out["stage"], "blueprint")
        self.assertTrue(all(e["editable"] for e in elements))
        hook = next(e for e in elements if e["id"] == "hook-main")
        self.assertEqual(len(hook["variants"]), 3, "variants should be capped at 3")

    def test_stage_blueprint_caches(self):
        research = {"data": _research_payload()}
        result = {"project": {"name": "Test"}}
        calls = []

        def fake_dispatch(m, c):
            calls.append(m)
            return json.dumps(_blueprint_payload(), ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("blueprint-cache", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                stage_blueprint(research, state, result, options={"api_key": "k"})
                stage_blueprint(research, state, result)
        self.assertEqual(len(calls), 1)

    def test_stage_blueprint_reads_clarifications(self):
        research = {"data": _research_payload()}
        result = {"project": {"name": "Test"}}
        captured = {}

        def fake_dispatch(m, c):
            captured["prompt"] = m[-1]["content"]
            return json.dumps(_blueprint_payload(), ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("bp-clar", cache_dir=Path(tmp))
            state.set("clarifications", {"answers": {"目标用户是谁": "独立开发者"}, "timestamp": 0})
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                stage_blueprint(research, state, result, options={"api_key": "k"})

        self.assertIn("用户补充信息", captured["prompt"])
        self.assertIn("独立开发者", captured["prompt"])
        self.assertIn("目标用户是谁", captured["prompt"])

    def test_stage_blueprint_no_clarifications_omits_block(self):
        research = {"data": _research_payload()}
        result = {"project": {"name": "Test"}}
        captured = {}

        def fake_dispatch(m, c):
            captured["prompt"] = m[-1]["content"]
            return json.dumps(_blueprint_payload(), ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("bp-noclar", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                stage_blueprint(research, state, result, options={"api_key": "k"})

        self.assertNotIn("用户补充信息", captured["prompt"])

    def test_stage_blueprint_reads_references(self):
        research = {"data": _research_payload()}
        result = {"project": {"name": "Test"}}
        captured = {}

        def fake_dispatch(m, c):
            captured["prompt"] = m[-1]["content"]
            return json.dumps(_blueprint_payload(), ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("bp-refs", cache_dir=Path(tmp))
            state.set("references", {"examples": ["【案例】\n参考广告正文"], "searched": True,
                                     "source": "search", "timestamp": 0})
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                stage_blueprint(research, state, result, options={"api_key": "k"})

        self.assertIn("参考广告/示例", captured["prompt"])
        self.assertIn("参考广告正文", captured["prompt"])

    # ------------------------------------------------------------------
    # Pipeline: blueprint editing
    # ------------------------------------------------------------------

    def _make_blueprint(self) -> dict:
        return {
            "data": {
                "elements": [
                    {"id": "a", "content": "A", "variants": ["v1", "v2"]},
                    {"id": "b", "content": "B", "variants": []},
                ],
                "structure": {"alternative_structures": []},
            }
        }

    def test_edit_blueprint_updates_content(self):
        edited = edit_blueprint(self._make_blueprint(), {"a": "new A"})
        self.assertEqual(edited["data"]["elements"][0]["content"], "new A")
        self.assertTrue(edited["data"]["elements"][0]["edited"])
        self.assertTrue(edited["data"]["edit_history"])

    def test_edit_blueprint_select_variant(self):
        edited = edit_blueprint(self._make_blueprint(), {"_selectVariant": {"a": 1}})
        self.assertEqual(edited["data"]["elements"][0]["content"], "v2")
        self.assertEqual(edited["data"]["elements"][0]["selected_variant"], 1)

    def test_edit_blueprint_variant_out_of_range_is_noop(self):
        edited = edit_blueprint(self._make_blueprint(), {"_selectVariant": {"a": 9}})
        self.assertEqual(edited["data"]["elements"][0]["content"], "A")

    def test_edit_blueprint_reorder(self):
        edited = edit_blueprint(self._make_blueprint(), {"_reorder": ["b", "a"]})
        self.assertEqual([e["id"] for e in edited["data"]["elements"]], ["b", "a"])

    def test_edit_blueprint_remove_element(self):
        edited = edit_blueprint(self._make_blueprint(), {"_removeElement": "a"})
        self.assertEqual([e["id"] for e in edited["data"]["elements"]], ["b"])

    def test_edit_blueprint_add_element(self):
        edited = edit_blueprint(self._make_blueprint(), {
            "_addElement": {"id": "c", "content": "C", "type": "story"}
        })
        ids = [e["id"] for e in edited["data"]["elements"]]
        self.assertIn("c", ids)
        self.assertTrue(next(e for e in edited["data"]["elements"] if e["id"] == "c")["editable"])

    def test_edit_blueprint_set_structure(self):
        bp = {
            "data": {
                "elements": [
                    {"id": "hook", "content": "H"},
                    {"id": "story", "content": "S"},
                    {"id": "cta", "content": "C"},
                ],
                "structure": {
                    "alternative_structures": [
                        {"name": "故事型", "order": ["hook", "story", "cta"]},
                    ],
                },
            }
        }
        edited = edit_blueprint(bp, {"_setStructure": "故事型"})
        self.assertEqual([e["id"] for e in edited["data"]["elements"]], ["hook", "story", "cta"])

    def test_preview_blueprint_markdown(self):
        blueprint = {
            "data": {
                "source": {"project_name": "Test"},
                "positioning": {"one_liner": "定位"},
                "elements": [
                    {"label": "Hook", "content": "Hello", "variants": []},
                    {"label": "Empty", "content": "", "variants": []},
                ],
                "metrics": {"estimated_read_time": "30s", "emotion_profile": "neutral"},
            }
        }
        out = preview_blueprint(blueprint)
        self.assertIn("# Test", out)
        self.assertIn("**定位**: 定位", out)
        self.assertIn("## Hook", out)
        self.assertIn("Hello", out)
        self.assertNotIn("## Empty", out)

    def test_preview_blueprint_plain_format(self):
        blueprint = {
            "data": {
                "elements": [{"content": "First"}, {"content": "Second"}],
            }
        }
        out = preview_blueprint(blueprint, format="plain")
        self.assertEqual(out, "First\n\nSecond")

    # ------------------------------------------------------------------
    # Pipeline: stage_produce
    # ------------------------------------------------------------------

    def test_stage_produce_generates_each_platform(self):
        blueprint = {"data": {"positioning": {"one_liner": "L"},
                              "elements": [{"label": "Hook", "content": "Hello"}]}}
        research = {"data": {}}

        def fake_dispatch(messages, config):
            return json.dumps({"platform": "x", "markdown": "content", "hashtags": []},
                              ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("produce-src", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                out = stage_produce(
                    blueprint, research, state, options={"api_key": "k"},
                    platforms=["xiaohongshu", "twitter"], parallel=False,
                )

        self.assertEqual(out["stage"], "produce")
        self.assertIn("xiaohongshu", out["data"])
        self.assertIn("twitter", out["data"])
        self.assertEqual(out["platforms"], ["xiaohongshu", "twitter"])

    def test_stage_produce_caches(self):
        blueprint = {"data": {"positioning": {"one_liner": "L"},
                              "elements": [{"label": "Hook", "content": "Hello"}]}}
        research = {"data": {}}
        calls = []

        def fake_dispatch(m, c):
            calls.append(m)
            return json.dumps({"markdown": "x"}, ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("produce-cache", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                stage_produce(blueprint, research, state, options={"api_key": "k"},
                              platforms=["twitter"], parallel=False)
                stage_produce(blueprint, research, state, platforms=["twitter"], parallel=False)
        self.assertEqual(len(calls), 1)

    # ------------------------------------------------------------------
    # Pipeline: quality modes (facts / playbook / few-shot / critic)
    # ------------------------------------------------------------------

    def _produce_capture(self, research_data, quality_mode, references=None):
        """Run produce with a dispatch mock that captures the prompt; return (calls, captured_prompt, captured_system)."""
        blueprint = {"data": {"positioning": {"one_liner": "L"},
                              "elements": [{"label": "Hook", "content": "Hello"}]}}
        calls = []
        captured = {"user": "", "system": ""}

        def fake_dispatch(m, c):
            calls.append(m)
            captured["system"] = m[0]["content"]
            captured["user"] = m[-1]["content"]
            return json.dumps({"markdown": "内容", "hashtags": []}, ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState(f"produce-{quality_mode}", cache_dir=Path(tmp))
            if references is not None:
                state.set("references", {"examples": references, "searched": True, "source": "search", "timestamp": 0})
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                stage_produce(blueprint, {"data": research_data}, state,
                              options={"api_key": "k", "quality_mode": quality_mode},
                              platforms=["xiaohongshu"], parallel=False)
        return calls, captured

    def test_produce_injects_facts(self):
        research_data = {"facts": {"core_claim": "测试主张", "key_facts": ["事实A", "事实B"]}}
        calls, captured = self._produce_capture(research_data, "fast")
        self.assertIn("事实A", captured["user"])
        self.assertIn("关键事实", captured["user"])

    def test_balanced_injects_playbook(self):
        research_data = {"facts": {"key_facts": ["x"]}}
        _, captured = self._produce_capture(research_data, "balanced")
        self.assertIn("平台法则", captured["system"])
        self.assertIn("前3行", captured["system"])  # xiaohongshu opening_rule

    def test_fast_omits_playbook(self):
        research_data = {"facts": {}}
        _, captured = self._produce_capture(research_data, "fast")
        self.assertNotIn("平台法则", captured["system"])

    def test_produce_injects_references(self):
        research_data = {"facts": {}}
        _, captured = self._produce_capture(research_data, "balanced", references=["【案例】\n参考广告正文"])
        self.assertIn("参考广告正文", captured["user"])
        self.assertIn("参考广告/示例", captured["user"])

    def test_produce_empty_references_no_crash(self):
        research_data = {"facts": {}}
        _, captured = self._produce_capture(research_data, "balanced", references=[])
        self.assertNotIn("参考广告/示例", captured["user"])

    def test_fast_mode_one_call_per_platform(self):
        research_data = {"facts": {"key_facts": ["x"]}}
        calls, _ = self._produce_capture(research_data, "fast")
        self.assertEqual(len(calls), 1, "fast mode must make exactly 1 call per platform")

    def test_critic_low_score_triggers_rewrite(self):
        blueprint = {"data": {"positioning": {"one_liner": "L"},
                              "elements": [{"label": "Hook", "content": "Hello"}]}}
        research = {"data": {"facts": {"key_facts": ["事实1"]}}}
        call_count = {"n": 0}

        def fake_dispatch(m, c):
            call_count["n"] += 1
            if call_count["n"] == 1:  # generate
                return json.dumps({"markdown": "空话连篇"}, ensure_ascii=False)
            if call_count["n"] == 2:  # critic
                return json.dumps({"scores": {"fidelity": 2, "engagement": 2, "alignment": 3},
                                   "issues": ["无事实"], "improvements": ["补事实"]}, ensure_ascii=False)
            return json.dumps({"markdown": "修正后含事实"}, ensure_ascii=False)  # rewrite

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("produce-critic-low", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                out = stage_produce(blueprint, research, state,
                                    options={"api_key": "k", "quality_mode": "polished"},
                                    platforms=["xiaohongshu"], parallel=False)
        self.assertEqual(call_count["n"], 3, "polished+low score → generate+critic+rewrite")
        content = out["data"]["xiaohongshu"]
        self.assertTrue(content["_meta"]["rewritten"])
        self.assertEqual(content["_meta"]["critique"]["total"], 7)

    def test_critic_high_score_skips_rewrite(self):
        blueprint = {"data": {"positioning": {"one_liner": "L"},
                              "elements": [{"label": "Hook", "content": "Hello"}]}}
        research = {"data": {"facts": {"key_facts": ["事实1"]}}}
        call_count = {"n": 0}

        def fake_dispatch(m, c):
            call_count["n"] += 1
            if call_count["n"] == 1:  # generate
                return json.dumps({"markdown": "高质量内容"}, ensure_ascii=False)
            return json.dumps({"scores": {"fidelity": 5, "engagement": 5, "alignment": 5},
                               "issues": [], "improvements": []}, ensure_ascii=False)  # critic

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("produce-critic-high", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                out = stage_produce(blueprint, research, state,
                                    options={"api_key": "k", "quality_mode": "polished"},
                                    platforms=["xiaohongshu"], parallel=False)
        self.assertEqual(call_count["n"], 2, "high score → generate+critic only")
        self.assertFalse(out["data"]["xiaohongshu"]["_meta"]["rewritten"])

    def test_quality_mode_change_bypasses_cache(self):
        blueprint = {"data": {"positioning": {"one_liner": "L"},
                              "elements": [{"label": "Hook", "content": "Hello"}]}}
        research = {"data": {"facts": {}}}
        calls = []

        def fake_dispatch(m, c):
            calls.append(m)
            return json.dumps({"markdown": "x"}, ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("produce-modechange", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                stage_produce(blueprint, research, state,
                              options={"api_key": "k", "quality_mode": "balanced"},
                              platforms=["twitter"], parallel=False)
                stage_produce(blueprint, research, state,
                              options={"api_key": "k", "quality_mode": "fast"},
                              platforms=["twitter"], parallel=False)
        self.assertEqual(len(calls), 2, "mode change must bypass cache")

    def test_produce_respects_blueprint_structure_order(self):
        """produce orders elements by blueprint.structure.recommended_order."""
        blueprint = {"data": {
            "positioning": {"one_liner": "L"},
            "elements": [
                {"id": "hook", "label": "Hook", "content": "钩子"},
                {"id": "solution", "label": "Solution", "content": "方案"},
                {"id": "cta", "label": "CTA", "content": "行动"},
            ],
            "structure": {"recommended_order": ["cta", "hook", "solution"]},
        }}
        research = {"data": {"facts": {}}}
        captured = {}

        def fake_dispatch(m, c):
            captured["user"] = m[-1]["content"]
            return json.dumps({"markdown": "x"}, ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("produce-order", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                stage_produce(blueprint, research, state,
                              options={"api_key": "k", "quality_mode": "fast"},
                              platforms=["xiaohongshu"], parallel=False)
        # Elements text in the prompt must follow the reordered sequence.
        user = captured["user"]
        cta_pos = user.find("行动")
        hook_pos = user.find("钩子")
        sol_pos = user.find("方案")
        self.assertLess(cta_pos, hook_pos, "cta should come before hook")
        self.assertLess(hook_pos, sol_pos, "hook should come before solution")

    def test_produce_appends_unordered_elements(self):
        """Elements not in recommended_order are appended at the end."""
        blueprint = {"data": {
            "positioning": {"one_liner": "L"},
            "elements": [
                {"id": "a", "label": "A", "content": "AAA"},
                {"id": "b", "label": "B", "content": "BBB"},
                {"id": "c", "label": "C", "content": "CCC"},  # not in order
            ],
            "structure": {"recommended_order": ["b", "a"]},
        }}
        research = {"data": {"facts": {}}}
        captured = {}

        def fake_dispatch(m, c):
            captured["user"] = m[-1]["content"]
            return json.dumps({"markdown": "x"}, ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("produce-append", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                stage_produce(blueprint, research, state,
                              options={"api_key": "k", "quality_mode": "fast"},
                              platforms=["xiaohongshu"], parallel=False)
        user = captured["user"]
        self.assertLess(user.find("BBB"), user.find("AAA"))
        self.assertLess(user.find("AAA"), user.find("CCC"))

    # ------------------------------------------------------------------
    # Pipeline: cross-stage backflow (cascade invalidation + critic routing)
    # ------------------------------------------------------------------

    def test_is_stale_detects_upstream_change(self):
        """blueprint cache is stale after research is regenerated."""
        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("stale-test", cache_dir=Path(tmp))
            # Simulate research + blueprint built together.
            state.set("research", {"timestamp": 1000.0, "data": {}})
            state.set("blueprint", {"timestamp": 1001.0, "data": {},
                                    "_upstream": {"research": 1000.0}})
            self.assertFalse(state.is_stale("blueprint", "research"))
            # Regenerate research → blueprint now stale.
            state.set("research", {"timestamp": 2000.0, "data": {}})
            self.assertTrue(state.is_stale("blueprint", "research"))

    def test_is_stale_no_upstream_field_returns_false(self):
        """Old caches without _upstream tolerate (no forced recompute)."""
        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("stale-old", cache_dir=Path(tmp))
            state.set("research", {"timestamp": 1000.0, "data": {}})
            state.set("blueprint", {"timestamp": 1001.0, "data": {}})  # no _upstream
            self.assertFalse(state.is_stale("blueprint", "research"))

    def test_critic_returns_classified_issues(self):
        """critic propagates classified_issues + primary_problem_type from the model."""
        blueprint = {"data": {"positioning": {"one_liner": "L"},
                              "elements": [{"id": "hook", "label": "Hook", "content": "H"}]}}
        research = {"data": {"facts": {"key_facts": ["x"]}}}
        call_count = {"n": 0}

        def fake_dispatch(m, c):
            call_count["n"] += 1
            if call_count["n"] == 1:  # generate
                return json.dumps({"markdown": "内容"}, ensure_ascii=False)
            # critic
            return json.dumps({
                "scores": {"fidelity": 2, "engagement": 4, "alignment": 4},
                "classified_issues": [{"type": "fact_insufficient",
                                       "description": "缺数据", "suggested_edit": None}],
                "primary_problem_type": "fact_insufficient",
                "issues": ["缺数据"], "improvements": ["补数据"],
            }, ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("critic-classified", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                out = stage_produce(blueprint, research, state,
                                    options={"api_key": "k", "quality_mode": "polished"},
                                    platforms=["xiaohongshu"], parallel=False)
        meta = out["data"]["xiaohongshu"].get("_meta", {})
        self.assertEqual(meta["critique"]["primary_problem_type"], "fact_insufficient")

    def test_critic_missing_classified_degrades_to_expression_weak(self):
        """No classified_issues → expression_weak (preserves rewrite-only behavior)."""
        from promoagent.pipeline import _critic_platform
        captured = {}

        def fake_dispatch(m, c):
            captured["resp"] = m[-1]["content"]
            # Old-style critic output: no classified_issues / primary_problem_type.
            return json.dumps({"scores": {"fidelity": 2, "engagement": 2, "alignment": 3},
                               "issues": ["x"], "improvements": ["y"]}, ensure_ascii=False)

        with patch.object(pipeline, "dispatch_chat", fake_dispatch):
            critique = _critic_platform("xiaohongshu", {"markdown": "x"},
                                        {"facts": {}}, {"style": "s", "tone": "t"},
                                        {"api_key": "k"})
        self.assertEqual(critique["primary_problem_type"], "expression_weak")

    def test_critic_prompt_problem_types_match_constant(self):
        """The prompt's problem-type lists must equal _CRITIC_PROBLEM_TYPES —
        if they drift, the critic's stated types and the normalization gate
        can disagree on what's a valid backflow trigger."""
        from promoagent.pipeline import _build_critic_user_prompt, _CRITIC_PROBLEM_TYPES, _CRITIC_PRIMARY_TYPES
        prompt = _build_critic_user_prompt("xiaohongshu", {"markdown": "x"}, "", {"style": "s"})
        self.assertIn("|".join(_CRITIC_PROBLEM_TYPES), prompt)
        self.assertIn("|".join(_CRITIC_PRIMARY_TYPES), prompt)

    def test_backflow_expression_weak_uses_rewrite(self):
        """expression_weak → produce-only rewrite, no upstream rerun."""
        blueprint = {"data": {"positioning": {"one_liner": "L"},
                              "elements": [{"id": "hook", "label": "Hook", "content": "H"}]}}
        research = {"data": {"facts": {"key_facts": ["x"]}}}
        call_count = {"n": 0}

        def fake_dispatch(m, c):
            call_count["n"] += 1
            if call_count["n"] == 1:  # generate
                return json.dumps({"markdown": "弱内容"}, ensure_ascii=False)
            if call_count["n"] == 2:  # critic
                return json.dumps({
                    "scores": {"fidelity": 4, "engagement": 2, "alignment": 4},
                    "classified_issues": [{"type": "expression_weak", "description": "开头弱"}],
                    "primary_problem_type": "expression_weak",
                    "issues": ["开头弱"], "improvements": ["改开头"],
                }, ensure_ascii=False)
            return json.dumps({"markdown": "改后内容"}, ensure_ascii=False)  # rewrite

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("backflow-expr", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                out = stage_produce(blueprint, research, state,
                                    options={"api_key": "k", "quality_mode": "polished"},
                                    platforms=["xiaohongshu"], parallel=False)
        # generate + critic + rewrite = 3 calls; no research rerun.
        self.assertEqual(call_count["n"], 3)
        meta = out["data"]["xiaohongshu"]["_meta"]
        self.assertTrue(meta["rewritten"])
        self.assertIsNone(meta["backflow"])

    def test_backflow_structure_issue_calls_edit_blueprint(self):
        """structure_issue → edit_blueprint applied + platform regenerated."""
        blueprint = {"data": {
            "positioning": {"one_liner": "L"},
            "elements": [
                {"id": "hook-main", "label": "Hook", "content": "旧钩子", "variants": ["v1", "v2", "v3"]},
                {"id": "cta-main", "label": "CTA", "content": "行动"},
            ],
            "structure": {"recommended_order": ["hook-main", "cta-main"]},
        }}
        research = {"data": {"facts": {"key_facts": ["x"]}}}
        call_count = {"n": 0}

        def fake_dispatch(m, c):
            call_count["n"] += 1
            if call_count["n"] == 1:  # generate
                return json.dumps({"markdown": "内容"}, ensure_ascii=False)
            if call_count["n"] == 2:  # critic
                return json.dumps({
                    "scores": {"fidelity": 4, "engagement": 4, "alignment": 2},
                    "classified_issues": [{"type": "structure_issue", "description": "钩子不对",
                                           "suggested_edit": {"_selectVariant": {"hook-main": 1}}}],
                    "primary_problem_type": "structure_issue",
                    "issues": ["钩子不对"], "improvements": ["用变体2"],
                }, ensure_ascii=False)
            if call_count["n"] == 3:  # regenerate platform (balanced, no critic)
                return json.dumps({"markdown": "用v2后内容"}, ensure_ascii=False)
            # call 4: final critic
            return json.dumps({"scores": {"fidelity": 5, "engagement": 5, "alignment": 5},
                               "issues": [], "improvements": []}, ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("backflow-struct", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                out = stage_produce(blueprint, research, state,
                                    options={"api_key": "k", "quality_mode": "polished"},
                                    platforms=["xiaohongshu"], parallel=False)
        meta = out["data"]["xiaohongshu"]["_meta"]
        self.assertIsNotNone(meta["backflow"])
        self.assertEqual(meta["backflow"]["stage"], "blueprint")
        self.assertEqual(meta["backflow"]["pre_backflow_score"], 10)
        self.assertEqual(call_count["n"], 4)

    def test_backflow_fact_insufficient_reruns_research(self):
        """fact_insufficient (with state+result) → research+blueprint rerun → platform regenerated."""
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        blueprint = {"data": {"positioning": {"one_liner": "L"},
                              "elements": [{"id": "hook", "label": "Hook", "content": "H"}]}}
        research = {"data": {"facts": {"key_facts": ["x"]}}}
        call_count = {"n": 0}

        def fake_dispatch(m, c):
            call_count["n"] += 1
            user = m[-1]["content"] if m else ""
            # critic — check first; its prompt contains "平台规格" too.
            if "评审以下" in user or "待评内容" in user:
                return json.dumps({
                    "scores": {"fidelity": 2, "engagement": 4, "alignment": 4},
                    "classified_issues": [{"type": "fact_insufficient", "description": "缺数据"}],
                    "primary_problem_type": "fact_insufficient",
                    "issues": ["缺数据"], "improvements": ["补数据"],
                }, ensure_ascii=False)
            # produce (generate or regenerate)
            if "转换为" in user or "平台规格" in user:
                return json.dumps({"markdown": f"内容{call_count['n']}"}, ensure_ascii=False)
            # research rerun (contains "推广策略")
            if "推广策略" in user or "research" in user.lower():
                return json.dumps({"facts": {"core_claim": "补充后主张", "key_facts": ["新事实"], "gaps": []},
                                   "strategy": {"recommended_platforms": ["xiaohongshu"],
                                                "positioning": {"one_liner": "L", "promise": "p", "differentiator": "d"},
                                                "creative_direction": {"main_hook": "h", "hook_variants": [], "tone": "t", "key_message": "m"}}},
                                  ensure_ascii=False)
            if "内容元素" in user or "Blueprint" in user:  # blueprint rerun
                return json.dumps({"version": "2.0", "elements": [{"id": "hook", "label": "Hook", "content": "新钩子"}],
                                   "positioning": {"one_liner": "L"}, "structure": {}, "metrics": {}}, ensure_ascii=False)
            return json.dumps({"markdown": "fallback"})

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("backflow-fact", cache_dir=Path(tmp))
            state.set("research", research)  # so stage_produce sees existing research
            state.set("blueprint", blueprint)
            with patch.object(pipeline, "dispatch_chat", fake_dispatch), \
                 patch.object(pipeline, "find_examples", lambda r, **kw: []):
                out = stage_produce(blueprint, research, state,
                                    options={"api_key": "k", "quality_mode": "polished"},
                                    platforms=["xiaohongshu"], parallel=False,
                                    result=result)
        meta = out["data"]["xiaohongshu"]["_meta"]
        self.assertEqual(meta["backflow"]["stage"], "research")
        self.assertGreater(call_count["n"], 4, "fact_insufficient should trigger research+blueprint+produce rerun")

    def test_backflow_no_recursion(self):
        """After a backflow, a second low-score critic does NOT trigger another backflow."""
        blueprint = {"data": {"positioning": {"one_liner": "L"},
                              "elements": [{"id": "hook", "label": "Hook", "content": "H"}]}}
        research = {"data": {"facts": {"key_facts": ["x"]}}}
        call_count = {"n": 0}

        def fake_dispatch(m, c):
            call_count["n"] += 1
            if call_count["n"] == 1:  # generate
                return json.dumps({"markdown": "x"}, ensure_ascii=False)
            if call_count["n"] == 2:  # first critic → structure_issue
                return json.dumps({
                    "scores": {"fidelity": 4, "engagement": 4, "alignment": 2},
                    "classified_issues": [{"type": "structure_issue", "description": "结构",
                                           "suggested_edit": {"_selectVariant": {"hook": 0}}}],
                    "primary_problem_type": "structure_issue",
                    "issues": ["结构"], "improvements": ["调"],
                }, ensure_ascii=False)
            if call_count["n"] == 3:  # regenerate
                return json.dumps({"markdown": "regen"}, ensure_ascii=False)
            # call 4: final critic — still low, but must NOT trigger another backflow.
            return json.dumps({
                "scores": {"fidelity": 4, "engagement": 4, "alignment": 2},
                "classified_issues": [{"type": "structure_issue", "description": "仍差"}],
                "primary_problem_type": "structure_issue",
                "issues": ["仍差"], "improvements": ["再调"],
            }, ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("backflow-norecurse", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                out = stage_produce(blueprint, research, state,
                                    options={"api_key": "k", "quality_mode": "polished"},
                                    platforms=["xiaohongshu"], parallel=False)
        # generate + critic + regen + final_critique = 4 calls (no 2nd backflow).
        self.assertEqual(call_count["n"], 4)
        self.assertEqual(out["data"]["xiaohongshu"]["_meta"]["backflow"]["stage"], "blueprint")

    def test_backflow_parallel_multiplatform_correctness(self):
        """Parallel polished produce with backflow on multiple platforms must
        not corrupt state AND each platform must receive its own distinct
        regenerated content — not a copy of the other platform's result.

        Exercises the RLock around PipelineState.set/get and verifies the
        backflow didn't cross-wire platforms (the last-writer-wins concern on
        the shared research/blueprint state)."""
        blueprint = {"data": {"positioning": {"one_liner": "L"},
                              "elements": [{"id": "hook", "label": "Hook", "content": "H",
                                            "variants": ["v1", "v2"]}]}}
        research = {"data": {"facts": {"key_facts": ["x"]}}}
        result = analyze_target("healthy-repo", cwd=FIXTURES)

        def fake_dispatch(m, c):
            user = m[-1]["content"] if m else ""
            if "评审以下" in user or "待评内容" in user:
                return json.dumps({
                    "scores": {"fidelity": 4, "engagement": 4, "alignment": 2},
                    "classified_issues": [{"type": "structure_issue", "description": "结构",
                                           "suggested_edit": {"_selectVariant": {"hook": 1}}}],
                    "primary_problem_type": "structure_issue",
                    "issues": ["结构"], "improvements": ["调"],
                }, ensure_ascii=False)
            # Produce output is tagged with the platform name from the prompt,
            # so we can tell each platform got its own regeneration.
            for plat in ("xiaohongshu", "twitter"):
                if plat in user:
                    return json.dumps({"markdown": f"内容-{plat}"}, ensure_ascii=False)
            return json.dumps({"markdown": "fallback"}, ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("backflow-parallel", cache_dir=Path(tmp))
            state.set("research", research)
            state.set("blueprint", blueprint)
            with patch.object(pipeline, "dispatch_chat", fake_dispatch), \
                 patch.object(pipeline, "find_examples", lambda r, **kw: []):
                out = stage_produce(blueprint, research, state,
                                    options={"api_key": "k", "quality_mode": "polished"},
                                    platforms=["xiaohongshu", "twitter"], parallel=True,
                                    result=result)
        # Both platforms produced content; no crash, no corruption.
        self.assertIn("xiaohongshu", out["data"])
        self.assertIn("twitter", out["data"])
        for plat in ("xiaohongshu", "twitter"):
            content = out["data"][plat]
            self.assertNotIn("error", content)
            # Each platform's regenerated markdown carries its own tag —
            # verifies backflow didn't cross-wire the two platforms.
            self.assertIn(plat, content["markdown"],
                          f"{plat} must receive its own regenerated content, not the other's")
            # Backflow was attempted (structure_issue → edit_blueprint).
            self.assertEqual(content["_meta"]["backflow"]["stage"], "blueprint")

    def test_backflow_result_none_degrades_to_expression_weak(self):
        """Without result, fact_insufficient can't rerun research → expression_weak."""
        blueprint = {"data": {"positioning": {"one_liner": "L"},
                              "elements": [{"id": "hook", "label": "Hook", "content": "H"}]}}
        research = {"data": {"facts": {"key_facts": ["x"]}}}
        call_count = {"n": 0}

        def fake_dispatch(m, c):
            call_count["n"] += 1
            user = m[-1]["content"] if m else ""
            if "评审以下" in user or "待评内容" in user:
                return json.dumps({
                    "scores": {"fidelity": 2, "engagement": 4, "alignment": 4},
                    "classified_issues": [{"type": "fact_insufficient", "description": "缺数据"}],
                    "primary_problem_type": "fact_insufficient",
                    "issues": ["缺数据"], "improvements": ["补数据"],
                }, ensure_ascii=False)
            if "评审发现以下问题" in (m[-1]["content"] if m else ""):
                return json.dumps({"markdown": "rewrite"}, ensure_ascii=False)
            return json.dumps({"markdown": "内容"}, ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("backflow-noresult", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                # result=None → fact_insufficient degrades to expression_weak rewrite.
                out = stage_produce(blueprint, research, state,
                                    options={"api_key": "k", "quality_mode": "polished"},
                                    platforms=["xiaohongshu"], parallel=False, result=None)
        meta = out["data"]["xiaohongshu"]["_meta"]
        # No research backflow (result missing); rewrote produce instead.
        self.assertIsNone(meta["backflow"])
        self.assertTrue(meta["rewritten"])

    def test_critic_unusable_output_skips_rewrite(self):
        """critic returns no scores and no classified_issues → skip rewrite, keep original."""
        blueprint = {"data": {"positioning": {"one_liner": "L"},
                              "elements": [{"id": "hook", "label": "Hook", "content": "H"}]}}
        research = {"data": {"facts": {"key_facts": ["x"]}}}
        call_count = {"n": 0}

        def fake_dispatch(m, c):
            call_count["n"] += 1
            if call_count["n"] == 1:  # generate
                return json.dumps({"markdown": "原始内容"}, ensure_ascii=False)
            # critic: malformed — no scores, no classified_issues
            return json.dumps({"issues": ["无法评分"], "improvements": []}, ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("critic-unusable", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                out = stage_produce(blueprint, research, state,
                                    options={"api_key": "k", "quality_mode": "polished"},
                                    platforms=["xiaohongshu"], parallel=False)
        # Only generate + critic = 2 calls; no rewrite attempted.
        self.assertEqual(call_count["n"], 2)
        meta = out["data"]["xiaohongshu"]["_meta"]
        self.assertEqual(meta.get("skipped"), "critic_output_unusable")
        self.assertFalse(meta["rewritten"])

    def test_sanitize_for_prompt_flattens_and_caps(self):
        from promoagent.pipeline import _sanitize_for_prompt
        # Newlines flattened.
        self.assertNotIn("\n", _sanitize_for_prompt("line1\nline2"))
        # Long text capped.
        out = _sanitize_for_prompt("x" * 500)
        self.assertLessEqual(len(out), 201)
        self.assertTrue(out.endswith("…"))
        # Short text passes through.
        self.assertEqual(_sanitize_for_prompt("ok"), "ok")

    def test_backflow_research_upstream_failure_keeps_original(self):
        """When fact_insufficient routes but stage_research raises, the original
        content is kept and NO produce-only rewrite runs (routed=True path)."""
        blueprint = {"data": {"positioning": {"one_liner": "L"},
                              "elements": [{"id": "hook", "label": "Hook", "content": "H"}]}}
        research = {"data": {"facts": {"key_facts": ["x"]}}}
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        call_count = {"n": 0}

        def fake_dispatch(m, c):
            call_count["n"] += 1
            user = m[-1]["content"] if m else ""
            if "评审以下" in user or "待评内容" in user:  # critic → fact_insufficient
                return json.dumps({
                    "scores": {"fidelity": 2, "engagement": 4, "alignment": 4},
                    "classified_issues": [{"type": "fact_insufficient", "description": "缺数据"}],
                    "primary_problem_type": "fact_insufficient",
                    "issues": ["缺数据"], "improvements": ["补数据"],
                }, ensure_ascii=False)
            # Any research rerun → raise to simulate upstream failure.
            if "推广策略" in user or "research" in user.lower():
                raise RuntimeError("research rerun exploded")
            return json.dumps({"markdown": "内容"}, ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("backflow-upstream-fail", cache_dir=Path(tmp))
            state.set("research", research)
            state.set("blueprint", blueprint)
            with patch.object(pipeline, "dispatch_chat", fake_dispatch), \
                 patch.object(pipeline, "find_examples", lambda r, **kw: []):
                out = stage_produce(blueprint, research, state,
                                    options={"api_key": "k", "quality_mode": "polished"},
                                    platforms=["xiaohongshu"], parallel=False, result=result)
        meta = out["data"]["xiaohongshu"]["_meta"]
        # Routed to research backflow (attempted=True), but upstream failed →
        # original content kept and NO produce-only rewrite (routed path).
        self.assertTrue(meta["backflow"]["attempted"])
        self.assertEqual(meta["backflow"]["stage"], "research")
        self.assertFalse(meta["rewritten"], "must NOT rewrite when a backflow branch was routed")
        self.assertEqual(out["data"]["xiaohongshu"].get("markdown"), "内容")

    def test_backflow_blueprint_no_edits_returns_none_silently(self):
        """structure_issue with no actionable suggested_edit → silent None, no warning."""
        blueprint = {"data": {"positioning": {"one_liner": "L"},
                              "elements": [{"id": "hook", "label": "Hook", "content": "H"}]}}
        research = {"data": {"facts": {"key_facts": ["x"]}}}
        warnings = []
        call_count = {"n": 0}

        def fake_dispatch(m, c):
            call_count["n"] += 1
            user = m[-1]["content"] if m else ""
            if "评审以下" in user or "待评内容" in user:  # critic → structure_issue, no suggested_edit
                return json.dumps({
                    "scores": {"fidelity": 4, "engagement": 4, "alignment": 2},
                    "classified_issues": [{"type": "structure_issue", "description": "结构",
                                           "suggested_edit": None}],
                    "primary_problem_type": "structure_issue",
                    "issues": ["结构"], "improvements": ["调"],
                }, ensure_ascii=False)
            return json.dumps({"markdown": "内容"}, ensure_ascii=False)

        real_warning = pipeline.logger.warning

        def spy_warning(msg, **kw):
            warnings.append(msg)
            real_warning(msg, **kw)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("backflow-no-edits", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch), \
                 patch.object(pipeline, "find_examples", lambda r, **kw: []), \
                 patch.object(pipeline, "logger") as mock_logger:
                mock_logger.warning = spy_warning
                out = stage_produce(blueprint, research, state,
                                    options={"api_key": "k", "quality_mode": "polished"},
                                    platforms=["xiaohongshu"], parallel=False)
        meta = out["data"]["xiaohongshu"]["_meta"]
        # Routed to blueprint (attempted=True) but no edits → no upstream change,
        # original kept, and crucially NO warning logged (empty edits are not a failure).
        self.assertTrue(meta["backflow"]["attempted"])
        self.assertEqual(meta["backflow"]["stage"], "blueprint")
        self.assertFalse(meta["rewritten"])
        edit_warnings = [w for w in warnings if "edit_blueprint" in str(w)]
        self.assertEqual(edit_warnings, [], "empty edits must not log a warning")

    # ------------------------------------------------------------------
    # Pipeline: run_pipeline
    # ------------------------------------------------------------------

    def test_run_pipeline_stops_after_research(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        with patch.object(pipeline, "dispatch_chat",
                          lambda m, c: json.dumps(_research_payload(), ensure_ascii=False)):
            with tempfile.TemporaryDirectory() as tmp:
                state = PipelineState("pipe-research", cache_dir=Path(tmp))
                outputs = run_pipeline(result, options={"api_key": "k"},
                                       stop_after="research", state=state)
        self.assertIn("research", outputs)
        self.assertNotIn("blueprint", outputs)

    def test_run_pipeline_full(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)

        def fake_dispatch(messages, config):
            user = messages[-1]["content"]
            if "research" in user or "推广策略" in user:
                return json.dumps(_research_payload(), ensure_ascii=False)
            if "Blueprint" in user or "内容元素" in user:
                return json.dumps(_blueprint_payload(), ensure_ascii=False)
            return json.dumps({"platform": "x", "markdown": "content"}, ensure_ascii=False)

        with tempfile.TemporaryDirectory() as tmp:
            state = PipelineState("pipe-full", cache_dir=Path(tmp))
            with patch.object(pipeline, "dispatch_chat", fake_dispatch):
                outputs = run_pipeline(result, options={"api_key": "k"}, state=state)

        self.assertIn("research", outputs)
        self.assertIn("blueprint", outputs)
        self.assertIn("produce", outputs)
        self.assertTrue(outputs["produce"]["data"])

    # ------------------------------------------------------------------
    # Optimize
    # ------------------------------------------------------------------

    def test_optimize_writes_files(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "launch-assets"
            manifest = run_optimize(result, cwd=FIXTURES, output_dir=output_dir)

            self.assertIn("INDEX.md", manifest["generated"])
            self.assertIn("evidence-summary.md", manifest["generated"])
            self.assertIn("promo-draft.md", manifest["generated"])
            self.assertEqual(manifest["promoSource"], "unavailable")

    def test_optimize_uses_ai_content_when_provided(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "launch-assets"
            manifest = run_optimize(
                result, cwd=FIXTURES, output_dir=output_dir,
                ai_content=sample_ai_content(), ai_model="test-model",
            )

            self.assertEqual(manifest["promoSource"], "ai")
            self.assertEqual(manifest["promoModel"], "test-model")
            xhs = (output_dir / "promo-xiaohongshu.md").read_text(encoding="utf-8")
            self.assertIn("AI 小红书正文", xhs)

    def test_optimize_surfaces_full_platform_fields(self):
        """title / hashtags / thread / publish_notes are written to files, not just markdown."""
        from promoagent.optimize import _format_platform_content
        rendered = _format_platform_content({
            "title": "测试标题",
            "markdown": "正文内容",
            "hashtags": ["#foo", "#bar"],
            "thread": ["第一推", "第二推"],
            "publish_notes": "建议晚上发",
        })
        self.assertIn("# 测试标题", rendered)
        self.assertIn("1/ 第一推", rendered)
        self.assertIn("2/ 第二推", rendered)
        self.assertIn("#foo #bar", rendered)
        self.assertIn("📌 建议晚上发", rendered)

    def test_optimize_twitter_thread_rendered(self):
        """Twitter threads are rendered as numbered posts, not dropped."""
        from promoagent.optimize import _format_platform_content
        rendered = _format_platform_content({
            "platform": "twitter",
            "thread": ["钩子推文", "价值点", "CTA"],
            "hashtags": [],
            "publish_notes": "",
        })
        self.assertIn("1/ 钩子推文", rendered)
        self.assertIn("3/ CTA", rendered)
        # No markdown body when thread is present — thread replaces it.
        self.assertNotIn("markdown", rendered.lower())

    def test_optimize_blank_thread_falls_back_to_markdown(self):
        """A non-empty but all-blank thread (models sometimes emit [""]) must
        not silently discard the markdown body."""
        from promoagent.optimize import _format_platform_content
        rendered = _format_platform_content({
            "title": "标题",
            "markdown": "正文内容",
            "thread": ["", ""],
        })
        self.assertIn("# 标题", rendered)
        self.assertIn("正文内容", rendered)

    def test_optimize_runs_with_full_fields(self):
        """run_optimize writes the enriched content to the platform file."""
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        ai_content = {"twitter": {
            "title": "Show HN: Repo Pulse",
            "markdown": "正文",
            "hashtags": ["#showhn"],
            "thread": ["推文1", "推文2"],
            "publish_notes": "首发后转发",
        }}
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "launch-assets"
            run_optimize(result, cwd=FIXTURES, output_dir=output_dir,
                         ai_content=ai_content, ai_model="test-model")
            tw = (output_dir / "promo-twitter.md").read_text(encoding="utf-8")
        self.assertIn("Show HN: Repo Pulse", tw)
        self.assertIn("1/ 推文1", tw)
        self.assertIn("#showhn", tw)
        self.assertIn("首发后转发", tw)

    def test_optimize_with_images_false_skips_image_generation(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "launch-assets"
            manifest = run_optimize(result, cwd=FIXTURES, output_dir=output_dir, generate_images=False)
        self.assertIn("INDEX.md", manifest["generated"])
        self.assertEqual(manifest.get("images"), [])

    def test_optimize_with_images_true_and_no_key_skips_ai_image(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        env_backup = {k: os.environ.pop(k, None) for k in [
            "PROMOAGENT_IMAGE_API_KEY", "OPENAI_API_KEY",
            "PROMOAGENT_MODELSCOPE_API_KEY", "PROMOAGENT_API_KEY", "MODELSCOPE_API_KEY",
        ]}
        try:
            with tempfile.TemporaryDirectory() as tmp:
                output_dir = Path(tmp) / "launch-assets"
                manifest = run_optimize(result, cwd=FIXTURES, output_dir=output_dir, generate_images=True)
            self.assertIn("INDEX.md", manifest["generated"])
            self.assertIsInstance(manifest.get("images"), list)
        finally:
            for k, v in env_backup.items():
                if v is not None:
                    os.environ[k] = v

    # ------------------------------------------------------------------
    # CLI
    # ------------------------------------------------------------------

    def test_python_cli_accepts_subcommand_and_legacy_target(self):
        explicit = subprocess.run(
            [sys.executable, "-m", "promoagent", "analyze", str(FIXTURES / "healthy-repo"), "--json"],
            cwd=ROOT, text=True, capture_output=True, check=True,
        )
        legacy = subprocess.run(
            [sys.executable, "-m", "promoagent", str(FIXTURES / "healthy-repo"), "--json"],
            cwd=ROOT, text=True, capture_output=True, check=True,
        )
        self.assertEqual(json.loads(explicit.stdout)["project"]["name"], "repo-pulse")
        self.assertEqual(json.loads(legacy.stdout)["project"]["name"], "repo-pulse")

    def test_python_cli_draft_help_lists_stages(self):
        result = subprocess.run(
            [sys.executable, "-m", "promoagent", "draft", "--help"],
            cwd=ROOT, text=True, capture_output=True, check=True,
        )
        self.assertIn("--stage", result.stdout)
        self.assertIn("blueprint", result.stdout)

    def test_python_cli_draft_help_includes_no_search(self):
        result = subprocess.run(
            [sys.executable, "-m", "promoagent", "draft", "--help"],
            cwd=ROOT, text=True, capture_output=True, check=True,
        )
        self.assertIn("--no-search", result.stdout)

    def test_python_cli_json_failure_outputs_structured_error(self):
        """When --json mode fails, stdout gets a {ok:false,error} object so
        scripts/CI/MCP callers can parse the failure instead of empty stdout."""
        env = {**os.environ, "PROMOAGENT_CACHE_DIR": str(Path(tempfile.mkdtemp()))}
        # Point at a dead base_url to force a network failure regardless of
        # whether the host has working API keys.
        result = subprocess.run(
            [sys.executable, "-m", "promoagent", "draft",
             str(FIXTURES / "healthy-repo"), "--no-search", "--stage", "research",
             "--json", "--base-url", "http://127.0.0.1:1"],
            cwd=ROOT, env=env, text=True, capture_output=True, timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        # stdout must be parseable JSON with an error field (not empty).
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["error"])

    def test_python_cli_serve_launches_mcp_server(self):
        """`serve` now launches the MCP server over stdio."""
        import json as _json
        result = subprocess.run(
            [sys.executable, "-m", "promoagent", "serve"],
            cwd=ROOT, text=True, capture_output=True,
            input=_json.dumps({
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "test", "version": "1"}},
            }) + "\n",
            timeout=10,
        )
        # A successful initialize returns serverInfo, not an error.
        self.assertIn("serverInfo", result.stdout)
        self.assertIn("promoagent", result.stdout)

    def test_promoagent_bin_delegates_to_python_cli(self):
        result = subprocess.run(
            [str(ROOT / "bin" / "promoagent"), "--version"],
            cwd=ROOT, text=True, capture_output=True, check=True,
        )
        self.assertEqual(result.stdout.strip(), "0.4.0")

    # ------------------------------------------------------------------
    # .env loading
    # ------------------------------------------------------------------

    def test_dotenv_loads_keys_not_already_in_environ(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text("S2L_TEST_KEY=hello\nS2L_ALREADY_SET=original\n", encoding="utf-8")
            os.environ["S2L_ALREADY_SET"] = "original"
            os.environ.pop("S2L_TEST_KEY", None)
            import promoagent
            original_cwd = Path.cwd()
            try:
                os.chdir(tmp)
                promoagent._load_dotenv()
            finally:
                os.chdir(original_cwd)
            self.assertEqual(os.environ.get("S2L_TEST_KEY"), "hello")
            self.assertEqual(os.environ.get("S2L_ALREADY_SET"), "original")
            os.environ.pop("S2L_TEST_KEY", None)
            os.environ.pop("S2L_ALREADY_SET", None)

    # ------------------------------------------------------------------
    # Category detection + example finding
    # ------------------------------------------------------------------

    def test_detect_category_restaurant(self):
        result = analyze_free_text("上海阿强火锅，主打麻辣鲜香，人均80元")
        category = detect_category(result)
        self.assertIsInstance(category, str)
        self.assertTrue(len(category) > 0)

    def test_detect_category_tech(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        category = detect_category(result)
        self.assertIsInstance(category, str)
        self.assertTrue(len(category) > 0)

    def test_detect_category_github(self):
        result = {"source": "github", "project": {"name": "whisper", "description": "ASR"}, "evidence": {}, "target": ""}
        category = detect_category(result)
        self.assertIn("科技", category)

    def test_find_examples_no_key_returns_empty_or_ai(self):
        result = analyze_free_text("上海火锅店推广")
        env_backup = {k: os.environ.pop(k, None) for k in [
            "TAVILY_API_KEY", "PROMOAGENT_API_KEY", "PROMOAGENT_MODELSCOPE_API_KEY",
            "OPENAI_API_KEY", "MODELSCOPE_API_KEY",
        ]}
        try:
            examples = find_examples(result, platform="xhs", verbose=False)
            self.assertIsInstance(examples, list)
        finally:
            for k, v in env_backup.items():
                if v is not None:
                    os.environ[k] = v

    def test_format_examples_for_prompt(self):
        from promoagent.examples import format_examples_for_prompt
        formatted = format_examples_for_prompt(["案例一内容", "案例二内容"])
        self.assertIn("参考广告/示例", formatted)
        self.assertIn("参考示例 1", formatted)
        self.assertIn("参考示例 2", formatted)
        self.assertIn("不要复制内容", formatted)

    def test_format_examples_empty(self):
        from promoagent.examples import format_examples_for_prompt
        self.assertEqual(format_examples_for_prompt([]), "")

    # ------------------------------------------------------------------
    # Image generation
    # ------------------------------------------------------------------

    def test_build_image_prompt_contains_project_info(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        prompt = build_image_prompt(result, platform="xhs", model="dall-e-3")
        self.assertIn("repo-pulse", prompt)
        self.assertIn("3:4", prompt)
        self.assertIn("poster", prompt)
        self.assertIn("ad-ready campaign visual", prompt)
        self.assertIn("Creative skill:", prompt)
        self.assertIn("PROMO_RENDER_SPEC", prompt)
        self.assertIn("Ad copy to reserve space", prompt)
        self.assertIn("hard subject-exclusion", prompt)
        self.assertIn("separate local typography overlay", prompt)

    def test_image_skills_are_listed_and_resolved(self):
        self.assertIn("b2b-saas", list_image_skills())
        self.assertEqual(resolve_image_skill(requested="food", recommendation_kind="general")["name"], "food-local")
        self.assertEqual(resolve_image_skill(requested="unknown", recommendation_kind="product")["name"], "product-hero")

    def test_build_image_prompt_uses_explicit_creative_skill(self):
        result = analyze_free_text("LuminaDesk 护眼桌面灯，三档色温，金属机身，售价299元")
        prompt = build_image_prompt(result, platform="wechat", skill="product-hero", model="dall-e-3")
        self.assertIn("Creative skill: product-hero", prompt)
        self.assertIn("product-render-config", prompt)
        self.assertIn("reference_route", prompt)
        self.assertIn("Product & Food", prompt)
        self.assertIn("fake brand logo", prompt)

    def test_build_image_prompt_auto_uses_xhs_lifestyle_skill(self):
        result = analyze_free_text("一个适合自由职业者的时间管理服务，帮助整理客户项目和报价")
        prompt = build_image_prompt(result, platform="xhs", skill="auto", model="dall-e-3")
        self.assertIn("Creative skill: xhs-lifestyle", prompt)
        self.assertIn("Xiaohongshu cover", prompt)
        self.assertIn("first glance", prompt)
        self.assertIn("Ad-tool benchmark", prompt)

    def test_build_image_prompt_platform_dims(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        xhs_prompt = build_image_prompt(result, platform="xhs", model="dall-e-3")
        wechat_prompt = build_image_prompt(result, platform="wechat", model="dall-e-3")
        self.assertIn("3:4", xhs_prompt)
        self.assertIn("1:1", wechat_prompt)

    def test_build_image_prompt_chinese_model_branch(self):
        """Chinese image models (e.g. Qwen) get a Chinese-language prompt."""
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        prompt = build_image_prompt(result, platform="xhs", model="Qwen/Qwen-Image")
        self.assertIn("小红书封面", prompt)
        self.assertIn("核心要求", prompt)
        self.assertIn("竖版3:4比例", prompt)
        # Chinese branch must NOT emit the English skill/render-spec block
        self.assertNotIn("PROMO_RENDER_SPEC", prompt)
        self.assertNotIn("Creative skill:", prompt)

    def test_build_image_prompt_adapts_to_restaurant_recommendation(self):
        result = analyze_free_text("上海阿强火锅，主打麻辣鲜香，人均80元，位于静安区南京西路")
        prompt = build_image_prompt(result, platform="xhs", model="dall-e-3")
        self.assertIn("restaurant/local lifestyle recommendation", prompt)
        self.assertIn("sensory appeal", prompt)
        self.assertIn("Scene/backdrop", prompt)
        self.assertIn("Visual density", prompt)
        self.assertNotIn("open source software", prompt)
        self.assertNotIn("modern tech editorial", prompt)

    def test_build_image_prompt_adapts_to_event_recommendation(self):
        result = analyze_free_text("周末 AI 创业者线下沙龙，上海徐汇，适合产品经理和独立开发者报名")
        prompt = build_image_prompt(result, platform="linkedin", model="dall-e-3")
        self.assertIn("event/activity recommendation", prompt)
        self.assertIn("why attend", prompt)
        self.assertIn("wide LinkedIn banner", prompt)

    def test_build_image_prompt_adapts_to_product_recommendation(self):
        result = analyze_free_text("LuminaDesk 护眼桌面灯，三档色温，金属机身，售价299元")
        prompt = build_image_prompt(result, platform="wechat", model="dall-e-3")
        self.assertIn("consumer product recommendation", prompt)
        self.assertIn("product desirability", prompt)
        self.assertIn("one clear hero product", prompt)
        self.assertIn("square 1:1 card", prompt)
        self.assertIn("upper-left 42-48% wide copy-safe zone", prompt)
        self.assertIn("Avoid placing the subject", prompt)

    def test_build_image_prompt_adapts_to_research_recommendation(self):
        result = analyze_free_text("一篇关于推荐系统冷启动问题的研究论文，包含实验、数据集和方法对比")
        prompt = build_image_prompt(result, platform="zhihu", model="dall-e-3")
        self.assertIn("research/document recommendation", prompt)
        self.assertIn("method clarity", prompt)
        self.assertIn("research-diagram-grammar", prompt)
        self.assertIn("diagram_grammar", prompt)
        self.assertIn("senior art director", prompt)
        self.assertIn("wide 16:9 header image", prompt)

    def test_image_brief_resolves_ad_overlay_fields(self):
        result = analyze_free_text("一款适合夜间学习的护眼桌面灯，售价299元")
        brief = image_brief(result, options={
            "title": "今晚桌面更舒服",
            "subtitle": "三档色温，减少眩光",
            "cta": "立即了解",
            "badges": "护眼,金属机身",
        }, env={})
        self.assertEqual(brief["title"], "今晚桌面更舒服")
        self.assertEqual(brief["cta"], "立即了解")
        self.assertIn("护眼", brief["badges"])
        self.assertTrue(brief["textOverlay"])

    def test_apply_text_overlay_writes_ad_copy(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cover.png"
            Image.new("RGB", (900, 1200), (230, 224, 214)).save(path)
            before = path.read_bytes()

            changed = apply_text_overlay(path, platform="xhs", brief={
                "title": "今晚桌面更舒服",
                "subtitle": "三档色温，减少眩光",
                "cta": "立即了解",
                "badges": ["护眼", "金属机身"],
                "textOverlay": True,
            })

            self.assertTrue(changed)
            self.assertNotEqual(path.read_bytes(), before)

    def test_fetch_readme_images_returns_empty_when_no_urls(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            saved = fetch_readme_images(result, Path(tmp) / "images")
        self.assertIsInstance(saved, list)

    def test_generate_platform_images_with_mock_modelscope(self):
        import base64
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
        )
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        server = MockModelScopeImageServer(png_bytes)
        server.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                output_dir = Path(tmp) / "launch-assets"
                images = generate_platform_images(
                    result,
                    output_dir,
                    options={
                        "base_url": server.base_url,
                        "api_key": "test-key",
                        "model": "test-model",
                        "skill": "b2b-saas",
                        "poll_interval_ms": 10,
                        "timeout_ms": 5000,
                    },
                )
                ai_images = [img for img in images if img.get("provider") == "modelscope"]
                self.assertTrue(len(ai_images) >= 1)
                self.assertTrue(Path(ai_images[0]["outputPath"]).exists())
                self.assertEqual(ai_images[0]["skill"], "b2b-saas")
        finally:
            server.stop()

    def test_generate_openai_image_with_b64_response(self):
        import base64
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
        )
        server = MockOpenAIImageServer(png_bytes)
        server.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out_path = Path(tmp) / "cover-xhs.png"
                meta = generate_openai_image(
                    "Test prompt for xhs",
                    output_path=out_path,
                    config={
                        "apiKey": "test-key",
                        "baseUrl": server.base_url,
                        "model": "gpt-image-2",
                        "quality": "medium",
                        "timeoutMs": 10000,
                    },
                    platform="xhs",
                )
                self.assertTrue(out_path.exists())
                self.assertEqual(out_path.read_bytes(), png_bytes)
        finally:
            server.stop()

        self.assertEqual(meta["provider"], "openai")
        self.assertEqual(meta["size"], "1024x1536")

    def test_image_config_uses_image_specific_openai_env(self):
        env = {
            "PROMOAGENT_IMAGE_API_KEY": "image-key",
            "PROMOAGENT_IMAGE_BASE_URL": "https://image.example.test/v1",
            "PROMOAGENT_API_KEY": "text-key",
            "PROMOAGENT_BASE_URL": "https://text.example.test/v1",
            "PROMOAGENT_IMAGE_MODEL": "gpt-image-2",
        }
        cfg = image_config(env=env)
        self.assertEqual(cfg["apiKey"], "image-key")
        self.assertEqual(cfg["baseUrl"], "https://image.example.test/v1")
        self.assertEqual(cfg["model"], "gpt-image-2")

    def test_generate_platform_images_with_custom_openai_platforms(self):
        import base64
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
        )
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        server = MockOpenAIImageServer(png_bytes)
        server.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                output_dir = Path(tmp) / "launch-assets"
                images = generate_platform_images(
                    result,
                    output_dir,
                    options={
                        "base_url": server.base_url,
                        "api_key": "test-key",
                        "model": "gpt-image-2",
                        "platforms": "twitter,linkedin",
                    },
                )
                names = {Path(img["outputPath"]).name for img in images if img.get("provider") == "openai"}
                self.assertIn("cover-twitter.png", names)
                self.assertIn("cover-linkedin.png", names)
        finally:
            server.stop()

    def test_openai_model_detection(self):
        from promoagent.image import _is_openai_model
        self.assertTrue(_is_openai_model("gpt-image-2"))
        self.assertTrue(_is_openai_model("dall-e-3"))
        self.assertFalse(_is_openai_model("Qwen/Qwen-Image"))
        self.assertFalse(_is_openai_model("stabilityai/stable-diffusion"))

    def test_sanitize_error_body_truncates_and_flattens(self):
        from promoagent.image import _sanitize_error_body
        # Multi-line response is flattened to one line.
        self.assertNotIn("\n", _sanitize_error_body("line1\nline2\nline3"))
        # Long bodies are capped.
        long_body = "x" * 500
        out = _sanitize_error_body(long_body)
        self.assertLessEqual(len(out), 201)  # 200 + ellipsis
        self.assertTrue(out.endswith("…"))
        # Short bodies pass through (flattened only).
        self.assertEqual(_sanitize_error_body("ok"), "ok")
        # None / empty are safe.
        self.assertEqual(_sanitize_error_body(""), "")
        self.assertEqual(_sanitize_error_body(None), "")

    # ------------------------------------------------------------------
    # Platform publishers
    # ------------------------------------------------------------------

    def test_publisher_is_configured_telegram(self):
        env = {"TELEGRAM_BOT_TOKEN": "123:TOKEN", "TELEGRAM_CHAT_ID": "@channel"}
        pub = TelegramPublisher(env)
        self.assertTrue(pub.is_configured())

    def test_publisher_not_configured_without_keys(self):
        pub = TelegramPublisher({})
        self.assertFalse(pub.is_configured())

    def test_available_publishers_returns_only_configured(self):
        env = {
            "TELEGRAM_BOT_TOKEN": "123:TOKEN",
            "TELEGRAM_CHAT_ID": "@channel",
        }
        pubs = available_publishers(env)
        self.assertIn("telegram", pubs)
        self.assertNotIn("twitter", pubs)

    def test_publish_content_unknown_platform(self):
        result = publish_content("unknown_platform_xyz", "test content", env={})
        self.assertFalse(result.ok)
        self.assertIn("Unknown platform", result.error)

    def test_publish_content_no_api_platform(self):
        result = publish_content("xiaohongshu", "test content", env={})
        self.assertFalse(result.ok)
        self.assertIn("手动", result.error)

    def test_publish_content_missing_credentials(self):
        result = publish_content("telegram", "test content", env={})
        self.assertFalse(result.ok)
        self.assertIn("Missing env vars", result.error)

    def test_telegram_publish_with_mock_server(self):
        server = MockTelegramServer()
        server.start()
        env = {
            "TELEGRAM_BOT_TOKEN": "fake-token",
            "TELEGRAM_CHAT_ID": "@testchannel",
        }
        try:
            pub = TelegramPublisher(env)
            pub._BASE_URL = server.base_url
            original_post = pub._post

            def patched_post(url, body, headers=None):
                new_url = url.replace("https://api.telegram.org", server.base_url)
                return original_post(new_url, body, headers)

            pub._post = patched_post
            result = pub.publish("测试发布内容")
        finally:
            server.stop()
        self.assertTrue(result.ok)
        self.assertEqual(result.platform, "telegram")

    def test_bluesky_publisher_requires_handle_and_password(self):
        pub = BlueskyPublisher({"BLUESKY_HANDLE": "test.bsky.social"})
        self.assertFalse(pub.is_configured())

    def test_load_content_from_assets_resolves_alias(self):
        """fill/publish should find promo-xiaohongshu.md when asked for 'xhs'."""
        from promoagent.publish import load_content_from_assets
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "launch-assets"
            out.mkdir()
            (out / "promo-xiaohongshu.md").write_text("XHS content", encoding="utf-8")
            (out / "promo-twitter.md").write_text("Twitter content", encoding="utf-8")
            # Alias 'xhs' must resolve to the xiaohongshu file, not fall back to
            # the first promo-*.md (which would be twitter alphabetically).
            self.assertEqual(load_content_from_assets(out, "xhs"), "XHS content")
            self.assertEqual(load_content_from_assets(out, "x"), "Twitter content")

    def test_load_content_from_assets_missing_raises(self):
        from promoagent.publish import load_content_from_assets
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                load_content_from_assets(Path(tmp), "xiaohongshu")

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def test_cache_set_and_get(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            data = {"value": 42, "nested": {"list": [1, 2, 3]}}
            cache.set("test", "key", data=data, cache_dir=cache_dir)
            self.assertEqual(cache.get("test", "key", cache_dir=cache_dir), data)

    def test_cache_expires_after_ttl(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            cache.set("expiring", "key", data="test", cache_dir=cache_dir)
            cached = cache.get("expiring", "key", cache_dir=cache_dir, ttl_seconds=0)
            self.assertIsNone(cached)

    def test_cache_clear_removes_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            cache.set("a", "b", data="1", cache_dir=cache_dir)
            cache.set("a", "c", data="2", cache_dir=cache_dir)
            self.assertEqual(cache.clear("a", cache_dir=cache_dir), 2)

    def test_cache_stats_reports_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            cache.set("test", "1", data="a", cache_dir=cache_dir)
            cache.set("test", "2", data="b", cache_dir=cache_dir)
            stats = cache.get_stats(cache_dir=cache_dir)
            self.assertEqual(stats["entries"], 2)
            self.assertEqual(stats["valid_entries"], 2)
            self.assertIn("size_human", stats)

    def test_cache_stats_reports_empty_missing_cache_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = cache.get_stats(cache_dir=Path(tmp) / "missing-cache")
            self.assertEqual(stats["entries"], 0)
            self.assertEqual(stats["valid_entries"], 0)
            self.assertEqual(stats["expired_entries"], 0)
            self.assertIn("size_human", stats)
            self.assertIn("cache_dir", stats)

    def test_cache_key_generation(self):
        key1 = cache._make_key("github", "repos", "openai/whisper")
        key2 = cache._make_key("github", "repos", "openai/whisper")
        key3 = cache._make_key("github", "repos", "anthropic/claude")
        self.assertEqual(key1, key2)
        self.assertNotEqual(key1, key3)

    # ------------------------------------------------------------------
    # Logger
    # ------------------------------------------------------------------

    def test_logger_levels(self):
        logger = Logger("test", level=LogLevel.WARNING)
        self.assertFalse(logger._should_log(LogLevel.DEBUG))
        self.assertFalse(logger._should_log(LogLevel.INFO))
        self.assertTrue(logger._should_log(LogLevel.WARNING))
        self.assertTrue(logger._should_log(LogLevel.ERROR))

    def test_logger_text_format(self):
        logger = Logger("test")
        output = logger._format_text(LogLevel.INFO, "test message", key="value")
        self.assertIn("test", output)
        self.assertIn("INFO", output)
        self.assertIn("key='value'", output)

    def test_logger_json_format(self):
        logger = Logger("test")
        logger._use_json = True
        output = logger._format_json(LogLevel.INFO, "test message", count=42)
        parsed = json.loads(output)
        self.assertEqual(parsed["level"], "INFO")
        self.assertEqual(parsed["message"], "test message")
        self.assertEqual(parsed["context"]["count"], 42)

    def test_log_timer_success(self):
        import time
        with LogTimer("test_operation", items=10):
            time.sleep(0.01)

    def test_log_duration(self):
        import time
        start = time.time()
        time.sleep(0.01)
        log_duration("quick_op", start, items=10)

    # ------------------------------------------------------------------
    # Clarification UI
    # ------------------------------------------------------------------

    def test_ask_for_clarifications_skips_empty(self):
        from promoagent.ui import ask_for_clarifications, console as ui_console
        from rich.prompt import Prompt

        answers_iter = iter(["独立开发者", "", "  "])
        seen_consoles = []

        def fake_ask(prompt, **kwargs):
            seen_consoles.append(kwargs.get("console"))
            return next(answers_iter)

        with patch.object(Prompt, "ask", fake_ask):
            result = ask_for_clarifications(["目标用户是谁", "可选跳过", "空白也跳过"])

        # Only the non-empty answer is kept (after strip).
        self.assertEqual(result, {"目标用户是谁": "独立开发者"})
        # Every prompt must route through the stderr console to keep --json clean.
        self.assertTrue(all(c is ui_console for c in seen_consoles))

    def test_ask_for_clarifications_empty_gaps_returns_empty(self):
        from promoagent.ui import ask_for_clarifications
        self.assertEqual(ask_for_clarifications([]), {})


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

def sample_ai_content():
    return {
        "positioning": "测试定位",
        "targetUsers": ["维护者"],
        "strongestAngles": ["证据先行"],
        "promotionStrategy": {
            "coreAngle": "先读来源证据再写平台文案",
            "contentGraph": [],
            "audienceSegments": [],
            "platformAdaptation": [],
            "visualNarrative": [],
            "qualityRubric": {
                "fidelity": {"checks": ["事实来自 README"], "risks": ["不要编造"], "improvements": ["补截图"]},
                "engagement": {"checks": ["开头具体"], "risks": ["太模板"], "improvements": ["换成场景"]},
                "alignment": {"checks": ["平台语气匹配"], "risks": ["跨平台复用"], "improvements": ["分平台改写"]},
            },
            "reviewGate": {
                "fidelityQuestions": ["事实是否可核验？"],
                "engagementQuestions": ["开头是否具体？"],
                "platformQuestions": ["语气是否适配？"],
            },
        },
        "promotions": {
            "xiaohongshu": {"titles": ["证据先行"], "markdown": "# 小红书\n\nAI 小红书正文", "tags": ["#开源"]},
            "zhihu": {"suggestedQuestions": ["如何推广？"], "markdown": "# 知乎\n\nAI 知乎正文"},
            "wechatMoments": {"markdown": "# 微信\n\nAI 微信正文"},
            "showHn": {"title": "Show HN: Repo Pulse", "markdown": "# Show HN\n\nAI HN body"},
            "productHunt": {"markdown": "# Product Hunt\n\nAI PH body"},
        },
        "launchSequence": [],
    }


# ---------------------------------------------------------------------------
# Mock servers
# ---------------------------------------------------------------------------

class MockChatHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.last_request = json.loads(body.decode("utf-8"))
        response = {"choices": [{"message": {"content": json.dumps(self.server.ai_content, ensure_ascii=False)}}]}
        payload = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):  # noqa: A002
        return


class MockChatServer:
    def __init__(self, ai_content):
        self.httpd = HTTPServer(("127.0.0.1", 0), MockChatHandler)
        self.httpd.ai_content = ai_content
        self.httpd.last_request = None
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self):
        host, port = self.httpd.server_address
        return f"http://{host}:{port}/v1"

    @property
    def last_request(self):
        return self.httpd.last_request

    def start(self): self.thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.thread.join(timeout=5)
        self.httpd.server_close()


class MockTelegramHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        body = json.dumps({"ok": True, "result": {"message_id": 42}}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, format, *args): return  # noqa: A002


class MockTelegramServer:
    def __init__(self):
        self.httpd = HTTPServer(("127.0.0.1", 0), MockTelegramHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
    @property
    def base_url(self):
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"
    def start(self): self.thread.start()
    def stop(self):
        self.httpd.shutdown()
        self.thread.join(timeout=5)
        self.httpd.server_close()


class MockAnthropicHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        body = json.dumps({
            "content": [{"type": "text", "text": self.server.response_text}],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, format, *args): return  # noqa: A002


class MockAnthropicServer:
    def __init__(self, response_text: str):
        self.httpd = HTTPServer(("127.0.0.1", 0), MockAnthropicHandler)
        self.httpd.response_text = response_text
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
    @property
    def base_url(self):
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"
    def start(self): self.thread.start()
    def stop(self):
        self.httpd.shutdown()
        self.thread.join(timeout=5)
        self.httpd.server_close()


class MockGeminiHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        body = json.dumps({
            "candidates": [{"content": {"parts": [{"text": self.server.response_text}]}}]
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, format, *args): return  # noqa: A002


class MockGeminiServer:
    def __init__(self, response_text: str):
        self.httpd = HTTPServer(("127.0.0.1", 0), MockGeminiHandler)
        self.httpd.response_text = response_text
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
    @property
    def base_url(self):
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"
    def start(self): self.thread.start()
    def stop(self):
        self.httpd.shutdown()
        self.thread.join(timeout=5)
        self.httpd.server_close()


class MockOpenAIImageHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        import base64
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        b64 = base64.b64encode(self.server.png_bytes).decode("ascii")
        self._write_json({"created": 1, "data": [{"b64_json": b64}]})

    def _write_json(self, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        return


class MockOpenAIImageServer:
    def __init__(self, png_bytes: bytes):
        self.httpd = HTTPServer(("127.0.0.1", 0), MockOpenAIImageHandler)
        self.httpd.png_bytes = png_bytes
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self):
        host, port = self.httpd.server_address
        return f"http://{host}:{port}/v1"

    def start(self): self.thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.thread.join(timeout=5)
        self.httpd.server_close()


class MockModelScopeImageHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        self._write_json({"task_id": "img-task-1"})

    def do_GET(self):  # noqa: N802
        if "/tasks/" in self.path:
            self._write_json({
                "task_status": "SUCCEED",
                "output_images": [f"{self.server.base_url}/img.png"],
            })
        elif self.path.endswith("/img.png"):
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(self.server.png_bytes)))
            self.end_headers()
            self.wfile.write(self.server.png_bytes)
        else:
            self.send_error(404)

    def _write_json(self, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        return


class MockModelScopeImageServer:
    def __init__(self, png_bytes: bytes):
        self.httpd = HTTPServer(("127.0.0.1", 0), MockModelScopeImageHandler)
        self.httpd.png_bytes = png_bytes
        host, port = self.httpd.server_address
        self.httpd.base_url = f"http://{host}:{port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self):
        return self.httpd.base_url

    def start(self): self.thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.thread.join(timeout=5)
        self.httpd.server_close()


class MockGitHubHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path.startswith("/repos/"):
            self._write_json(self.server.api_payload)
        elif self.path.endswith("/README.md"):
            body = self.server.readme_text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def _write_json(self, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        return


class MockGitHubServer:
    def __init__(self, api_payload, readme_text):
        self.httpd = HTTPServer(("127.0.0.1", 0), MockGitHubHandler)
        self.httpd.api_payload = api_payload
        self.httpd.readme_text = readme_text
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self):
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"

    def start(self): self.thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.thread.join(timeout=5)
        self.httpd.server_close()


if __name__ == "__main__":
    unittest.main()

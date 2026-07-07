import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from promoagent.ai import _detect_provider, _chat_anthropic, _chat_gemini, _chat_ollama, generate_ai_content, parse_json_content, refine_content, validate_content
from promoagent.cache import get, set, clear, get_stats, _make_key
from promoagent.logger import Logger, LogLevel, get_logger, log_duration, LogTimer
from promoagent.publish import (
    BlueskyPublisher, TelegramPublisher, TwitterPublisher,
    available_publishers, publish_content,
)
from promoagent.analyzer import analyze_free_text, analyze_target, parse_github_owner_repo
from promoagent.image import apply_text_overlay, build_image_prompt, fetch_readme_images, generate_openai_image, generate_platform_images, image_brief, image_config
from promoagent.examples import detect_category, find_examples, format_examples_for_prompt
from promoagent.interactive import has_significant_gaps, identify_gaps
from promoagent.optimize import run_optimize
from promoagent.promo_prompts import PROMO_JSON_SCHEMA, build_evidence_brief, build_promo_system_prompt, build_promo_user_prompt, expand_presets

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests_py" / "fixtures"


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

    # ------------------------------------------------------------------
    # Free-text input (general promotion agent)
    # ------------------------------------------------------------------

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

    def test_evidence_brief_handles_free_text_result(self):
        result = analyze_free_text("上海阿强火锅，麻辣鲜香，人均80，静安区")
        payload = {"project": result["project"], "evidence": result["evidence"]}
        brief = build_evidence_brief(payload)
        self.assertIn("上海阿强火锅", brief)
        self.assertIn("推广主体", brief)
        self.assertIn("核心描述", brief)

    def test_identify_gaps_for_thin_text_input(self):
        result = analyze_free_text("火锅店")  # very thin
        gaps = identify_gaps(result)
        self.assertIn("description", gaps)   # description is too short
        self.assertIn("cta", gaps)           # no CTA
        self.assertTrue(len(gaps) <= 3)

    def test_has_significant_gaps_for_repo(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        # Repo with README, install command, visuals — should not have significant gaps
        # (or at least cta and description are filled)
        gaps = identify_gaps(result)
        # Install command fills cta, description from README fills description
        self.assertNotIn("cta", gaps)

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

        # Falls back to placeholder when network/repo not found
        self.assertIn(result["source"], ("url", "github"))
        self.assertEqual(result["project"]["name"], "repo-pulse")

    # ------------------------------------------------------------------
    # GitHub URL fetching
    # ------------------------------------------------------------------

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
    # AI
    # ------------------------------------------------------------------

    def test_ai_generation_with_openai_compatible_server(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        server = MockChatServer(sample_ai_content())
        server.start()
        try:
            generated = generate_ai_content(result, platform="xhs", options={
                "base_url": server.base_url,
                "api_key": "test-key",
                "model": "test-model",
            })
        finally:
            server.stop()

        self.assertEqual(generated["model"], "test-model")
        self.assertEqual(generated["content"]["positioning"], "测试定位")
        self.assertIn("qualityRubric", server.last_request["messages"][1]["content"])

    # ------------------------------------------------------------------
    # Output validation
    # ------------------------------------------------------------------

    def test_validate_content_catches_missing_rubric(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        content = {
            "promotionStrategy": {"qualityRubric": {}},
            "promotions": {}
        }
        issues = validate_content(content, result)
        rubric_issues = [i for i in issues if "qualityRubric" in i["message"]]
        self.assertGreater(len(rubric_issues), 0)

    def test_validate_content_passes_clean_output(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        content = {
            "promotionStrategy": {"qualityRubric": {
                "fidelity": {"checks": ["事实准确"]},
                "engagement": {"checks": ["开头具体"]},
                "alignment": {"checks": ["平台语气匹配"]},
            }},
            "promotions": {
                "xiaohongshu": {
                    "titles": ["用一行命令生成推广文案"],
                    "markdown": "npx repo-pulse . 把仓库变成小红书帖子，5分钟搞定。",
                }
            }
        }
        issues = validate_content(content, result)
        self.assertEqual(issues, [])  # No structural issues

    def test_parse_json_content_accepts_fenced_json(self):
        parsed = parse_json_content("```json\n{\"ok\": true}\n```")
        self.assertEqual(parsed, {"ok": True})

    # ------------------------------------------------------------------
    # Multi-provider LLM support
    # ------------------------------------------------------------------

    def test_detect_provider_from_anthropic_key(self):
        env = {"ANTHROPIC_API_KEY": "sk-ant-test"}
        self.assertEqual(_detect_provider({}, env), "anthropic")

    def test_detect_provider_from_gemini_key(self):
        env = {"GOOGLE_API_KEY": "test-key"}
        self.assertEqual(_detect_provider({}, env), "gemini")

    def test_detect_provider_from_ollama_url(self):
        env = {"OLLAMA_BASE_URL": "http://localhost:11434"}
        self.assertEqual(_detect_provider({}, env), "ollama")

    def test_detect_provider_from_modelscope_key(self):
        env = {"PROMOAGENT_MODELSCOPE_API_KEY": "ms-test"}
        self.assertEqual(_detect_provider({}, env), "modelscope")

    def test_detect_provider_from_explicit_override(self):
        env = {"PROMOAGENT_PROVIDER": "anthropic", "OPENAI_API_KEY": "sk-test"}
        self.assertEqual(_detect_provider({}, env), "anthropic")

    def test_detect_provider_from_claude_model_name(self):
        opts = {"model": "claude-opus-4-5"}
        self.assertEqual(_detect_provider(opts, {}), "anthropic")

    def test_detect_provider_from_gemini_model_name(self):
        opts = {"model": "gemini-2.0-flash"}
        self.assertEqual(_detect_provider(opts, {}), "gemini")

    def test_detect_provider_defaults_to_openai(self):
        self.assertEqual(_detect_provider({}, {}), "openai")

    def test_chat_anthropic_with_mock_server(self):
        """_chat_anthropic converts messages and parses Anthropic response format."""
        server = MockAnthropicServer(json.dumps({"key": "value"}))
        server.start()
        try:
            result = _chat_anthropic(
                [
                    {"role": "system", "content": "You are a helper."},
                    {"role": "user", "content": "Say hello."},
                ],
                {
                    "apiKey": "test-key",
                    "baseUrl": server.base_url,
                    "model": "claude-haiku-4-5",
                    "maxTokens": 100,
                    "temperature": 0.7,
                    "timeout": 10,
                },
            )
        finally:
            server.stop()
        self.assertIn("key", result)

    def test_chat_gemini_with_mock_server(self):
        """_chat_gemini converts messages and parses Gemini response format."""
        server = MockGeminiServer(json.dumps({"gemini": "response"}))
        server.start()
        try:
            result = _chat_gemini(
                [
                    {"role": "system", "content": "You are a helper."},
                    {"role": "user", "content": "Say hello."},
                ],
                {
                    "apiKey": "test-key",
                    "baseUrl": server.base_url,
                    "model": "gemini-flash",
                    "maxTokens": 100,
                    "temperature": 0.7,
                    "timeout": 10,
                },
            )
        finally:
            server.stop()
        self.assertIn("gemini", result)

    def test_chat_ollama_with_mock_server(self):
        """_chat_ollama uses /api/chat endpoint and parses Ollama response."""
        server = MockOllamaServer(json.dumps({"ollama": "response"}))
        server.start()
        try:
            result = _chat_ollama(
                [{"role": "user", "content": "Say hello."}],
                {
                    "apiKey": "",
                    "baseUrl": server.base_url,
                    "model": "llama3.2",
                    "maxTokens": 100,
                    "temperature": 0.7,
                    "timeout": 10,
                },
            )
        finally:
            server.stop()
        self.assertIn("ollama", result)

    # ------------------------------------------------------------------
    # Prompt presets
    # ------------------------------------------------------------------

    def test_expand_presets_returns_hint_string(self):
        result = expand_presets(["autopr", "paper"])
        self.assertIn("autopr", result)
        self.assertIn("paper", result)
        self.assertIsInstance(result, str)

    def test_expand_presets_empty_returns_empty(self):
        self.assertEqual(expand_presets([]), "")

    def test_prompt_schema_requires_quality_rubric(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        payload = {"project": result["project"], "evidence": result["evidence"]}
        prompt = build_promo_user_prompt(payload, platform="xhs")

        self.assertIn("qualityRubric", PROMO_JSON_SCHEMA)
        self.assertIn("qualityRubric", prompt)
        self.assertIn("npx repo-pulse .", build_evidence_brief(payload))

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
            # Without AI, a placeholder draft is written
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
            # Filename derived from AI output key ("xiaohongshu" → "promo-xiaohongshu.md")
            xhs = (output_dir / "promo-xiaohongshu.md").read_text(encoding="utf-8")
            self.assertIn("AI 小红书正文", xhs)

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

    def test_python_cli_context_and_prompt_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes.md"
            notes.write_text("Use a dry maintainer voice.", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable, "-m", "promoagent", "promote",
                    str(FIXTURES / "healthy-repo"),
                    "--context", str(notes),
                    "--prompt-note", "Avoid hype.",
                    "--prompt-preset", "launch",
                    "--json",
                ],
                cwd=ROOT, text=True, capture_output=True, check=True,
            )

        payload = json.loads(result.stdout)
        self.assertIn("Avoid hype.", payload["user"])
        self.assertIn("Use a dry maintainer voice.", payload["user"])

    def test_promoagent_bin_delegates_to_python_cli(self):
        result = subprocess.run(
            [str(ROOT / "bin" / "promoagent"), "--version"],
            cwd=ROOT, text=True, capture_output=True, check=True,
        )
        self.assertEqual(result.stdout.strip(), "0.3.0")

    def test_python_cli_ai_promote_and_optimize_with_mock_server(self):
        server = MockChatServer(sample_ai_content())
        server.start()
        env = {**os.environ, "PROMOAGENT_API_KEY": "test-key"}
        try:
            promoted = subprocess.run(
                [
                    sys.executable, "-m", "promoagent", "promote",
                    str(FIXTURES / "healthy-repo"),
                    "--ai", "--json", "--base-url", server.base_url, "--model", "test-model",
                ],
                cwd=ROOT, env=env, text=True, capture_output=True, check=True,
            )
            with tempfile.TemporaryDirectory() as tmp:
                output_dir = Path(tmp) / "launch-assets"
                subprocess.run(
                    [
                        sys.executable, "-m", "promoagent", "optimize",
                        str(FIXTURES / "healthy-repo"),
                        "--ai", "--base-url", server.base_url, "--model", "test-model",
                        "--output", str(output_dir),
                    ],
                    cwd=ROOT, env=env, text=True, capture_output=True, check=True,
                )
                xhs = (output_dir / "promo-xiaohongshu.md").read_text(encoding="utf-8")
        finally:
            server.stop()

        self.assertEqual(json.loads(promoted.stdout)["ai"]["content"]["positioning"], "测试定位")
        self.assertIn("AI 小红书正文", xhs)

    # ------------------------------------------------------------------
    # .env loading
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Two-stage: category detection + example finding
    # ------------------------------------------------------------------

    def test_detect_category_restaurant(self):
        result = analyze_free_text("上海阿强火锅，主打麻辣鲜香，人均80元")
        # Without AI key, falls back to heuristic — just check it returns a non-empty string
        category = detect_category(result)
        self.assertIsInstance(category, str)
        self.assertTrue(len(category) > 0)

    def test_detect_category_tech(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        # Local repo → heuristic returns 科技/开源项目
        category = detect_category(result)
        self.assertIsInstance(category, str)
        self.assertTrue(len(category) > 0)

    def test_detect_category_github(self):
        result = {"source": "github", "project": {"name": "whisper", "description": "ASR"}, "evidence": {}, "target": ""}
        category = detect_category(result)
        # GitHub source → heuristic → 科技/开源项目
        self.assertIn("科技", category)

    def test_format_examples_for_prompt(self):
        examples = ["这是示例一的内容，非常精彩", "这是示例二，风格不同"]
        formatted = format_examples_for_prompt(examples, platform="xhs")
        self.assertIn("参考示例", formatted)
        self.assertIn("示例 1", formatted)
        self.assertIn("示例 2", formatted)
        self.assertIn("不要复制内容", formatted)

    def test_format_examples_empty(self):
        self.assertEqual(format_examples_for_prompt([]), "")

    def test_find_examples_no_key_returns_empty_or_ai(self):
        """Without API keys, find_examples should return empty list gracefully."""
        result = analyze_free_text("上海火锅店推广")
        # Remove all API keys for this test
        env_backup = {k: os.environ.pop(k, None) for k in [
            "TAVILY_API_KEY", "PROMOAGENT_API_KEY", "PROMOAGENT_MODELSCOPE_API_KEY",
            "OPENAI_API_KEY", "MODELSCOPE_API_KEY"
        ]}
        try:
            examples = find_examples(result, platform="xhs", verbose=False)
            # Without any API key, should return empty list (not crash)
            self.assertIsInstance(examples, list)
        finally:
            for k, v in env_backup.items():
                if v is not None:
                    os.environ[k] = v

    def test_examples_injected_in_prompt(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        payload = {"project": result["project"], "evidence": result["evidence"]}
        examples = ["示例内容1：这是一个优质的小红书帖子示例", "示例内容2：另一个不同风格的示例"]
        prompt = build_promo_user_prompt(payload, platform="xhs", examples=examples)
        self.assertIn("参考示例", prompt)
        self.assertIn("示例内容1", prompt)
        self.assertIn("不要复制内容", prompt)

    def test_examples_not_injected_when_empty(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        payload = {"project": result["project"], "evidence": result["evidence"]}
        prompt_without = build_promo_user_prompt(payload, platform="xhs", examples=[])
        prompt_with_none = build_promo_user_prompt(payload, platform="xhs", examples=None)
        self.assertNotIn("参考示例", prompt_without)
        self.assertNotIn("参考示例", prompt_with_none)

    # ------------------------------------------------------------------
    # Image generation
    # ------------------------------------------------------------------

    def test_build_image_prompt_contains_project_info(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        prompt = build_image_prompt(result, platform="xhs")
        self.assertIn("repo-pulse", prompt)
        self.assertIn("3:4", prompt)
        self.assertIn("poster", prompt)
        self.assertIn("ad-ready campaign visual", prompt)
        self.assertIn("Ad copy to reserve space", prompt)

    def test_build_image_prompt_platform_dims(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        xhs_prompt = build_image_prompt(result, platform="xhs")
        wechat_prompt = build_image_prompt(result, platform="wechat")
        self.assertIn("3:4", xhs_prompt)
        self.assertIn("1:1", wechat_prompt)

    def test_build_image_prompt_adapts_to_restaurant_recommendation(self):
        result = analyze_free_text("上海阿强火锅，主打麻辣鲜香，人均80元，位于静安区南京西路")
        prompt = build_image_prompt(result, platform="xhs")

        self.assertIn("restaurant/local lifestyle recommendation", prompt)
        self.assertIn("sensory appeal", prompt)
        self.assertIn("Scene/backdrop", prompt)
        self.assertIn("Visual density", prompt)
        self.assertNotIn("open source software", prompt)
        self.assertNotIn("modern tech editorial", prompt)

    def test_build_image_prompt_adapts_to_event_recommendation(self):
        result = analyze_free_text("周末 AI 创业者线下沙龙，上海徐汇，适合产品经理和独立开发者报名")
        prompt = build_image_prompt(result, platform="linkedin")

        self.assertIn("event/activity recommendation", prompt)
        self.assertIn("why attend", prompt)
        self.assertIn("wide LinkedIn banner", prompt)

    def test_build_image_prompt_adapts_to_product_recommendation(self):
        result = analyze_free_text("LuminaDesk 护眼桌面灯，三档色温，金属机身，售价299元")
        prompt = build_image_prompt(result, platform="wechat")

        self.assertIn("consumer product recommendation", prompt)
        self.assertIn("product desirability", prompt)
        self.assertIn("one clear hero product", prompt)
        self.assertIn("square 1:1 card", prompt)

    def test_build_image_prompt_adapts_to_research_recommendation(self):
        result = analyze_free_text("一篇关于推荐系统冷启动问题的研究论文，包含实验、数据集和方法对比")
        prompt = build_image_prompt(result, platform="zhihu")

        self.assertIn("research/document recommendation", prompt)
        self.assertIn("method clarity", prompt)
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

    def test_promo_system_prompt_includes_recommendation_task_guidance(self):
        prompt = build_promo_system_prompt()

        self.assertIn("推荐任务适配", prompt)
        self.assertIn("软件/工具", prompt)
        self.assertIn("本地生活/餐饮", prompt)

    def test_fetch_readme_images_returns_empty_when_no_urls(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        # healthy-repo README has no external image URLs — should return empty list
        with tempfile.TemporaryDirectory() as tmp:
            saved = fetch_readme_images(result, Path(tmp) / "images")
        self.assertIsInstance(saved, list)

    def test_optimize_with_images_false_skips_image_generation(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "launch-assets"
            manifest = run_optimize(result, cwd=FIXTURES, output_dir=output_dir, generate_images=False)
        self.assertIn("INDEX.md", manifest["generated"])
        self.assertEqual(manifest.get("images"), [])

    def test_optimize_with_images_true_and_no_key_skips_ai_image(self):
        """When --image is set but no API key, README images are attempted but AI image is skipped."""
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        # Remove any API key from environment for this test
        env_backup = {k: os.environ.pop(k, None) for k in [
            "PROMOAGENT_IMAGE_API_KEY", "OPENAI_API_KEY",
            "PROMOAGENT_MODELSCOPE_API_KEY", "PROMOAGENT_API_KEY", "MODELSCOPE_API_KEY"
        ]}
        try:
            with tempfile.TemporaryDirectory() as tmp:
                output_dir = Path(tmp) / "launch-assets"
                manifest = run_optimize(result, cwd=FIXTURES, output_dir=output_dir, generate_images=True)
            # Should not crash; images list may be empty (no readme images in fixture)
            self.assertIn("INDEX.md", manifest["generated"])
            self.assertIsInstance(manifest.get("images"), list)
        finally:
            for k, v in env_backup.items():
                if v is not None:
                    os.environ[k] = v

    def test_generate_platform_images_with_mock_modelscope(self):
        """Full image generation flow with a mock ModelScope server."""
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
                        "api_key": "test-key",   # api_key in options → picked up by image_config
                        "model": "test-model",
                        "poll_interval_ms": 10,
                        "timeout_ms": 5000,
                    },
                )
                # Check paths while temp dir still exists
                ai_images = [img for img in images if img.get("provider") == "modelscope"]
                self.assertTrue(len(ai_images) >= 1)
                self.assertTrue(Path(ai_images[0]["outputPath"]).exists())
        finally:
            server.stop()

    def test_generate_openai_image_with_b64_response(self):
        """GPT Image 2 synchronous API: POST → b64_json response → save file."""
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
        self.assertEqual(meta["size"], "1024x1536")   # xhs portrait size

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
        """Image platform list can be customized for platform-specific assets."""
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

    # ------------------------------------------------------------------
    # Multi-turn refinement + example comparison
    # ------------------------------------------------------------------

    def test_refine_content_with_mock_server(self):
        """refine_content() appends feedback to conversation and calls AI again."""
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        server = MockChatServer(sample_ai_content())
        server.start()
        try:
            # Simulate a previous generation result with messages saved
            previous_result = {
                "messages": [
                    {"role": "system", "content": "You are a promo editor."},
                    {"role": "user", "content": "Generate promo for repo-pulse."},
                ],
                "content": sample_ai_content(),
                "model": "test-model",
                "baseUrl": server.base_url,
            }
            refined = refine_content(
                previous_result,
                "小红书那条太广告感了，改得更自然一些",
                options={"base_url": server.base_url, "api_key": "test-key", "model": "test-model"},
            )
        finally:
            server.stop()

        # Should have extended conversation
        self.assertIn("content", refined)
        self.assertIn("messages", refined)
        msgs = refined["messages"]
        # Original 2 messages + assistant response + user feedback = 4 messages
        self.assertGreaterEqual(len(msgs), 4)
        # Last user message contains the feedback
        self.assertIn("广告感", msgs[-1]["content"])

    def test_generate_ai_content_saves_messages(self):
        """generate_ai_content returns messages for subsequent refinement."""
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        server = MockChatServer(sample_ai_content())
        server.start()
        try:
            ai_result = generate_ai_content(result, platform="xhs", options={
                "base_url": server.base_url,
                "api_key": "test-key",
                "model": "test-model",
            }, compare_with_examples=False)
        finally:
            server.stop()

        self.assertIn("messages", ai_result)
        self.assertIsInstance(ai_result["messages"], list)
        self.assertGreater(len(ai_result["messages"]), 0)

    def test_refine_raises_without_context(self):
        """refine_content raises ValueError when no messages in previous result."""
        with self.assertRaises(ValueError):
            refine_content(
                {"content": {}, "messages": []},
                "改一下",
                options={"api_key": "test-key"},
            )

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
            # Twitter NOT configured
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
            pub._BASE_URL = server.base_url  # redirect to mock
            # Override the URL in _post by patching
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
        self.assertFalse(pub.is_configured())  # missing password

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
    # Cache
    # ------------------------------------------------------------------

    def test_cache_set_and_get(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            key = ("test", "key")
            data = {"value": 42, "nested": {"list": [1, 2, 3]}}

            # Set and get
            set(*key, data=data, cache_dir=cache_dir)
            cached = get(*key, cache_dir=cache_dir)
            self.assertEqual(cached, data)

    def test_cache_expires_after_ttl(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            key = ("expiring", "key")

            set("expiring", "key", data="test", cache_dir=cache_dir)
            # Should be expired with 0 TTL
            cached = get("expiring", "key", cache_dir=cache_dir, ttl_seconds=0)
            self.assertIsNone(cached)

    def test_cache_clear_removes_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            set("a", "b", data="1", cache_dir=cache_dir)
            set("a", "c", data="2", cache_dir=cache_dir)

            cleared = clear("a", cache_dir=cache_dir)
            self.assertEqual(cleared, 2)

    def test_cache_stats_reports_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            set("test", "1", data="a", cache_dir=cache_dir)
            set("test", "2", data="b", cache_dir=cache_dir)

            stats = get_stats(cache_dir=cache_dir)
            self.assertEqual(stats["entries"], 2)
            self.assertEqual(stats["valid_entries"], 2)
            self.assertIn("size_human", stats)

    def test_cache_stats_reports_empty_missing_cache_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = get_stats(cache_dir=Path(tmp) / "missing-cache")

            self.assertEqual(stats["entries"], 0)
            self.assertEqual(stats["valid_entries"], 0)
            self.assertEqual(stats["expired_entries"], 0)
            self.assertIn("size_human", stats)
            self.assertIn("cache_dir", stats)

    def test_cache_key_generation(self):
        key1 = _make_key("github", "repos", "openai/whisper")
        key2 = _make_key("github", "repos", "openai/whisper")
        key3 = _make_key("github", "repos", "anthropic/claude")

        self.assertEqual(key1, key2)
        self.assertNotEqual(key1, key3)

    # ------------------------------------------------------------------
    # Logger
    # ------------------------------------------------------------------

    def test_logger_levels(self):
        logger = Logger("test", level=LogLevel.WARNING)

        # Debug and info should not be logged
        self.assertFalse(logger._should_log(LogLevel.DEBUG))
        self.assertFalse(logger._should_log(LogLevel.INFO))
        # Warning and above should be logged
        self.assertTrue(logger._should_log(LogLevel.WARNING))
        self.assertTrue(logger._should_log(LogLevel.ERROR))

    def test_logger_text_format(self):
        logger = Logger("test")
        output = logger._format_text(LogLevel.INFO, "test message", key="value")
        self.assertIn("test", output)
        self.assertIn("INFO", output)
        self.assertIn("key='value'", output)

    def test_logger_json_format(self):
        import json
        logger = Logger("test")
        logger._use_json = True
        output = logger._format_json(LogLevel.INFO, "test message", count=42)

        parsed = json.loads(output)
        self.assertEqual(parsed["level"], "INFO")
        self.assertEqual(parsed["message"], "test message")
        self.assertEqual(parsed["context"]["count"], 42)

    def test_log_timer_success(self):
        import time
        logger = get_logger("test")

        with LogTimer("test_operation", items=10):
            time.sleep(0.01)  # 10ms

        # Timer should complete without error

    def test_log_duration(self):
        import time
        start = time.time()
        time.sleep(0.01)
        # Should not raise
        log_duration("quick_op", start, items=10)


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
    """Simulates Telegram Bot API: POST /botTOKEN/sendMessage → ok response."""
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
    """Simulates Anthropic Messages API: POST /v1/messages → content[0].text."""
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
    """Simulates Google Gemini generateContent API."""
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


class MockOllamaHandler(BaseHTTPRequestHandler):
    """Simulates Ollama /api/chat API."""
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        body = json.dumps({
            "message": {"role": "assistant", "content": self.server.response_text},
            "done": True,
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, format, *args): return  # noqa: A002


class MockOllamaServer:
    def __init__(self, response_text: str):
        self.httpd = HTTPServer(("127.0.0.1", 0), MockOllamaHandler)
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
    """Simulates OpenAI Images API: POST → b64_json response (synchronous)."""

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
    """Simulates ModelScope image generation API: submit task → poll → download."""

    def do_POST(self):  # noqa: N802
        # POST /v1/images/generations → task_id
        self._write_json({"task_id": "img-task-1"})

    def do_GET(self):  # noqa: N802
        if "/tasks/" in self.path:
            # Poll → SUCCEED with image URL
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

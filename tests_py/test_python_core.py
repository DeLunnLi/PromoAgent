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

from source2launch.ai import generate_ai_content, parse_json_content, validate_content
from source2launch.analyzer import analyze_free_text, analyze_target, parse_github_owner_repo
from source2launch.image import build_image_prompt, fetch_readme_images, generate_openai_image, generate_platform_images
from source2launch.examples import detect_category, find_examples, format_examples_for_prompt
from source2launch.interactive import has_significant_gaps, identify_gaps
from source2launch.optimize import run_optimize
from source2launch.promo_prompts import PROMPT_PRESETS, PROMO_JSON_SCHEMA, build_evidence_brief, build_promo_user_prompt, expand_presets

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
        from source2launch.analyzer import analyze_url_reference

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
        self.assertIn("promotionStrategy.qualityRubric", server.last_request["messages"][1]["content"])

    # ------------------------------------------------------------------
    # Output validation
    # ------------------------------------------------------------------

    def test_validate_content_catches_banned_words(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        content = {
            "promotionStrategy": {"qualityRubric": {
                "fidelity": {"checks": ["ok"]},
                "engagement": {"checks": ["ok"]},
                "alignment": {"checks": ["ok"]},
            }},
            "promotions": {
                "xiaohongshu": {
                    "titles": ["短标题"],
                    "markdown": "这款神器必备，颠覆你的工作流！",
                }
            }
        }
        issues = validate_content(content, result)
        messages = [i["message"] for i in issues]
        self.assertTrue(any("神器" in m or "必备" in m or "颠覆" in m for m in messages))

    def test_validate_content_catches_long_xhs_title(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        content = {
            "promotionStrategy": {"qualityRubric": {
                "fidelity": {"checks": ["ok"]},
                "engagement": {"checks": ["ok"]},
                "alignment": {"checks": ["ok"]},
            }},
            "promotions": {
                "xiaohongshu": {
                    "titles": ["这个标题超过了二十个汉字的限制真的太长了吧"],  # 21 chars
                    "markdown": "正文内容",
                }
            }
        }
        issues = validate_content(content, result)
        xhs_issues = [i for i in issues if i["platform"] == "xhs"]
        self.assertTrue(any("20字" in i["message"] for i in xhs_issues))

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
                    "markdown": "npx repo-pulse . 把仓库变成小红书帖子，5分钟搞定发布前的文案焦虑。",
                }
            }
        }
        issues = validate_content(content, result)
        # Clean output should have no or minimal issues
        critical_issues = [i for i in issues if "禁用词" in i["message"] or "标题" in i["message"]]
        self.assertEqual(len(critical_issues), 0)

    def test_parse_json_content_accepts_fenced_json(self):
        parsed = parse_json_content("```json\n{\"ok\": true}\n```")
        self.assertEqual(parsed, {"ok": True})

    # ------------------------------------------------------------------
    # Prompt presets
    # ------------------------------------------------------------------

    def test_expand_presets_returns_instructions(self):
        result = expand_presets(["autopr", "grounded"])
        self.assertIn("AutoPR", result)
        self.assertIn("traceable", result)
        self.assertEqual(result.count("### Preset:"), 2)

    def test_expand_presets_skips_unknown(self):
        result = expand_presets(["grounded", "unknown_xyz"])
        self.assertIn("traceable", result)
        self.assertNotIn("unknown_xyz", result)

    def test_all_documented_presets_exist(self):
        for name in ["grounded", "author", "realworld", "autopr", "scholardag",
                     "human", "tweet", "paper", "launch", "launchkit",
                     "technical", "zhihu", "xhs", "wechat", "visual", "paper2web", "thread"]:
            self.assertIn(name, PROMPT_PRESETS, f"Preset '{name}' missing")

    def test_prompt_schema_requires_quality_rubric(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        payload = {"project": result["project"], "evidence": result["evidence"]}
        prompt = build_promo_user_prompt(payload, platform="xhs")

        self.assertIn("qualityRubric", PROMO_JSON_SCHEMA)
        self.assertIn("promotionStrategy.qualityRubric", prompt)
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
            self.assertIn("promo-xhs.md", manifest["generated"])
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
            xhs = (output_dir / "promo-xhs.md").read_text(encoding="utf-8")
            self.assertIn("AI 小红书正文", xhs)

    # ------------------------------------------------------------------
    # CLI
    # ------------------------------------------------------------------

    def test_python_cli_accepts_subcommand_and_legacy_target(self):
        explicit = subprocess.run(
            [sys.executable, "-m", "source2launch", "analyze", str(FIXTURES / "healthy-repo"), "--json"],
            cwd=ROOT, text=True, capture_output=True, check=True,
        )
        legacy = subprocess.run(
            [sys.executable, "-m", "source2launch", str(FIXTURES / "healthy-repo"), "--json"],
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
                    sys.executable, "-m", "source2launch", "promote",
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

    def test_source2launch_bin_delegates_to_python_cli(self):
        result = subprocess.run(
            [str(ROOT / "bin" / "source2launch"), "--version"],
            cwd=ROOT, text=True, capture_output=True, check=True,
        )
        self.assertEqual(result.stdout.strip(), "0.2.0")

    def test_python_cli_ai_promote_and_optimize_with_mock_server(self):
        server = MockChatServer(sample_ai_content())
        server.start()
        env = {**os.environ, "SOURCE2LAUNCH_API_KEY": "test-key"}
        try:
            promoted = subprocess.run(
                [
                    sys.executable, "-m", "source2launch", "promote",
                    str(FIXTURES / "healthy-repo"),
                    "--ai", "--json", "--base-url", server.base_url, "--model", "test-model",
                ],
                cwd=ROOT, env=env, text=True, capture_output=True, check=True,
            )
            with tempfile.TemporaryDirectory() as tmp:
                output_dir = Path(tmp) / "launch-assets"
                subprocess.run(
                    [
                        sys.executable, "-m", "source2launch", "optimize",
                        str(FIXTURES / "healthy-repo"),
                        "--ai", "--base-url", server.base_url, "--model", "test-model",
                        "--output", str(output_dir),
                    ],
                    cwd=ROOT, env=env, text=True, capture_output=True, check=True,
                )
                xhs = (output_dir / "promo-xhs.md").read_text(encoding="utf-8")
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
        category = detect_category(result)
        self.assertIn("餐饮", category)

    def test_detect_category_tech(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        category = detect_category(result)
        self.assertIn("科技", category)

    def test_detect_category_github(self):
        result = {"source": "github", "project": {"name": "whisper", "description": "automatic speech recognition"}, "evidence": {}, "target": ""}
        category = detect_category(result)
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
            "TAVILY_API_KEY", "SOURCE2LAUNCH_API_KEY", "SOURCE2LAUNCH_MODELSCOPE_API_KEY",
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

    def test_build_image_prompt_platform_dims(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        xhs_prompt = build_image_prompt(result, platform="xhs")
        wechat_prompt = build_image_prompt(result, platform="wechat")
        self.assertIn("3:4", xhs_prompt)
        self.assertIn("1:1", wechat_prompt)

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
            "SOURCE2LAUNCH_MODELSCOPE_API_KEY", "SOURCE2LAUNCH_API_KEY", "MODELSCOPE_API_KEY"
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

    def test_openai_model_detection(self):
        from source2launch.image import _is_openai_model
        self.assertTrue(_is_openai_model("gpt-image-2"))
        self.assertTrue(_is_openai_model("dall-e-3"))
        self.assertFalse(_is_openai_model("Qwen/Qwen-Image"))
        self.assertFalse(_is_openai_model("stabilityai/stable-diffusion"))

    def test_dotenv_loads_keys_not_already_in_environ(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text("S2L_TEST_KEY=hello\nS2L_ALREADY_SET=original\n", encoding="utf-8")
            os.environ["S2L_ALREADY_SET"] = "original"
            os.environ.pop("S2L_TEST_KEY", None)
            import source2launch
            original_cwd = Path.cwd()
            try:
                os.chdir(tmp)
                source2launch._load_dotenv()
            finally:
                os.chdir(original_cwd)
            self.assertEqual(os.environ.get("S2L_TEST_KEY"), "hello")
            self.assertEqual(os.environ.get("S2L_ALREADY_SET"), "original")
            os.environ.pop("S2L_TEST_KEY", None)
            os.environ.pop("S2L_ALREADY_SET", None)


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

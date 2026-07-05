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

from source2launch.ai import generate_ai_content, parse_json_content
from source2launch.analyzer import analyze_target, parse_github_owner_repo
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

import base64
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
from source2launch.analyzer import analyze_target
from source2launch.campaign import build_campaign, format_content_review
from source2launch.image import build_promo_image_prompt, generate_image
from source2launch.markdown import generate_markdown_document
from source2launch.optimize import run_optimize
from source2launch.promo_prompts import PROMO_JSON_SCHEMA, build_evidence_brief, build_promo_user_prompt
from source2launch.publish import build_publish_plan, format_publish_plan
from source2launch.server import start_image_api_server
from source2launch.skills import build_promotion_skill_plan


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "test" / "fixtures"


class PythonCoreTest(unittest.TestCase):
    def test_analyzes_healthy_repo(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)

        self.assertEqual(result["project"]["name"], "repo-pulse")
        self.assertEqual(result["project"]["installCommand"], "npx repo-pulse .")
        self.assertGreaterEqual(result["score"], 70)
        self.assertEqual(result["repository"]["readme"], "README.md")
        self.assertTrue(result["evidence"]["visuals"])

    def test_generates_markdown_documents(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        launch = generate_markdown_document(result, markdown_type="launch")
        all_docs = generate_markdown_document(result, markdown_type="all")

        self.assertIn("# Launch Kit: repo-pulse", launch)
        self.assertIn("Product Hunt Draft", launch)
        self.assertIn("---", all_docs)

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

        self.assertEqual(result["source"], "url")
        self.assertEqual(result["inputType"], "url")
        self.assertEqual(result["project"]["name"], "repo-pulse")
        self.assertEqual(result["project"]["repositoryUrl"], "https://github.com/example/repo-pulse")
        self.assertTrue(result["topFixes"])

    def test_builds_skill_plan(self):
        plan = build_promotion_skill_plan("paper-code,social")

        self.assertEqual([skill["name"] for skill in plan["skills"]], ["paper-code", "social"])
        self.assertIn("paper", plan["promptPresets"])
        self.assertIn("Platform alignment", plan["reviewFocus"])

    def test_prompt_schema_requires_quality_rubric(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        payload = {
            "project": result["project"],
            "evidence": result["evidence"],
            "heuristicScore": {"score": result["score"], "grade": result["grade"]},
            "checks": result["checks"],
            "topFixes": result["topFixes"],
        }
        prompt = build_promo_user_prompt(payload, platform="xhs")

        self.assertIn("qualityRubric", PROMO_JSON_SCHEMA)
        self.assertIn("promotionStrategy.qualityRubric", prompt)
        self.assertIn("npx repo-pulse .", build_evidence_brief(payload))

    def test_optimize_writes_reviewable_assets(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "launch-assets"
            manifest = run_optimize(result, cwd=FIXTURES, output_dir=output_dir)

            self.assertIn("INDEX.md", manifest["generated"])
            self.assertIn("content-review.md", manifest["generated"])
            self.assertIn("campaign.json", manifest["generated"])
            review = (output_dir / "content-review.md").read_text(encoding="utf-8")
            self.assertIn("三轴审核", review)
            self.assertIn("Fidelity", review)
            campaign = json.loads((output_dir / "campaign.json").read_text(encoding="utf-8"))
            self.assertEqual(campaign["status"], "needs_model_config")
            self.assertIn("qualityRubric", campaign["reviewGate"])

    def test_optimize_uses_ai_content_when_provided(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        ai_content = sample_ai_content()
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "launch-assets"
            manifest = run_optimize(result, cwd=FIXTURES, output_dir=output_dir, ai_content=ai_content, ai_model="test-model")

            self.assertEqual(manifest["promoSource"], "ai")
            self.assertEqual(manifest["promoModel"], "test-model")
            self.assertIn("AI 小红书正文", (output_dir / "platform/xhs.md").read_text(encoding="utf-8"))
            campaign = json.loads((output_dir / "campaign.json").read_text(encoding="utf-8"))
            self.assertEqual(campaign["status"], "review_required")
            self.assertEqual(campaign["reviewGate"]["qualityRubric"]["fidelity"]["checks"][0], "事实来自 README")

    def test_campaign_and_publish_plan(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        manifest = {"generated": [], "skipped": [], "images": {}, "promoSource": "unavailable", "mode": "full"}
        review = format_content_review(result, manifest)
        campaign = build_campaign(result, manifest)
        plan = build_publish_plan({
            "ai": {
                "content": {
                    "project": result["project"],
                    "promotions": {
                        "xiaohongshu": {
                            "titles": ["开源项目怎么发"],
                            "markdown": "# 小红书\n\n正文",
                            "tags": ["#开源"],
                        }
                    },
                }
            }
        }, {"platform": "xhs", "publishMode": "review"})

        self.assertIn("内容审核清单", review)
        self.assertEqual(campaign["files"]["platforms"]["showHn"], "platform/show-hn.md")
        self.assertEqual(plan["status"], "review_required")
        self.assertIn("Human has reviewed", format_publish_plan(plan))

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
        self.assertEqual(server.last_request["model"], "test-model")
        self.assertIn("promotionStrategy.qualityRubric", server.last_request["messages"][1]["content"])

    def test_parse_json_content_accepts_fenced_json(self):
        parsed = parse_json_content("```json\n{\"ok\": true}\n```")
        self.assertEqual(parsed, {"ok": True})

    def test_python_cli_accepts_subcommand_and_legacy_target(self):
        explicit = subprocess.run(
            [sys.executable, "-m", "source2launch", "analyze", str(FIXTURES / "healthy-repo"), "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        legacy = subprocess.run(
            [sys.executable, "-m", "source2launch", str(FIXTURES / "healthy-repo"), "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertEqual(json.loads(explicit.stdout)["project"]["name"], "repo-pulse")
        self.assertEqual(json.loads(legacy.stdout)["project"]["name"], "repo-pulse")

    def test_python_cli_fail_under_and_intro(self):
        failed = subprocess.run(
            [sys.executable, "-m", "source2launch", str(FIXTURES / "healthy-repo"), "--fail-under", "90"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        intro = subprocess.run(
            [sys.executable, "-m", "source2launch", str(FIXTURES / "healthy-repo"), "--intro"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertEqual(failed.returncode, 1)
        self.assertIn("Source2Launch · Python local analysis", failed.stdout)
        self.assertIn("# repo-pulse", intro.stdout)

    def test_python_cli_skill_context_and_prompt_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes.md"
            notes.write_text("Use a maintainer reading-note voice and mention the demo path.", encoding="utf-8")
            promoted = subprocess.run(
                [
                    sys.executable, "-m", "source2launch", "promote", str(FIXTURES / "healthy-repo"),
                    "--skill", "code",
                    "--context", str(notes),
                    "--prompt-note", "Avoid hype.",
                    "--prompt-preset", "launchkit",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )

        payload = json.loads(promoted.stdout)
        self.assertEqual(payload["platform"], "launch")
        self.assertIn("Task Skill Guidance", payload["user"])
        self.assertIn("Avoid hype.", payload["user"])
        self.assertIn("Use a maintainer reading-note voice", payload["user"])

    def test_source2launch_bin_delegates_to_python_cli(self):
        result = subprocess.run(
            [str(ROOT / "bin" / "source2launch"), "--version"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertEqual(result.stdout.strip(), "0.2.0")

    def test_python_cli_ai_promote_and_optimize_with_mock_server(self):
        server = MockChatServer(sample_ai_content())
        server.start()
        env = {**os.environ, "SOURCE2LAUNCH_API_KEY": "test-key"}
        try:
            promoted = subprocess.run(
                [
                    sys.executable, "-m", "source2launch", "promote", str(FIXTURES / "healthy-repo"),
                    "--ai", "--json", "--base-url", server.base_url, "--model", "test-model",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            with tempfile.TemporaryDirectory() as tmp:
                output_dir = Path(tmp) / "launch-assets"
                subprocess.run(
                    [
                        sys.executable, "-m", "source2launch", "optimize", str(FIXTURES / "healthy-repo"),
                        "--ai", "--base-url", server.base_url, "--model", "test-model", "--output", str(output_dir),
                    ],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=True,
                )
                xhs = (output_dir / "platform" / "xhs.md").read_text(encoding="utf-8")
                campaign = json.loads((output_dir / "campaign.json").read_text(encoding="utf-8"))
        finally:
            server.stop()

        self.assertEqual(json.loads(promoted.stdout)["ai"]["content"]["positioning"], "测试定位")
        self.assertIn("AI 小红书正文", xhs)
        self.assertEqual(campaign["status"], "review_required")

    def test_image_prompt_uses_source_evidence(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        prompt = build_promo_image_prompt(result, platform="xhs")

        self.assertIn("repo-pulse", prompt)
        self.assertIn("npx repo-pulse .", prompt)
        self.assertIn("avoid fake metrics", prompt)

    def test_modelscope_image_generation_with_mock_server(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        server = MockImageServer()
        server.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "promo.png"
                generated = generate_image(result, platform="xhs", output_path=output, options={
                    "provider": "modelscope",
                    "base_url": f"{server.base_url}/v1",
                    "api_key": "test-key",
                    "model": "Qwen/Qwen-Image",
                    "poll_interval_ms": 1,
                    "timeout_ms": 1000,
                })
                image_bytes = output.read_bytes()
        finally:
            server.stop()

        self.assertEqual(generated["provider"], "modelscope")
        self.assertEqual(generated["taskStatus"], "SUCCEED")
        self.assertEqual(image_bytes, PNG_BYTES)
        self.assertEqual(server.modelscope_request["model"], "Qwen/Qwen-Image")
        self.assertEqual(server.modelscope_request["width"], 1104)
        self.assertEqual(server.modelscope_request["height"], 1472)
        self.assertIn("repo-pulse", server.modelscope_request["prompt"])

    def test_gradio_image_generation_with_mock_server(self):
        result = analyze_target("healthy-repo", cwd=FIXTURES)
        server = MockImageServer()
        server.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "gradio.png"
                generated = generate_image(result, prompt="Launch poster", platform="wechat", output_path=output, options={
                    "provider": "gradio",
                    "base_url": server.base_url,
                    "api_name": "generate_image",
                    "seed": 7,
                    "randomize_seed": False,
                    "poll_interval_ms": 1,
                    "timeout_ms": 1000,
                })
                image_bytes = output.read_bytes()
        finally:
            server.stop()

        data = server.gradio_request["data"]
        self.assertEqual(generated["provider"], "gradio")
        self.assertEqual(generated["seed"], 123)
        self.assertEqual(image_bytes, PNG_BYTES)
        self.assertEqual(data[1], "Launch poster")
        self.assertEqual(data[4], 7.0)
        self.assertFalse(data[5])
        self.assertEqual(data[6], 1536)
        self.assertEqual(data[7], 1536)

    def test_python_cli_image_dry_run(self):
        planned = subprocess.run(
            [
                sys.executable, "-m", "source2launch", "image", str(FIXTURES / "healthy-repo"),
                "--dry-run", "--json", "--platform", "xhs",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(planned.stdout)

        self.assertEqual(payload["provider"], "modelscope")
        self.assertEqual(payload["platform"], "xhs")
        self.assertIn("repo-pulse", payload["prompt"])

    def test_python_image_api_health_auth_and_dry_run(self):
        server_info = start_image_api_server({"port": 0, "token": "secret"}, {})
        thread = threading.Thread(target=server_info["server"].serve_forever, daemon=True)
        thread.start()
        try:
            health = request_json(f"{server_info['url']}/health")
            unauthorized = request_json(
                f"{server_info['url']}/v1/images/generations",
                method="POST",
                payload={"prompt": "Launch poster", "dry_run": True},
                expect_status=401,
            )
            generated = request_json(
                f"{server_info['url']}/v1/images/generations",
                method="POST",
                payload={"prompt": "Launch poster", "dry_run": True, "provider": "gradio", "platform": "wechat"},
                headers={"Authorization": "Bearer secret"},
            )
        finally:
            server_info["server"].shutdown()
            thread.join(timeout=5)
            server_info["server"].server_close()

        self.assertTrue(health["ok"])
        self.assertEqual(health["runtime"], "python")
        self.assertEqual(unauthorized["error"]["type"], "unauthorized")
        self.assertEqual(generated["operation"], "generate")
        self.assertEqual(generated["provider"], "gradio")
        self.assertTrue(generated["result"]["dryRun"])
        self.assertEqual(generated["result"]["platform"], "wechat")

    def test_python_image_api_rejects_body_api_keys(self):
        server_info = start_image_api_server({"port": 0}, {})
        thread = threading.Thread(target=server_info["server"].serve_forever, daemon=True)
        thread.start()
        try:
            rejected = request_json(
                f"{server_info['url']}/v1/images/generations",
                method="POST",
                payload={"prompt": "Launch poster", "dry_run": True, "api_key": "secret"},
                expect_status=400,
            )
        finally:
            server_info["server"].shutdown()
            thread.join(timeout=5)
            server_info["server"].server_close()

        self.assertIn("Do not send provider API keys", rejected["error"]["message"])

    def test_source2launch_api_bin_delegates_to_python(self):
        result = subprocess.run(
            [str(ROOT / "bin" / "source2launch-api"), "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertIn("source2launch-api", result.stdout)
        self.assertIn("--token", result.stdout)

    def test_npm_package_manifest_is_python_first(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))

        self.assertEqual(package["bin"]["source2launch"], "./bin/source2launch")
        self.assertEqual(package["bin"]["source2launch-api"], "./bin/source2launch-api")
        self.assertNotIn("src", package["files"])
        self.assertNotIn("scripts", package["files"])
        self.assertIn("scripts/modelscope-image-edit.py", package["files"])
        self.assertIn("scripts/test-and-generate.sh", package["files"])
        self.assertNotIn("dependencies", package)
        self.assertNotIn("exports", package)
        self.assertTrue((ROOT / "bin" / "source2launch").is_file())
        self.assertTrue((ROOT / "bin" / "source2launch-api").is_file())


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
            "zhihu": {"suggestedQuestions": ["如何推广开源项目？"], "markdown": "# 知乎\n\nAI 知乎正文"},
            "wechatMoments": {"markdown": "# 微信\n\nAI 微信正文"},
            "showHn": {"title": "Show HN: Repo Pulse", "markdown": "# Show HN\n\nAI HN body"},
            "productHunt": {"markdown": "# Product Hunt\n\nAI PH body"},
        },
        "launchSequence": [],
    }


class MockChatHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - stdlib callback name.
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.last_request = json.loads(body.decode("utf-8"))
        response = {
            "choices": [{
                "message": {
                    "content": json.dumps(self.server.ai_content, ensure_ascii=False)
                }
            }]
        }
        payload = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature.
        return


class MockChatServer:
    def __init__(self, ai_content):
        self.ai_content = ai_content
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

    def start(self):
        self.thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.thread.join(timeout=5)
        self.httpd.server_close()


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class MockImageHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - stdlib callback name.
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        payload = json.loads(body.decode("utf-8"))
        if self.path == "/v1/images/generations":
            self.server.modelscope_request = payload
            self.write_json({"task_id": "task-1"})
            return
        if self.path == "/call/generate_image":
            self.server.gradio_request = payload
            self.write_json({"event_id": "event-1"})
            return
        self.send_error(404)

    def do_GET(self):  # noqa: N802 - stdlib callback name.
        base_url = self.server.base_url
        if self.path == "/v1/tasks/task-1":
            self.write_json({
                "task_status": "SUCCEED",
                "output_images": [f"{base_url}/generated.png"],
            })
            return
        if self.path == "/call/generate_image/event-1":
            self.write_json({
                "msg": "process_completed",
                "output": {
                    "data": [
                        {"url": f"{base_url}/generated.png"},
                        123,
                        "done",
                    ]
                },
            })
            return
        if self.path == "/generated.png":
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(PNG_BYTES)))
            self.end_headers()
            self.wfile.write(PNG_BYTES)
            return
        self.send_error(404)

    def write_json(self, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature.
        return


class MockImageServer:
    def __init__(self):
        self.httpd = HTTPServer(("127.0.0.1", 0), MockImageHandler)
        host, port = self.httpd.server_address
        self.httpd.base_url = f"http://{host}:{port}"
        self.httpd.modelscope_request = None
        self.httpd.gradio_request = None
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self):
        return self.httpd.base_url

    @property
    def modelscope_request(self):
        return self.httpd.modelscope_request

    @property
    def gradio_request(self):
        return self.httpd.gradio_request

    def start(self):
        self.thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.thread.join(timeout=5)
        self.httpd.server_close()


def request_json(url, *, method="GET", payload=None, headers=None, expect_status=200):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            self_status = response.status
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        self_status = error.code
        body = json.loads(error.read().decode("utf-8"))
    if self_status != expect_status:
        raise AssertionError(f"Expected HTTP {expect_status}, got {self_status}: {body}")
    return body


if __name__ == "__main__":
    unittest.main()

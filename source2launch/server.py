from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .image import build_promo_image_prompt, generate_image, resolve_image_provider

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4317
MAX_BODY_BYTES = 2 * 1024 * 1024


class ApiError(RuntimeError):
    def __init__(self, message: str, *, status: int = 400, error_type: str = "invalid_request"):
        super().__init__(message)
        self.status = status
        self.error_type = error_type


def create_image_api_server(
    options: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
    *,
    host: str | None = None,
    port: int | None = None,
) -> ThreadingHTTPServer:
    options = options or {}
    env = env or os.environ
    bind_host = host or options.get("host") or env.get("SOURCE2LAUNCH_API_HOST") or DEFAULT_HOST
    bind_port = int(port if port is not None else options.get("port") or env.get("SOURCE2LAUNCH_API_PORT") or DEFAULT_PORT)

    class ImageApiHandler(BaseHTTPRequestHandler):
        server_version = "Source2LaunchImageAPI/0.2"

        def do_OPTIONS(self):  # noqa: N802 - stdlib callback name.
            self.send_response(204)
            self.write_cors_headers()
            self.end_headers()

        def do_GET(self):  # noqa: N802 - stdlib callback name.
            if urlparse(self.path).path == "/health":
                self.send_json(200, {"ok": True, "service": "source2launch image api", "runtime": "python"})
                return
            self.send_json(404, {"error": {"message": "Not found", "type": "not_found"}})

        def do_POST(self):  # noqa: N802 - stdlib callback name.
            try:
                self.assert_authorized(options, env)
                path = urlparse(self.path).path
                if path in {"/v1/images/generations", "/api/images/generate"}:
                    body = self.read_json_body()
                    reject_client_api_key(body)
                    result = handle_generation_request(body, env)
                    self.send_json(200, {
                        "ok": True,
                        "operation": "generate",
                        "provider": result.get("provider") or resolve_image_provider(image_options_from_body(body), env),
                        "result": result,
                    })
                    return
                if path in {"/v1/images/edits", "/api/images/edit"}:
                    body = self.read_json_body()
                    reject_client_api_key(body)
                    result = handle_edit_request(body, env)
                    self.send_json(200, {
                        "ok": True,
                        "operation": "edit",
                        "provider": result.get("provider") or resolve_image_provider(image_options_from_body(body), env),
                        "result": result,
                    })
                    return
                self.send_json(404, {"error": {"message": "Not found", "type": "not_found"}})
            except ApiError as error:
                self.send_json(error.status, {"error": {"message": str(error), "type": error.error_type}})
            except Exception as error:  # noqa: BLE001 - API should return structured failures.
                self.send_json(500, {"error": {"message": str(error), "type": "server_error"}})

        def read_json_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                raise ApiError("Request body is too large.", status=413)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as error:
                raise ApiError("Request body must be valid JSON.") from error
            if not isinstance(body, dict):
                raise ApiError("Request body must be a JSON object.")
            return body

        def assert_authorized(self, options: dict[str, Any], env: dict[str, str]) -> None:
            token = options.get("token") or env.get("SOURCE2LAUNCH_API_SERVER_TOKEN")
            if not token:
                return
            authorization = self.headers.get("Authorization") or ""
            header_token = self.headers.get("X-Source2Launch-Token")
            if authorization == f"Bearer {token}" or header_token == token:
                return
            raise ApiError("Unauthorized image API request.", status=401, error_type="unauthorized")

        def send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            self.send_response(status)
            self.write_cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def write_cors_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "authorization, content-type, x-source2launch-token")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

        def log_message(self, format, *args):  # noqa: A002 - stdlib signature.
            if env.get("SOURCE2LAUNCH_API_LOGS"):
                super().log_message(format, *args)

    return ThreadingHTTPServer((bind_host, bind_port), ImageApiHandler)


def start_image_api_server(options: dict[str, Any] | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    server = create_image_api_server(options, env)
    host, port = server.server_address
    return {
        "host": host,
        "port": port,
        "url": f"http://{host}:{port}",
        "server": server,
    }


def run_image_api_cli(argv: list[str] | None = None, env: dict[str, str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    env = env or os.environ
    options = parse_server_args(argv)
    if options.get("help"):
        print(help_text())
        return 0
    server_info = start_image_api_server(options, env)
    print(f"Source2Launch image API listening on {server_info['url']}", flush=True)
    print("POST /v1/images/generations", flush=True)
    print("POST /v1/images/edits", flush=True)
    try:
        server_info["server"].serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server_info["server"].server_close()
    return 0


def handle_generation_request(body: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    prompt = clean_text(body.get("prompt"))
    result = source_result_from_body(body)
    if not prompt and result:
        prompt = build_promo_image_prompt(result, platform=clean_text(body.get("platform")) or "xhs")
    if not prompt:
        raise ApiError("Image generation requires a prompt.")
    options = image_options_from_body(body)
    if body.get("dryRun") or body.get("dry_run"):
        return image_plan(prompt, body, options, env)
    return generate_image(
        result,
        prompt=prompt,
        platform=clean_text(body.get("platform")) or "xhs",
        output_path=body.get("outputPath") or body.get("output_path") or "promo-image.jpg",
        options=options,
        env=env,
    )


def handle_edit_request(body: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    prompt = clean_text(body.get("prompt"))
    if not prompt:
        raise ApiError("Image edit requires a prompt.")
    options = image_options_from_body(body)
    attach_reference_image(options, body)
    if not (options.get("image_url") or options.get("image_base64") or options.get("image_file")):
        raise ApiError("Image edit requires image_url, image_base64, image_file, source_images, or image.")
    if body.get("dryRun") or body.get("dry_run"):
        return image_plan(prompt, body, options, env)
    return generate_image(
        None,
        prompt=prompt,
        platform=clean_text(body.get("platform")) or "xhs",
        output_path=body.get("outputPath") or body.get("output_path") or "promo-image.jpg",
        options=options,
        env=env,
    )


def image_options_from_body(body: dict[str, Any]) -> dict[str, Any]:
    width, height = parse_size(body.get("size"))
    return {
        "provider": body.get("provider"),
        "base_url": body.get("baseUrl") or body.get("base_url"),
        "gradio_url": body.get("gradioUrl") or body.get("gradio_url"),
        "api_name": body.get("apiName") or body.get("api_name"),
        "model": body.get("model"),
        "negative_prompt": body.get("negativePrompt") or body.get("negative_prompt"),
        "image_url": body.get("imageUrl") or body.get("image_url"),
        "image_base64": body.get("imageBase64") or body.get("image_base64"),
        "image_file": body.get("imageFile") or body.get("image_file"),
        "width": body.get("width") or width,
        "height": body.get("height") or height,
        "seed": body.get("seed"),
        "randomize_seed": body.get("randomizeSeed") if "randomizeSeed" in body else body.get("randomize_seed"),
        "prompt_extend": body.get("promptExtend") if "promptExtend" in body else body.get("prompt_extend"),
        "edit_custom_size": body.get("editCustomSize") if "editCustomSize" in body else body.get("edit_custom_size"),
        "poll_interval_ms": body.get("pollIntervalMs") or body.get("poll_interval_ms"),
        "timeout_ms": body.get("taskTimeoutMs") or body.get("task_timeout_ms") or body.get("timeoutMs") or body.get("timeout_ms"),
    }


def image_plan(prompt: str, body: dict[str, Any], options: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    return {
        "provider": resolve_image_provider(options, env),
        "prompt": prompt,
        "model": options.get("model"),
        "platform": clean_text(body.get("platform")) or "xhs",
        "outputPath": body.get("outputPath") or body.get("output_path") or "promo-image.jpg",
        "usesReference": bool(options.get("image_url") or options.get("image_base64") or options.get("image_file")),
        "dryRun": True,
    }


def source_result_from_body(body: dict[str, Any]) -> dict[str, Any] | None:
    project = body.get("project")
    if isinstance(project, dict):
        return {
            "project": project,
            "evidence": body.get("evidence") if isinstance(body.get("evidence"), dict) else {},
        }
    return None


def attach_reference_image(options: dict[str, Any], body: dict[str, Any]) -> None:
    if options.get("image_url") or options.get("image_base64") or options.get("image_file"):
        return
    source_images = body.get("sourceImages") or body.get("source_images") or body.get("image")
    if isinstance(source_images, str):
        if source_images.startswith("http://") or source_images.startswith("https://"):
            options["image_url"] = source_images
        else:
            options["image_base64"] = source_images
    elif isinstance(source_images, list) and source_images:
        first = source_images[0]
        if isinstance(first, str):
            attach_reference_image(options, {"image": first})
        elif isinstance(first, dict):
            options["image_url"] = first.get("url") or first.get("image_url")
            options["image_base64"] = first.get("base64") or first.get("image_base64")
            options["image_file"] = first.get("path") or first.get("image_file")
    elif isinstance(source_images, dict):
        options["image_url"] = source_images.get("url") or source_images.get("image_url")
        options["image_base64"] = source_images.get("base64") or source_images.get("image_base64")
        options["image_file"] = source_images.get("path") or source_images.get("image_file")


def reject_client_api_key(body: dict[str, Any]) -> None:
    if body.get("apiKey") or body.get("api_key") or body.get("authorization"):
        raise ApiError("Do not send provider API keys in the request body. Configure them on the server environment.")


def parse_server_args(args: list[str]) -> dict[str, Any]:
    options: dict[str, Any] = {"help": False, "host": None, "port": None, "token": None}
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in {"--help", "-h"}:
            options["help"] = True
        elif arg == "--host":
            options["host"] = require_value(args, index, "--host")
            index += 1
        elif arg == "--port":
            value = require_value(args, index, "--port")
            port = int(value)
            if port < 0 or port > 65535:
                raise ValueError("--port expects a valid port")
            options["port"] = port
            index += 1
        elif arg == "--token":
            options["token"] = require_value(args, index, "--token")
            index += 1
        else:
            raise ValueError(f"Unknown option: {arg}")
        index += 1
    return options


def require_value(args: list[str], index: int, name: str) -> str:
    if index + 1 >= len(args) or args[index + 1].startswith("--"):
        raise ValueError(f"{name} expects a value")
    return args[index + 1]


def parse_size(value: Any) -> tuple[int | None, int | None]:
    if not value:
        return None, None
    text = str(value).strip().lower()
    if "x" not in text:
        return None, None
    width, height = text.split("x", 1)
    try:
        return int(width), int(height)
    except ValueError:
        return None, None


def help_text() -> str:
    return "\n".join([
        "source2launch-api",
        "",
        "Usage:",
        "  source2launch-api [options]",
        "",
        "Options:",
        "  --host <host>      Host to bind, default 127.0.0.1",
        "  --port <port>      Port to bind, default 4317",
        "  --token <token>    Require Authorization: Bearer <token>",
        "  -h, --help         Show help",
    ])


def clean_text(value: Any) -> str:
    return str(value or "").strip()


if __name__ == "__main__":
    raise SystemExit(run_image_api_cli())

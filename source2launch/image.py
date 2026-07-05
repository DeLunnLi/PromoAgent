"""Image generation and extraction for Source2Launch.

Two image sources:
1. README visual URLs  — download existing screenshots from the project
2. ModelScope AI       — generate a cover image from project evidence
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Platform dimensions
# ---------------------------------------------------------------------------
PLATFORM_DIMS: dict[str, tuple[int, int]] = {
    "xhs":        (1104, 1472),   # 3:4 vertical for Xiaohongshu
    "xiaohongshu":(1104, 1472),
    "wechat":     (1024, 1024),   # 1:1 square for WeChat
    "zhihu":      (1280, 720),    # 16:9 banner
    "twitter":    (1200, 628),    # Twitter card
    "linkedin":   (1200, 628),
    "default":    (1024, 1024),
}

DEFAULT_MODELSCOPE_BASE = "https://api-inference.modelscope.cn/v1"
DEFAULT_IMAGE_MODEL = "Qwen/Qwen-Image"
FETCH_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def image_config(options: dict[str, Any] | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Read image generation configuration from options and environment."""
    options = options or {}
    env = env or os.environ
    api_key = (
        options.get("api_key")
        or env.get("SOURCE2LAUNCH_MODELSCOPE_API_KEY")
        or env.get("SOURCE2LAUNCH_API_KEY")
        or env.get("MODELSCOPE_API_KEY")
    )
    base_url = (
        options.get("base_url")
        or env.get("SOURCE2LAUNCH_BASE_URL")
        or DEFAULT_MODELSCOPE_BASE
    ).rstrip("/")
    model = (
        options.get("model")
        or env.get("SOURCE2LAUNCH_IMAGE_MODEL")
        or DEFAULT_IMAGE_MODEL
    )
    return {
        "apiKey": api_key,
        "baseUrl": base_url,
        "model": model,
        "pollIntervalMs": int(options.get("poll_interval_ms") or env.get("SOURCE2LAUNCH_IMAGE_POLL_MS") or 4000),
        "timeoutMs": int(options.get("timeout_ms") or env.get("SOURCE2LAUNCH_IMAGE_TIMEOUT_MS") or 180_000),
    }


def has_image_key(env: dict[str, str] | None = None) -> bool:
    env = env or os.environ
    return bool(
        env.get("SOURCE2LAUNCH_MODELSCOPE_API_KEY")
        or env.get("SOURCE2LAUNCH_API_KEY")
        or env.get("MODELSCOPE_API_KEY")
    )


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_image_prompt(result: dict[str, Any], *, platform: str = "xhs", style: str = "clean") -> str:
    """Build an image generation prompt from project evidence."""
    project = result.get("project", {})
    name = project.get("name", "Project")
    desc = project.get("description", "")
    topics = project.get("topics") or []
    install_cmd = project.get("installCommand", "")

    fmt = {
        "xhs": "vertical 3:4 poster",
        "xiaohongshu": "vertical 3:4 poster",
        "wechat": "square 1:1 card",
        "zhihu": "wide 16:9 header image",
        "twitter": "wide Twitter card",
        "linkedin": "wide LinkedIn banner",
    }.get(platform, "square card")

    topic_str = ", ".join(topics[:4]) if topics else "open source software"
    desc_short = (desc[:120] + "…") if len(desc) > 120 else desc
    cmd_hint = f"Key command: `{install_cmd}`. " if install_cmd else ""

    return (
        f"Professional tech launch poster for '{name}'. "
        f"{desc_short} "
        f"{cmd_hint}"
        f"Topics: {topic_str}. "
        f"Visual style: {style}, modern, clean, developer-friendly, dark or light background. "
        f"Format: {fmt}. "
        f"No misleading metrics, no fake charts, no stock photos."
    )


# ---------------------------------------------------------------------------
# ModelScope image generation
# ---------------------------------------------------------------------------

def generate_modelscope_image(
    prompt: str,
    *,
    output_path: str | Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Submit an image generation task to ModelScope, poll, download the result."""
    api_key = config["apiKey"]
    base_url = config["baseUrl"]
    model = config["model"]
    poll_sec = config["pollIntervalMs"] / 1000
    timeout_sec = config["timeoutMs"] / 1000

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Determine dimensions from output filename hint or default
    width, height = PLATFORM_DIMS["default"]
    out_str = str(output_path).lower()
    for platform, dims in PLATFORM_DIMS.items():
        if platform in out_str:
            width, height = dims
            break

    # Submit task
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "width": width,
        "height": height,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/images/generations",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            task_data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Image API error {exc.code}: {detail}") from exc

    task_id = task_data.get("task_id") or task_data.get("id")
    if not task_id:
        raise RuntimeError(f"No task_id in response: {task_data}")

    # Poll for result
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        time.sleep(poll_sec)
        req = urllib.request.Request(
            f"{base_url}/tasks/{task_id}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            status_data = json.loads(resp.read())

        status = status_data.get("task_status", "")
        if status == "SUCCEED":
            image_urls = status_data.get("output_images") or []
            if not image_urls:
                raise RuntimeError("Task succeeded but returned no output_images")
            image_url = image_urls[0]
            break
        if status in ("FAILED", "ERROR", "CANCELLED"):
            raise RuntimeError(f"Image generation {status}: {status_data}")
    else:
        raise RuntimeError(f"Image generation timed out after {config['timeoutMs']}ms")

    # Download
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(image_url, out)

    return {
        "provider": "modelscope",
        "model": model,
        "taskId": task_id,
        "outputPath": str(out),
        "width": width,
        "height": height,
    }


# ---------------------------------------------------------------------------
# README image extraction
# ---------------------------------------------------------------------------

def fetch_readme_images(result: dict[str, Any], output_dir: Path) -> list[dict[str, Any]]:
    """Download images from the project's README visual URLs."""
    urls = (result.get("evidence") or {}).get("visualUrls") or []
    saved: list[dict[str, Any]] = []
    if not urls:
        return saved

    output_dir.mkdir(parents=True, exist_ok=True)
    for i, url in enumerate(urls[:4]):
        try:
            ext = "jpg"
            for candidate in (".png", ".gif", ".webp", ".svg"):
                if candidate in url.lower():
                    ext = candidate.lstrip(".")
                    break
            out_path = output_dir / f"readme-{i + 1}.{ext}"
            req = urllib.request.Request(url, headers={"User-Agent": "source2launch/0.2"})
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
                out_path.write_bytes(resp.read())
            saved.append({"url": url, "path": str(out_path), "source": "readme"})
            print(f"source2launch: downloaded readme image → {out_path.name}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"source2launch: could not download {url}: {exc}", file=sys.stderr)

    return saved


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def generate_platform_images(
    result: dict[str, Any],
    output_dir: Path,
    options: dict[str, Any] | None = None,
    *,
    env: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Generate images from both README sources and AI (ModelScope).

    Returns a list of generated image metadata dicts.
    Image generation failures are logged but do not raise.
    """
    options = options or {}
    generated: list[dict[str, Any]] = []

    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # Source 1: README images
    readme_imgs = fetch_readme_images(result, images_dir)
    generated.extend(readme_imgs)

    # Source 2: AI-generated cover images (requires API key)
    # Merge env key into options so image_config and has_image_key both see it
    effective_env = {**(env or os.environ), **({"SOURCE2LAUNCH_API_KEY": options["api_key"]} if options.get("api_key") else {})}
    if not has_image_key(effective_env):
        print(
            "source2launch: no image API key found — skipping AI image generation. "
            "Set SOURCE2LAUNCH_MODELSCOPE_API_KEY to enable.",
            file=sys.stderr,
        )
        return generated

    cfg = image_config(options, effective_env)

    platforms_to_generate = [("xhs", "xhs"), ("wechat", "wechat")]
    for platform, filename_hint in platforms_to_generate:
        try:
            prompt = build_image_prompt(result, platform=platform)
            out_path = images_dir / f"cover-{filename_hint}.jpg"
            print(f"source2launch: generating AI image for {platform}…", file=sys.stderr)
            meta = generate_modelscope_image(prompt, output_path=out_path, config=cfg)
            meta["platform"] = platform
            generated.append(meta)
            print(f"source2launch: image saved → {out_path.name}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"source2launch: image generation failed for {platform}: {exc}", file=sys.stderr)

    return generated

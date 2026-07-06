"""Image generation and extraction for Source2Launch.

Two image sources:
1. README visual URLs  — download existing screenshots from the project
2. AI image model     — generate a cover image from project evidence
   Supported providers:
   - OpenAI  (gpt-image-2, dall-e-3): synchronous, returns base64 or URL
   - ModelScope (Qwen/Qwen-Image):    async task + polling
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Platform dimensions — derived from format, configurable via env
# ---------------------------------------------------------------------------

# Format → (width, height) for ModelScope
_FORMAT_DIMS = {
    "portrait":  (1024, 1536),
    "square":    (1024, 1024),
    "landscape": (1536, 1024),
}

# Format → size string for OpenAI
_FORMAT_OPENAI_SIZES = {
    "portrait":  "1024x1536",
    "square":    "1024x1024",
    "landscape": "1536x1024",
}


def _platform_format(platform: str, env: dict[str, str] | None = None) -> str:
    """Determine image format (portrait/square/landscape) from platform name.

    Configurable: PROMOAGENT_IMAGE_FORMAT=portrait overrides per-platform logic.
    """
    env = env or os.environ
    override = env.get("PROMOAGENT_IMAGE_FORMAT", "").lower().strip()
    if override in _FORMAT_DIMS:
        return override

    p = platform.lower()
    if any(k in p for k in ("xhs", "xiaohongshu", "red", "vertical")):
        return "portrait"
    if any(k in p for k in ("wechat", "moments", "weixin", "square")):
        return "square"
    return "landscape"   # default for Twitter, LinkedIn, zhihu, etc.


def _platform_dims(platform: str, env: dict[str, str] | None = None) -> tuple[int, int]:
    fmt = _platform_format(platform, env)
    return _FORMAT_DIMS.get(fmt, (1024, 1024))


def _platform_openai_size(platform: str, env: dict[str, str] | None = None) -> str:
    fmt = _platform_format(platform, env)
    return _FORMAT_OPENAI_SIZES.get(fmt, "1024x1024")

DEFAULT_OPENAI_BASE  = "https://api.openai.com/v1"
DEFAULT_MODELSCOPE_BASE = "https://api-inference.modelscope.cn/v1"
DEFAULT_IMAGE_MODEL  = "Qwen/Qwen-Image"
FETCH_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------

def _is_openai_model(model: str) -> bool:
    """Return True if the model should use the OpenAI synchronous Images API."""
    return bool(re.search(r"gpt-image|dall-e|gpt-4o", model, re.I))


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def image_config(options: dict[str, Any] | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Read image generation configuration from options and environment."""
    options = options or {}
    env = env or os.environ

    model = (
        options.get("model")
        or env.get("PROMOAGENT_IMAGE_MODEL")
        or DEFAULT_IMAGE_MODEL
    )

    # API key: OpenAI models prefer OPENAI_API_KEY; ModelScope prefers MODELSCOPE key
    if _is_openai_model(model):
        api_key = (
            options.get("api_key")
            or env.get("OPENAI_API_KEY")
            or env.get("PROMOAGENT_API_KEY")
        )
        default_base = DEFAULT_OPENAI_BASE
    else:
        api_key = (
            options.get("api_key")
            or env.get("PROMOAGENT_MODELSCOPE_API_KEY")
            or env.get("PROMOAGENT_API_KEY")
            or env.get("MODELSCOPE_API_KEY")
        )
        default_base = DEFAULT_MODELSCOPE_BASE

    base_url = (
        options.get("base_url")
        or env.get("PROMOAGENT_BASE_URL")
        or default_base
    ).rstrip("/")

    return {
        "apiKey": api_key,
        "baseUrl": base_url,
        "model": model,
        "quality": options.get("quality") or env.get("PROMOAGENT_IMAGE_QUALITY") or "medium",
        "pollIntervalMs": int(options.get("poll_interval_ms") or env.get("PROMOAGENT_IMAGE_POLL_MS") or 4000),
        "timeoutMs": int(options.get("timeout_ms") or env.get("PROMOAGENT_IMAGE_TIMEOUT_MS") or 180_000),
    }


def has_image_key(env: dict[str, str] | None = None) -> bool:
    env = env or os.environ
    return bool(
        env.get("OPENAI_API_KEY")
        or env.get("PROMOAGENT_MODELSCOPE_API_KEY")
        or env.get("PROMOAGENT_API_KEY")
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

    # Derive dimensions from output filename (platform hint)
    out_stem = Path(output_path).stem.lower()
    width, height = _platform_dims(out_stem)

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
# OpenAI image generation (gpt-image-2, dall-e-3 — synchronous)
# ---------------------------------------------------------------------------

def generate_openai_image(
    prompt: str,
    *,
    output_path: str | Path,
    config: dict[str, Any],
    platform: str = "default",
) -> dict[str, Any]:
    """Generate an image via OpenAI Images API (gpt-image-2, dall-e-3).

    Synchronous — response contains base64 JSON or a URL directly.
    """
    api_key = config["apiKey"]
    base_url = config["baseUrl"]
    model = config["model"]
    quality = config.get("quality", "medium")
    size = _platform_openai_size(platform)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # gpt-image-2 returns b64_json by default; url is also supported
    body_dict: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "n": 1,
    }
    # gpt-image-2 supports quality; dall-e-3 uses "hd"/"standard"
    if re.search(r"gpt-image", model, re.I):
        body_dict["quality"] = quality         # low / medium / high / auto
        body_dict["output_format"] = "png"
    else:
        body_dict["quality"] = "hd" if quality in ("high", "hd") else "standard"
        body_dict["response_format"] = "b64_json"

    body = json.dumps(body_dict).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/images/generations",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=config["timeoutMs"] / 1000) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI Image API error {exc.code}: {detail}") from exc

    items = data.get("data") or []
    if not items:
        raise RuntimeError(f"No image data in response: {data}")

    item = items[0]
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if item.get("b64_json"):
        out.write_bytes(base64.b64decode(item["b64_json"]))
    elif item.get("url"):
        urllib.request.urlretrieve(item["url"], out)
    else:
        raise RuntimeError(f"Response item has neither b64_json nor url: {item}")

    return {
        "provider": "openai",
        "model": model,
        "outputPath": str(out),
        "size": size,
        "quality": quality,
        "platform": platform,
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
            req = urllib.request.Request(url, headers={"User-Agent": "promoagent/0.2"})
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
                out_path.write_bytes(resp.read())
            saved.append({"url": url, "path": str(out_path), "source": "readme"})
            print(f"promoagent: downloaded readme image → {out_path.name}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"promoagent: could not download {url}: {exc}", file=sys.stderr)

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
    effective_env = {**(env or os.environ), **({"PROMOAGENT_API_KEY": options["api_key"]} if options.get("api_key") else {})}
    if not has_image_key(effective_env):
        print(
            "promoagent: no image API key found — skipping AI image generation. "
            "Set PROMOAGENT_MODELSCOPE_API_KEY to enable.",
            file=sys.stderr,
        )
        return generated

    cfg = image_config(options, effective_env)
    use_openai = _is_openai_model(cfg["model"])
    provider_label = "openai" if use_openai else "modelscope"
    print(f"promoagent: image provider → {provider_label} ({cfg['model']})", file=sys.stderr)

    platforms_to_generate = [("xhs", "xhs"), ("wechat", "wechat")]
    for platform, filename_hint in platforms_to_generate:
        try:
            prompt = build_image_prompt(result, platform=platform)
            ext = "png" if use_openai else "jpg"
            out_path = images_dir / f"cover-{filename_hint}.{ext}"
            print(f"promoagent: generating image for {platform}…", file=sys.stderr)

            if use_openai:
                meta = generate_openai_image(prompt, output_path=out_path, config=cfg, platform=platform)
            else:
                meta = generate_modelscope_image(prompt, output_path=out_path, config=cfg)
                meta["platform"] = platform

            generated.append(meta)
            print(f"promoagent: image saved → {out_path.name}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"promoagent: image generation failed for {platform}: {exc}", file=sys.stderr)

    return generated

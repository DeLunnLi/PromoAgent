from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_MODELSCOPE_BASE_URL = "https://api-inference.modelscope.cn/"
DEFAULT_MODELSCOPE_IMAGE_MODEL = "Qwen/Qwen-Image"
DEFAULT_MODELSCOPE_TASK_TYPE = "image_generation"
DEFAULT_GRADIO_URL = "http://127.0.0.1:7860"
DEFAULT_GRADIO_API = "generate_image"


def build_promo_image_prompt(result: dict[str, Any], *, platform: str = "xhs", style: str = "clean") -> str:
    project = result.get("project", {})
    evidence = result.get("evidence", {})
    name = project.get("name") or "Source project"
    description = project.get("description") or "source-grounded launch content"
    install = project.get("installCommand")
    topics = ", ".join(project.get("topics") or [])
    visual_count = len(evidence.get("visuals") or []) + len(evidence.get("visualUrls") or [])
    platform_hint = {
        "xhs": "vertical Xiaohongshu cover poster, readable Chinese title area",
        "xiaohongshu": "vertical Xiaohongshu cover poster, readable Chinese title area",
        "wechat": "square WeChat article cover, calm technical editorial style",
        "zhihu": "clean Zhihu answer header, technical and credible",
        "twitter": "wide technical launch card for an engineering thread",
        "producthunt": "polished Product Hunt launch thumbnail",
    }.get(normalize_platform(platform), "technical launch poster")

    lines = [
        f"Create a {platform_hint} for {name}.",
        f"Core message: {finish_sentence(description)}",
        "Use a source-grounded, human-written launch style; avoid fake metrics, fake logos, fake testimonials, or exaggerated claims.",
        f"Visual style: {style}, crisp typography, high contrast, practical developer-tool aesthetic.",
    ]
    if install:
        lines.append(f"Include the exact command as small supporting text: {install}")
    if topics:
        lines.append(f"Use subtle visual cues for these topics: {topics}.")
    if visual_count:
        lines.append("Leave space for a real screenshot or paper figure to be layered by the user later.")
    return " ".join(lines)


def generate_image(
    result: dict[str, Any] | None = None,
    *,
    prompt: str | None = None,
    platform: str = "xhs",
    output_path: str | Path = "promo-image.jpg",
    options: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    options = dict(options or {})
    env = env or os.environ
    final_prompt = str(prompt or "").strip()
    if not final_prompt:
        if result is None:
            raise RuntimeError("Image generation requires a prompt or analyzed source result.")
        final_prompt = build_promo_image_prompt(result, platform=platform, style=str(options.get("style") or "clean"))
    provider = resolve_image_provider(options, env)
    if provider == "gradio":
        return generate_gradio_image(final_prompt, platform=platform, output_path=output_path, options=options, env=env)
    return generate_modelscope_image(final_prompt, platform=platform, output_path=output_path, options=options, env=env)


def resolve_image_provider(options: dict[str, Any] | None = None, env: dict[str, str] | None = None) -> str:
    options = options or {}
    env = env or os.environ
    explicit = str(options.get("provider") or env.get("SOURCE2LAUNCH_IMAGE_PROVIDER") or "").strip().lower()
    if explicit in {"gradio", "modelscope"}:
        return explicit
    if options.get("gradio_url") or env.get("SOURCE2LAUNCH_GRADIO_URL") or env.get("GRADIO_URL"):
        return "gradio"
    return "modelscope"


def modelscope_image_config(options: dict[str, Any] | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    options = options or {}
    env = env or os.environ
    api_key = (
        options.get("api_key")
        or env.get("SOURCE2LAUNCH_MODELSCOPE_API_KEY")
        or env.get("SOURCE2LAUNCH_IMAGE_API_KEY")
        or env.get("MODELSCOPE_API_KEY")
    )
    if not api_key:
        raise RuntimeError("Missing ModelScope image API key. Set SOURCE2LAUNCH_MODELSCOPE_API_KEY or MODELSCOPE_API_KEY.")
    return {
        "apiKey": api_key,
        "baseUrl": normalize_modelscope_base_url(options.get("base_url") or env.get("SOURCE2LAUNCH_MODELSCOPE_BASE_URL") or env.get("MODELSCOPE_BASE_URL") or DEFAULT_MODELSCOPE_BASE_URL),
        "model": options.get("model") or env.get("SOURCE2LAUNCH_IMAGE_MODEL") or env.get("MODELSCOPE_IMAGE_MODEL") or DEFAULT_MODELSCOPE_IMAGE_MODEL,
        "pollInterval": float(options.get("poll_interval_ms") or env.get("SOURCE2LAUNCH_IMAGE_POLL_MS") or 5000) / 1000,
        "timeout": float(options.get("timeout_ms") or env.get("SOURCE2LAUNCH_IMAGE_TIMEOUT_MS") or 300000) / 1000,
        "taskType": options.get("task_type") or env.get("SOURCE2LAUNCH_IMAGE_TASK_TYPE") or DEFAULT_MODELSCOPE_TASK_TYPE,
    }


def generate_modelscope_image(
    prompt: str,
    *,
    platform: str = "xhs",
    output_path: str | Path = "promo-image.jpg",
    options: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    options = options or {}
    env = env or os.environ
    config = modelscope_image_config(options, env)
    payload: dict[str, Any] = {
        "model": config["model"],
        "prompt": prompt,
    }
    negative_prompt = options.get("negative_prompt") or env.get("SOURCE2LAUNCH_IMAGE_NEGATIVE_PROMPT")
    if negative_prompt is not None:
        payload["negative_prompt"] = str(negative_prompt)

    image_url = str(options.get("image_url") or "").strip()
    image_file = options.get("image_file")
    image_base64 = str(options.get("image_base64") or "").strip()
    has_reference = bool(image_url or image_file or image_base64)
    if image_url:
        payload["image_url"] = image_url
    elif image_base64:
        payload["image"] = image_base64
    elif image_file:
        payload["image"] = read_image_as_data_url(image_file)
    elif modelscope_image_requires_reference(config["model"]):
        raise RuntimeError(
            f"Model {config['model']} requires a reference image. Provide --image-url or --image-file, or use Qwen/Qwen-Image."
        )

    if not modelscope_image_requires_reference(config["model"]) or has_reference:
        dimensions = resolve_image_dimensions(platform, options, env)
        payload["width"] = dimensions["width"]
        payload["height"] = dimensions["height"]
    else:
        dimensions = None

    task_id = submit_modelscope_image_task(config, payload)
    task = poll_modelscope_image_task(config, task_id)
    remote_url = task["outputImages"][0]
    image_bytes = download_bytes(resolve_url(remote_url, config["baseUrl"]))
    final_path = write_image_file(output_path, image_bytes)
    return {
        "provider": "modelscope",
        "taskId": task_id,
        "model": config["model"],
        "prompt": prompt,
        "remoteUrl": remote_url,
        "outputPath": str(final_path),
        "taskStatus": task["taskStatus"],
        "dimensions": dimensions,
    }


def submit_modelscope_image_task(config: dict[str, Any], payload: dict[str, Any]) -> str:
    response = post_json(
        urllib.parse.urljoin(config["baseUrl"], "v1/images/generations"),
        payload,
        headers={
            "Authorization": f"Bearer {config['apiKey']}",
            "X-ModelScope-Async-Mode": "true",
        },
        timeout=config["timeout"],
    )
    task_id = response.get("task_id")
    if not task_id:
        raise RuntimeError("ModelScope image API did not return task_id.")
    return str(task_id)


def poll_modelscope_image_task(config: dict[str, Any], task_id: str) -> dict[str, Any]:
    started = time.monotonic()
    while time.monotonic() - started < config["timeout"]:
        response = get_json(
            urllib.parse.urljoin(config["baseUrl"], f"v1/tasks/{task_id}"),
            headers={
                "Authorization": f"Bearer {config['apiKey']}",
                "X-ModelScope-Task-Type": config["taskType"],
            },
            timeout=config["timeout"],
        )
        status = str(response.get("task_status") or "").upper()
        if status == "SUCCEED":
            output_images = response.get("output_images") or []
            if not output_images:
                raise RuntimeError("ModelScope image task succeeded but returned no output_images.")
            return {"taskStatus": status, "outputImages": output_images}
        if status == "FAILED":
            reason = response.get("error_message") or response.get("message") or "unknown error"
            raise RuntimeError(f"ModelScope image generation failed: {reason}")
        time.sleep(config["pollInterval"])
    raise RuntimeError(f"ModelScope image generation timed out after {int(config['timeout'] * 1000)}ms.")


def gradio_image_config(options: dict[str, Any] | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    options = options or {}
    env = env or os.environ
    return {
        "baseUrl": normalize_base_url(options.get("gradio_url") or options.get("base_url") or env.get("SOURCE2LAUNCH_GRADIO_URL") or env.get("GRADIO_URL") or DEFAULT_GRADIO_URL, trailing=False),
        "apiName": normalize_api_name(options.get("api_name") or env.get("SOURCE2LAUNCH_GRADIO_API") or DEFAULT_GRADIO_API),
        "promptExtend": parse_bool(options.get("prompt_extend") if "prompt_extend" in options else env.get("SOURCE2LAUNCH_GRADIO_PROMPT_EXTEND"), True),
        "editCustomSize": parse_bool(options.get("edit_custom_size") if "edit_custom_size" in options else env.get("SOURCE2LAUNCH_GRADIO_EDIT_CUSTOM_SIZE"), False),
        "seed": float(options.get("seed") or env.get("SOURCE2LAUNCH_GRADIO_SEED") or 0),
        "randomizeSeed": parse_bool(options.get("randomize_seed") if "randomize_seed" in options else env.get("SOURCE2LAUNCH_GRADIO_RANDOMIZE_SEED"), True),
        "negativePrompt": str(options.get("negative_prompt") if options.get("negative_prompt") is not None else env.get("SOURCE2LAUNCH_GRADIO_NEGATIVE_PROMPT") or " "),
        "pollInterval": float(options.get("poll_interval_ms") or env.get("SOURCE2LAUNCH_GRADIO_POLL_MS") or 2000) / 1000,
        "timeout": float(options.get("timeout_ms") or env.get("SOURCE2LAUNCH_GRADIO_TIMEOUT_MS") or 600000) / 1000,
    }


def build_gradio_predict_payload(prompt: str, config: dict[str, Any], dimensions: dict[str, int], options: dict[str, Any] | None = None) -> list[Any]:
    options = options or {}
    input_images: list[Any] = []
    image_url = str(options.get("image_url") or "").strip()
    if image_url:
        input_images.append({"image": {"url": image_url, "path": None, "is_stream": False, "meta": {}}, "caption": None})
    elif options.get("image_file"):
        input_images.append({"image": {"url": read_image_as_data_url(options["image_file"]), "path": None, "is_stream": False, "meta": {}}, "caption": None})
    return [
        input_images,
        str(prompt).strip(),
        config["promptExtend"],
        config["editCustomSize"],
        config["seed"],
        config["randomizeSeed"],
        dimensions["height"],
        dimensions["width"],
        config["negativePrompt"],
    ]


def generate_gradio_image(
    prompt: str,
    *,
    platform: str = "xhs",
    output_path: str | Path = "promo-image.jpg",
    options: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    options = options or {}
    env = env or os.environ
    config = gradio_image_config(options, env)
    dimensions = resolve_gradio_dimensions(platform, options, env)
    data = build_gradio_predict_payload(prompt, config, dimensions, options)
    event_id = submit_gradio_call(config, data)
    result = poll_gradio_call(config, event_id)
    image_ref = (result.get("data") or [None])[0]
    remote_url = resolve_gradio_image_url(image_ref, config["baseUrl"])
    image_bytes = download_bytes(remote_url)
    final_path = write_image_file(output_path, image_bytes)
    return {
        "provider": "gradio",
        "taskId": event_id,
        "model": config["apiName"],
        "prompt": prompt,
        "seed": (result.get("data") or [None, None])[1],
        "remoteUrl": remote_url,
        "outputPath": str(final_path),
        "queueStatus": (result.get("data") or [None, None, None])[2],
        "dimensions": dimensions,
    }


def submit_gradio_call(config: dict[str, Any], data: list[Any]) -> str:
    response = post_json(f"{config['baseUrl']}/call/{config['apiName']}", {"data": data}, timeout=config["timeout"])
    event_id = response.get("event_id")
    if not event_id:
        raise RuntimeError("Gradio API did not return event_id.")
    return str(event_id)


def poll_gradio_call(config: dict[str, Any], event_id: str) -> dict[str, Any]:
    started = time.monotonic()
    while time.monotonic() - started < config["timeout"]:
        response = get_json(f"{config['baseUrl']}/call/{config['apiName']}/{event_id}", timeout=config["timeout"])
        message = str(response.get("msg") or "")
        if message == "process_completed":
            output = response.get("output") or {}
            if not output.get("data"):
                raise RuntimeError("Gradio image task completed but returned no output data.")
            return output
        if message == "process_error":
            reason = (response.get("output") or {}).get("error") or response.get("title") or "unknown error"
            raise RuntimeError(f"Gradio image generation failed: {reason}")
        time.sleep(config["pollInterval"])
    raise RuntimeError(f"Gradio image generation timed out after {int(config['timeout'] * 1000)}ms.")


def resolve_image_dimensions(platform: str, options: dict[str, Any] | None = None, env: dict[str, str] | None = None) -> dict[str, int]:
    options = options or {}
    env = env or os.environ
    if options.get("width") and options.get("height"):
        return {"width": int(options["width"]), "height": int(options["height"])}
    size = str(env.get("SOURCE2LAUNCH_IMAGE_SIZE") or "").strip().lower()
    if "x" in size:
        width, height = size.split("x", 1)
        return {"width": int(width), "height": int(height)}
    if normalize_platform(platform) == "wechat":
        square = int(env.get("SOURCE2LAUNCH_IMAGE_WECHAT_SIZE") or 1024)
        return {"width": square, "height": square}
    return {
        "width": int(env.get("SOURCE2LAUNCH_IMAGE_WIDTH") or 1104),
        "height": int(env.get("SOURCE2LAUNCH_IMAGE_HEIGHT") or 1472),
    }


def resolve_gradio_dimensions(platform: str, options: dict[str, Any] | None = None, env: dict[str, str] | None = None) -> dict[str, int]:
    options = options or {}
    env = env or os.environ
    if options.get("width") and options.get("height"):
        return {"width": int(options["width"]), "height": int(options["height"])}
    if normalize_platform(platform) == "wechat":
        square = int(env.get("SOURCE2LAUNCH_GRADIO_WECHAT_SIZE") or 1536)
        return {"width": square, "height": square}
    return {
        "width": int(env.get("SOURCE2LAUNCH_GRADIO_WIDTH") or 2688),
        "height": int(env.get("SOURCE2LAUNCH_GRADIO_HEIGHT") or 1536),
    }


def resolve_gradio_image_url(result_image: Any, base_url: str) -> str:
    if isinstance(result_image, str):
        if result_image.startswith("http://") or result_image.startswith("https://") or result_image.startswith("data:"):
            return result_image
        if result_image.startswith("/file="):
            return f"{base_url}{result_image}"
        if result_image.startswith("file="):
            return f"{base_url}/{result_image}"
        return f"{base_url}/file={urllib.parse.quote(result_image)}"
    if isinstance(result_image, dict):
        if result_image.get("url"):
            return str(result_image["url"])
        if result_image.get("path"):
            return f"{base_url}/file={urllib.parse.quote(str(result_image['path']))}"
    raise RuntimeError("Gradio returned an unrecognized image result.")


def post_json(url: str, body: dict[str, Any], *, headers: dict[str, str] | None = None, timeout: float = 120) -> dict[str, Any]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Image API request failed with HTTP {error.code}: {detail}") from error


def get_json(url: str, *, headers: dict[str, str] | None = None, timeout: float = 120) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Image API poll failed with HTTP {error.code}: {detail}") from error


def download_bytes(url: str) -> bytes:
    if url.startswith("data:"):
        _, encoded = url.split(",", 1)
        return base64.b64decode(encoded)
    with urllib.request.urlopen(url) as response:
        return response.read()


def write_image_file(output_path: str | Path, image_bytes: bytes) -> Path:
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image_bytes)
    return path


def read_image_as_data_url(file_path: str | Path) -> str:
    path = Path(file_path).expanduser().resolve()
    mime = {
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(path.suffix.lower(), "image/jpeg")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def modelscope_image_requires_reference(model_id: str) -> bool:
    model = str(model_id or "").lower()
    return "image-edit" in model or "image_edit" in model or "-edit-" in model or "/fire" in model


def normalize_api_name(value: str) -> str:
    return str(value).strip().lstrip("/")


def normalize_base_url(value: str, *, trailing: bool) -> str:
    cleaned = str(value).strip()
    return cleaned.rstrip("/") + "/" if trailing else cleaned.rstrip("/")


def normalize_modelscope_base_url(value: str) -> str:
    cleaned = normalize_base_url(value, trailing=False)
    if cleaned.endswith("/v1"):
        cleaned = cleaned[:-3]
    return f"{cleaned}/"


def normalize_platform(platform: str) -> str:
    normalized = str(platform or "xhs").strip().lower().replace("-", "")
    if normalized in {"wechat", "weixin", "wx"}:
        return "wechat"
    if normalized in {"producthunt", "ph"}:
        return "producthunt"
    if normalized in {"xiaohongshu", "redbook", "xhs"}:
        return "xhs"
    return normalized


def finish_sentence(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text[-1] in ".!?。！？":
        return text
    return f"{text}."


def parse_bool(value: Any, fallback: bool) -> bool:
    if value is None or value == "":
        return fallback
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"false", "0", "no", "off"}


def resolve_url(value: str, base_url: str) -> str:
    if value.startswith("http://") or value.startswith("https://") or value.startswith("data:"):
        return value
    return urllib.parse.urljoin(base_url, value)

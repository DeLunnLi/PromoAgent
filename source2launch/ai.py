from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from .promo_prompts import build_promo_system_prompt, build_promo_user_prompt

DEFAULT_BASE_URL = "https://api.openai.com/v1"
MODELSCOPE_BASE_URL = "https://api-inference.modelscope.cn/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_MODELSCOPE_MODEL = "Qwen/Qwen3.5-397B-A17B"


def ai_config(options: dict[str, Any] | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    options = options or {}
    env = env or os.environ
    api_key = (
        options.get("api_key")
        or env.get("SOURCE2LAUNCH_API_KEY")
        or env.get("SOURCE2LAUNCH_MODELSCOPE_API_KEY")
        or env.get("OPENAI_API_KEY")
        or env.get("MODELSCOPE_API_KEY")
    )
    modelscope_key = bool(env.get("SOURCE2LAUNCH_MODELSCOPE_API_KEY") or env.get("MODELSCOPE_API_KEY"))
    base_url = (
        options.get("base_url")
        or env.get("SOURCE2LAUNCH_BASE_URL")
        or env.get("OPENAI_BASE_URL")
        or (MODELSCOPE_BASE_URL if modelscope_key and not env.get("SOURCE2LAUNCH_API_KEY") and not env.get("OPENAI_API_KEY") else DEFAULT_BASE_URL)
    )
    model = (
        options.get("model")
        or env.get("SOURCE2LAUNCH_MODEL")
        or env.get("OPENAI_MODEL")
        or (DEFAULT_MODELSCOPE_MODEL if base_url.rstrip("/") == MODELSCOPE_BASE_URL else DEFAULT_MODEL)
    )
    return {
        "apiKey": api_key,
        "baseUrl": str(base_url).rstrip("/"),
        "model": model,
        "maxTokens": int(options.get("max_tokens") or env.get("SOURCE2LAUNCH_MAX_TOKENS") or (4096 if "modelscope" in str(base_url).lower() else 1800)),
        "temperature": float(options.get("temperature") if options.get("temperature") is not None else env.get("SOURCE2LAUNCH_TEMPERATURE") or 0.7),
        "timeout": float(options.get("timeout") or env.get("SOURCE2LAUNCH_TIMEOUT_MS") or 120_000) / 1000,
    }


def has_ai_key(env: dict[str, str] | None = None) -> bool:
    env = env or os.environ
    return bool(env.get("SOURCE2LAUNCH_API_KEY") or env.get("SOURCE2LAUNCH_MODELSCOPE_API_KEY") or env.get("OPENAI_API_KEY") or env.get("MODELSCOPE_API_KEY"))


def build_promo_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "project": result.get("project", {}),
        "evidence": result.get("evidence", {}),
        "target": result.get("target"),
        "source": result.get("source"),
        "inputType": result.get("inputType"),
    }


def build_promo_messages(
    result: dict[str, Any],
    *,
    platform: str = "all",
    brief_section: str = "",
    examples: list[str] | None = None,
) -> list[dict[str, str]]:
    payload = build_promo_payload(result)
    return [
        {"role": "system", "content": build_promo_system_prompt()},
        {"role": "user", "content": build_promo_user_prompt(
            payload, platform=platform, brief_section=brief_section, examples=examples
        )},
    ]


def generate_ai_content(
    result: dict[str, Any],
    *,
    platform: str = "all",
    brief_section: str = "",
    examples: list[str] | None = None,
    options: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    config = ai_config(options, env)
    if not config["apiKey"]:
        raise RuntimeError("Missing AI API key. Set SOURCE2LAUNCH_API_KEY or SOURCE2LAUNCH_MODELSCOPE_API_KEY.")
    messages = build_promo_messages(result, platform=platform, brief_section=brief_section, examples=examples)
    url = f"{config['baseUrl']}/chat/completions"
    headers = {"Authorization": f"Bearer {config['apiKey']}"}
    base_body: dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "temperature": config["temperature"],
        "max_tokens": config["maxTokens"],
    }
    # Try with response_format first; fall back if the provider does not support it.
    try:
        response = post_json(url, {**base_body, "response_format": {"type": "json_object"}}, headers=headers, timeout=config["timeout"])
    except RuntimeError as exc:
        err = str(exc).lower()
        if "response_format" in err or "json_object" in err or "unsupported" in err or "invalid" in err:
            response = post_json(url, base_body, headers=headers, timeout=config["timeout"])
        else:
            raise
    content = extract_chat_content(response)
    parsed = parse_json_content(content)
    return {
        "content": parsed,
        "rawContent": content,
        "model": config["model"],
        "baseUrl": config["baseUrl"],
    }


def post_json(url: str, body: dict[str, Any], *, headers: dict[str, str] | None = None, timeout: float = 120) -> dict[str, Any]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"AI request failed with HTTP {error.code}: {detail}") from error


def extract_chat_content(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError("AI response did not contain choices.")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        raise RuntimeError("AI response did not contain message content.")
    return str(content)


def parse_json_content(content: str) -> dict[str, Any]:
    text = str(content or "").strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.I)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise

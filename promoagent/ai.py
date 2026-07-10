"""AI content generation utilities for PromoAgent.

Core utilities for interacting with LLM providers.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import urllib.error
import urllib.request
from typing import Any

from .logger import logger

_PROVIDER_DEFAULTS = {
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "anthropic": {"base_url": "https://api.anthropic.com", "model": "claude-haiku-4-5"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com", "model": "gemini-2.0-flash"},
    "ollama": {"base_url": "http://localhost:11434", "model": "llama3.2"},
    "modelscope": {"base_url": "https://api-inference.modelscope.cn/v1", "model": "Qwen/Qwen3.5-397B-A17B"},
}

_KEY_MAP = {
    "anthropic": ["ANTHROPIC_API_KEY", "PROMOAGENT_API_KEY"],
    "gemini": ["GOOGLE_API_KEY", "GEMINI_API_KEY", "PROMOAGENT_API_KEY"],
    "ollama": ["OLLAMA_API_KEY"],
    "modelscope": ["PROMOAGENT_MODELSCOPE_API_KEY", "MODELSCOPE_API_KEY", "PROMOAGENT_API_KEY"],
    "openai": ["PROMOAGENT_API_KEY", "OPENAI_API_KEY", "MODELSCOPE_API_KEY"],
}


def _detect_provider(options: dict[str, Any], env: dict[str, str]) -> str:
    """Detect the LLM provider from options and environment."""
    if explicit := (options.get("provider") or env.get("PROMOAGENT_PROVIDER", "")):
        return explicit.lower().strip()

    # Key-based detection
    if options.get("api_key", "").startswith("sk-ant-") or env.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if env.get("GOOGLE_API_KEY") or env.get("GEMINI_API_KEY"):
        return "gemini"
    if env.get("OLLAMA_BASE_URL") or env.get("OLLAMA_HOST"):
        return "ollama"
    if env.get("PROMOAGENT_MODELSCOPE_API_KEY") or env.get("MODELSCOPE_API_KEY"):
        return "modelscope"

    # Model-name hints
    model = options.get("model") or env.get("PROMOAGENT_MODEL") or ""
    if re.match(r"^claude", model, re.I):
        return "anthropic"
    if re.match(r"^gemini", model, re.I):
        return "gemini"
    if re.match(r"^(llama|mistral|qwen|phi|deepseek)", model, re.I) and not env.get("PROMOAGENT_API_KEY"):
        return "ollama"

    # Base URL hints
    base_url = options.get("base_url") or env.get("PROMOAGENT_BASE_URL") or ""
    for provider, hint in [("anthropic", "anthropic"), ("gemini", "googleapis"), ("ollama", "localhost:11434"), ("modelscope", "modelscope")]:
        if hint in base_url:
            return provider

    return "openai"


def ai_config(options: dict[str, Any] | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Build unified AI configuration, auto-detecting provider."""
    options = options or {}
    env = os.environ if env is None else env
    provider = _detect_provider(options, env)
    defaults = _PROVIDER_DEFAULTS.get(provider, _PROVIDER_DEFAULTS["openai"])

    # Get API key
    api_key = options.get("api_key") or ""
    for key_name in _KEY_MAP.get(provider, []):
        if not api_key:
            api_key = env.get(key_name, "")

    base_url = options.get("base_url") or env.get("PROMOAGENT_BASE_URL") or defaults["base_url"]
    if provider == "ollama":
        base_url = options.get("base_url") or env.get("OLLAMA_BASE_URL") or env.get("OLLAMA_HOST") or defaults["base_url"]

    base_url = base_url.rstrip("/")
    # Ollama's OpenAI-compatible endpoint lives under /v1; append it when the
    # user gave a bare host (e.g. http://localhost:11434) without a version path.
    if provider == "ollama" and not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    return {
        "provider": provider,
        "apiKey": api_key,
        "baseUrl": base_url,
        "model": options.get("model") or env.get("PROMOAGENT_MODEL") or defaults["model"],
        "maxTokens": int(options.get("max_tokens") or env.get("PROMOAGENT_MAX_TOKENS") or 4096),
        "temperature": float(options.get("temperature") if options.get("temperature") is not None else env.get("PROMOAGENT_TEMPERATURE") or 0.7),
        "timeout": float(options.get("timeout") or env.get("PROMOAGENT_TIMEOUT_MS") or 120_000) / 1000,
    }


def has_ai_key(env: dict[str, str] | None = None) -> bool:
    env = os.environ if env is None else env
    keys = ["PROMOAGENT_API_KEY", "PROMOAGENT_MODELSCOPE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY", "OLLAMA_BASE_URL", "OLLAMA_HOST"]
    return any(env.get(k) for k in keys)


def post_json(url: str, data: dict[str, Any], headers: dict[str, str] | None = None, timeout: float = 60) -> dict[str, Any]:
    """POST JSON to API and return JSON response."""
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={**(headers or {}), "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def dispatch_chat(messages: list[dict[str, str]], config: dict[str, Any]) -> str:
    """Dispatch chat completion request based on provider."""
    provider = config.get("provider", "openai")

    if provider in ("openai", "modelscope", "ollama"):
        # Ollama exposes an OpenAI-compatible /v1/chat/completions endpoint.
        return _dispatch_openai(messages, config)
    elif provider == "anthropic":
        return _dispatch_anthropic(messages, config)
    elif provider == "gemini":
        return _dispatch_gemini(messages, config)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def _dispatch_openai(messages: list[dict[str, str]], config: dict[str, Any]) -> str:
    """Dispatch to OpenAI-compatible API."""
    resp = post_json(
        f"{config['baseUrl']}/chat/completions",
        {
            "model": config["model"],
            "messages": messages,
            "temperature": config["temperature"],
            "max_tokens": config["maxTokens"],
        },
        headers={"Authorization": f"Bearer {config['apiKey']}"},
        timeout=config["timeout"],
    )
    content = (resp.get("choices") or [{}])[0].get("message", {}).get("content")
    if not content:
        raise RuntimeError("AI response did not contain message content.")
    return str(content)


def _dispatch_anthropic(messages: list[dict[str, str]], config: dict[str, Any]) -> str:
    """Dispatch to Anthropic API."""
    system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_messages = [m for m in messages if m["role"] != "system"]

    body: dict[str, Any] = {
        "model": config["model"],
        "max_tokens": config["maxTokens"],
        "messages": user_messages,
    }
    if system_msg:
        body["system"] = system_msg

    resp = post_json(
        f"{config['baseUrl']}/v1/messages",
        body,
        headers={"x-api-key": config["apiKey"], "anthropic-version": "2023-06-01"},
        timeout=config["timeout"],
    )
    content = (resp.get("content") or [{}])[0].get("text")
    if not content:
        raise RuntimeError("AI response did not contain content.")
    return str(content)


def _dispatch_gemini(messages: list[dict[str, str]], config: dict[str, Any]) -> str:
    """Dispatch to Google Gemini API."""
    system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
        for m in messages if m["role"] != "system"
    ]

    body: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {"maxOutputTokens": config["maxTokens"], "temperature": config["temperature"]},
    }
    if system_msg:
        body["systemInstruction"] = {"parts": [{"text": system_msg}]}

    resp = post_json(
        f"{config['baseUrl']}/v1beta/models/{config['model']}:generateContent?key={config['apiKey']}",
        body,
        timeout=config["timeout"],
    )

    content = "".join(
        p.get("text", "")
        for cand in (resp.get("candidates") or [])
        for p in (cand.get("content") or {}).get("parts", [])
    )
    if not content:
        raise RuntimeError("AI response did not contain content.")
    return str(content)


def parse_json_content(content: str) -> dict[str, Any]:
    """Parse JSON from AI response, handling markdown fences."""
    text = str(content or "").strip()
    if fenced := re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.I):
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        if (start := text.find("{")) >= 0 and (end := text.rfind("}")) > start:
            return json.loads(text[start:end + 1])
        raise



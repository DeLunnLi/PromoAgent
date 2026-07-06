"""AI content generation for PromoAgent - unified interface for multiple LLM providers."""
from __future__ import annotations

import itertools
import json
import os
import re
import sys
import threading
import urllib.error
import urllib.request
from typing import Any

from .logger import logger
from .promo_prompts import build_promo_system_prompt, build_promo_user_prompt, build_promo_payload

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
    env = env or os.environ
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

    return {
        "provider": provider,
        "apiKey": api_key,
        "baseUrl": base_url.rstrip("/"),
        "model": options.get("model") or env.get("PROMOAGENT_MODEL") or defaults["model"],
        "maxTokens": int(options.get("max_tokens") or env.get("PROMOAGENT_MAX_TOKENS") or 4096),
        "temperature": float(options.get("temperature") if options.get("temperature") is not None else env.get("PROMOAGENT_TEMPERATURE") or 0.7),
        "timeout": float(options.get("timeout") or env.get("PROMOAGENT_TIMEOUT_MS") or 120_000) / 1000,
    }


def has_ai_key(env: dict[str, str] | None = None) -> bool:
    env = env or os.environ
    keys = ["PROMOAGENT_API_KEY", "PROMOAGENT_MODELSCOPE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY", "OLLAMA_BASE_URL", "OLLAMA_HOST"]
    return any(env.get(k) for k in keys)


def build_promo_messages(result: dict[str, Any], *, platform: str = "all", brief_section: str = "", examples: list[str] | None = None) -> list[dict[str, str]]:
    payload = build_promo_payload(result)
    return [
        {"role": "system", "content": build_promo_system_prompt()},
        {"role": "user", "content": build_promo_user_prompt(payload, platform=platform, brief_section=brief_section, examples=examples)},
    ]


def generate_ai_content(
    result: dict[str, Any],
    *,
    platform: str = "all",
    brief_section: str = "",
    examples: list[str] | None = None,
    options: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
    validate: bool = True,
    auto_fix: bool = True,
    compare_with_examples: bool = True,
) -> dict[str, Any]:
    """Generate promotional content with streaming, validation, and auto-fix."""
    config = ai_config(options, env)
    provider = config.get("provider", "openai")

    if not config["apiKey"] and provider not in ("ollama",):
        raise RuntimeError(f"Missing API key for provider '{provider}'.")

    messages = build_promo_messages(result, platform=platform, brief_section=brief_section, examples=examples)

    # Call AI with streaming or spinner
    use_stream = os.environ.get("PROMOAGENT_STREAM", "").lower() == "true"
    if use_stream:
        raw_content = _stream_with_provider(messages, config)
    elif sys.stderr.isatty():
        raw_content = _with_spinner(dispatch_chat, messages, config, label=f"generating [{provider} / {config['model']}]")
    else:
        logger.info(f"generating content [{provider} / {config['model']}]")
        raw_content = dispatch_chat(messages, config)

    parsed = parse_json_content(raw_content)

    # Validate and fix
    if validate:
        if issues := validate_content(parsed, result):
            logger.warning(f"found {len(issues)} issue(s) in generated content")
            for issue in issues:
                logger.warning(f"content issue", platform=issue['platform'], message=issue['message'])
            if auto_fix and (fixed := _auto_fix(parsed, issues, messages, config)):
                parsed = fixed
                logger.info("content issues fixed automatically")

    # Compare with examples and improve
    if compare_with_examples and examples and parsed:
        if improved := _compare_and_improve(parsed, examples, messages, config):
            parsed = improved

    return {"content": parsed, "rawContent": raw_content, "messages": messages, "model": config["model"], "baseUrl": config["baseUrl"]}


def _stream_with_provider(messages: list[dict], config: dict[str, Any]) -> str:
    """Stream content based on provider."""
    provider = config.get("provider", "openai")

    if provider in ("openai", "modelscope"):
        return _sse_stream(
            f"{config['baseUrl']}/chat/completions",
            {"model": config["model"], "messages": messages, "temperature": config["temperature"], "max_tokens": config["maxTokens"], "stream": True},
            {"Authorization": f"Bearer {config['apiKey']}"},
            config["timeout"],
            lambda c: (c.get("choices") or [{}])[0].get("delta", {}).get("content") or "",
        )
    elif provider == "anthropic":
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_messages = [m for m in messages if m["role"] != "system"]
        body: dict[str, Any] = {"model": config["model"], "max_tokens": config["maxTokens"], "messages": user_messages, "stream": True}
        if system_msg:
            body["system"] = system_msg
        return _sse_stream(
            f"{config['baseUrl']}/v1/messages",
            body,
            {"x-api-key": config["apiKey"], "anthropic-version": "2023-06-01"},
            config["timeout"],
            lambda c: c.get("delta", {}).get("text") if c.get("type") == "content_block_delta" else "",
            "Anthropic",
        )
    elif provider == "gemini":
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]} for m in messages if m["role"] != "system"]
        body = {"contents": contents, "generationConfig": {"maxOutputTokens": config["maxTokens"], "temperature": config["temperature"]}}
        if system_msg:
            body["systemInstruction"] = {"parts": [{"text": system_msg}]}
        return _sse_stream(
            f"{config['baseUrl']}/v1beta/models/{config['model']}:streamGenerateContent?key={config['apiKey']}&alt=sse",
            body,
            {},
            config["timeout"],
            lambda c: "".join(p.get("text", "") for cand in (c.get("candidates") or []) for p in (cand.get("content") or {}).get("parts", [])),
            "Gemini",
        )
    else:
        return _with_spinner(dispatch_chat, messages, config, label=f"generating [{provider} / {config['model']}]")


def _sse_stream(url: str, body: dict[str, Any], headers: dict[str, str], timeout: float, delta_fn: Any, error_label: str = "AI") -> str:
    """Shared SSE streaming helper."""
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json", **headers})
    buffer = ""
    logger.info("generating content via streaming")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload in ("[DONE]", ""):
                    continue
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if delta := delta_fn(chunk):
                    buffer += delta
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{error_label} stream failed (HTTP {exc.code}): {detail}") from exc

    logger.info("streaming completed", total_chars=len(buffer))
    return buffer


def _with_spinner(fn: Any, *args: Any, label: str = "generating", **kwargs: Any) -> Any:
    """Run function with animated spinner."""
    result: list[Any] = [None]
    error: list[Exception] = []
    done_evt = threading.Event()

    def _target() -> None:
        try:
            result[0] = fn(*args, **kwargs)
        except Exception as exc:
            error.append(exc)
        finally:
            done_evt.set()

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()

    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    spinner = itertools.cycle(frames)
    while not done_evt.wait(timeout=0.12):
        sys.stderr.write(f"\rpromoagent: {next(spinner)} {label}…")
        sys.stderr.flush()

    sys.stderr.write(f"\rpromoagent: ✓ {label} done{' ' * 20}\n")
    sys.stderr.flush()
    thread.join()

    if error:
        raise error[0]
    return result[0]


# ---------------------------------------------------------------------------
# Provider-specific chat dispatchers
# ---------------------------------------------------------------------------

def dispatch_chat(messages: list[dict], config: dict[str, Any]) -> str:
    """Route to the correct provider implementation."""
    provider = config.get("provider", "openai")
    dispatchers = {
        "anthropic": _chat_anthropic,
        "gemini": _chat_gemini,
        "ollama": _chat_ollama,
    }
    return dispatchers.get(provider, _chat_openai)(messages, config)


def _chat_openai(messages: list[dict], config: dict[str, Any]) -> str:
    """Call OpenAI-compatible /chat/completions."""
    url = f"{config['baseUrl']}/chat/completions"
    headers = {"Authorization": f"Bearer {config['apiKey']}"}
    body = {"model": config["model"], "messages": messages, "temperature": config["temperature"], "max_tokens": config["maxTokens"]}

    try:
        resp = post_json(url, {**body, "response_format": {"type": "json_object"}}, headers=headers, timeout=config["timeout"])
    except RuntimeError as exc:
        if any(kw in str(exc).lower() for kw in ("response_format", "json_object", "unsupported")):
            resp = post_json(url, body, headers=headers, timeout=config["timeout"])
        else:
            raise
    return _extract_choice_text(resp)


def _chat_anthropic(messages: list[dict], config: dict[str, Any]) -> str:
    """Call Anthropic Messages API."""
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
    content_blocks = resp.get("content") or []
    text = "".join(block.get("text", "") for block in content_blocks if block.get("type") == "text")
    if not text:
        raise RuntimeError(f"Anthropic response contained no text: {resp}")
    return text


def _chat_gemini(messages: list[dict], config: dict[str, Any]) -> str:
    """Call Google Gemini generateContent API."""
    system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
    contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]} for m in messages if m["role"] != "system"]

    body: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {"maxOutputTokens": config["maxTokens"], "temperature": config["temperature"]},
    }
    if system_msg:
        body["systemInstruction"] = {"parts": [{"text": system_msg}]}

    resp = post_json(
        f"{config['baseUrl']}/v1beta/models/{config['model']}:generateContent?key={config['apiKey']}",
        body,
        headers={},
        timeout=config["timeout"],
    )
    candidates = resp.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {resp}")
    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts)
    if not text:
        raise RuntimeError(f"Gemini response had no text: {resp}")
    return text


def _chat_ollama(messages: list[dict], config: dict[str, Any]) -> str:
    """Call Ollama local API."""
    resp = post_json(
        f"{config['baseUrl']}/api/chat",
        {
            "model": config["model"],
            "messages": messages,
            "stream": False,
            "options": {"temperature": config["temperature"], "num_predict": config["maxTokens"]},
        },
        headers={},
        timeout=config["timeout"],
    )
    text = (resp.get("message") or {}).get("content") or ""
    if not text:
        raise RuntimeError(f"Ollama returned no content: {resp}")
    return text


# ---------------------------------------------------------------------------
# HTTP utilities
# ---------------------------------------------------------------------------

def post_json(url: str, body: dict[str, Any], *, headers: dict[str, str] | None = None, timeout: float = 120) -> dict[str, Any]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"AI request failed with HTTP {error.code}: {detail}") from error


def _extract_choice_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError("AI response did not contain choices.")
    content = (choices[0].get("message") or {}).get("content")
    if not content:
        raise RuntimeError("AI response did not contain message content.")
    return str(content)


# ---------------------------------------------------------------------------
# Validation and improvement
# ---------------------------------------------------------------------------

def validate_content(content: dict[str, Any], result: dict[str, Any]) -> list[dict[str, str]]:
    """Check structural completeness of generated content."""
    issues: list[dict[str, str]] = []
    promotions = content.get("promotions") or {}

    has_content = any(isinstance(post, dict) and post.get("markdown") for post in promotions.values())
    if not has_content:
        issues.append({"platform": "all", "message": "没有生成任何平台内容"})

    if not (content.get("promotionStrategy") or {}).get("qualityRubric"):
        issues.append({"platform": "all", "message": "qualityRubric 缺失，无法进行三轴审核"})

    return issues


def _auto_fix(original: dict[str, Any], issues: list[dict[str, str]], original_messages: list[dict[str, str]], config: dict[str, Any]) -> dict[str, Any] | None:
    """Send one follow-up message to fix quality issues."""
    issue_lines = "\n".join(f"- [{i['platform']}] {i['message']}" for i in issues)
    fix_request = f"以下是上面输出中发现的问题，请修正并输出完整的 JSON（与上次格式相同）：\n\n{issue_lines}\n\n直接输出 JSON，不要其他解释。"

    fix_messages = [*original_messages, {"role": "assistant", "content": json.dumps(original, ensure_ascii=False)}, {"role": "user", "content": fix_request}]
    try:
        return parse_json_content(dispatch_chat(fix_messages, config))
    except Exception as exc:
        logger.error("auto-fix failed", error=str(exc))
        return None


_COMPARE_PROMPT = """\
你刚刚生成了以下推广内容（JSON 格式）。我们还有一些同类优质内容的参考示例。

请对比生成内容和参考示例，找出 2-3 个结构或风格上的改进点（不是内容上的，是写法上的）：
- 开头方式是否够吸引人？
- 段落节奏和层次是否清晰？
- 平台原生感是否足够？

如果有明显差距，直接输出改进后的完整 JSON（与上次格式完全一致）。
如果整体质量已经很好，输出原始 JSON 不做修改。

参考示例：
{examples_text}

只输出 JSON，不要任何解释。
"""


def _compare_and_improve(content: dict[str, Any], examples: list[str], original_messages: list[dict[str, str]], config: dict[str, Any]) -> dict[str, Any] | None:
    """Compare generated content with examples and run one improvement pass."""
    examples_text = "\n\n---\n\n".join(ex[:600] for ex in examples[:2])
    compare_messages = [
        *original_messages,
        {"role": "assistant", "content": json.dumps(content, ensure_ascii=False)},
        {"role": "user", "content": _COMPARE_PROMPT.format(examples_text=examples_text)},
    ]
    logger.info("comparing with examples and refining")
    try:
        improved = parse_json_content(dispatch_chat(compare_messages, config))
        return improved if isinstance(improved, dict) and improved.get("promotions") else None
    except Exception as exc:
        logger.warning("Stage 3 comparison skipped", error=str(exc))
        return None


# ---------------------------------------------------------------------------
# Refinement
# ---------------------------------------------------------------------------

def refine_content(previous_result: dict[str, Any], feedback: str, *, platform: str | None = None, options: dict[str, Any] | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Refine previously generated content based on user feedback."""
    config = ai_config(options, env)
    if not config["apiKey"]:
        raise RuntimeError("Missing AI API key.")

    messages = previous_result.get("messages") or []
    prev_content = previous_result.get("content") or {}

    if not messages:
        raise ValueError("No conversation context found. Run promote/optimize first.")

    platform_hint = f"重点修改 {platform} 平台的内容。" if platform else "可以修改任何平台的内容。"
    refine_messages = [
        *messages,
        {"role": "assistant", "content": json.dumps(prev_content, ensure_ascii=False)},
        {"role": "user", "content": f"{feedback}\n\n{platform_hint}保持 JSON 结构不变，输出完整修改后的 JSON。"},
    ]

    logger.info("refining content")
    refined = parse_json_content(dispatch_chat(refine_messages, config))
    return {"content": refined, "rawContent": json.dumps(refined), "messages": refine_messages, "model": config["model"], "baseUrl": config["baseUrl"]}


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

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

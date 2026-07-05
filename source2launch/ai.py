from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any

from .promo_prompts import build_promo_system_prompt, build_promo_user_prompt

# ---------------------------------------------------------------------------
# Provider defaults
# ---------------------------------------------------------------------------

_PROVIDER_DEFAULTS = {
    "openai":     {"base_url": "https://api.openai.com/v1",                          "model": "gpt-4o-mini"},
    "anthropic":  {"base_url": "https://api.anthropic.com",                          "model": "claude-haiku-4-5"},
    "gemini":     {"base_url": "https://generativelanguage.googleapis.com",           "model": "gemini-2.0-flash"},
    "ollama":     {"base_url": "http://localhost:11434",                              "model": "llama3.2"},
    "modelscope": {"base_url": "https://api-inference.modelscope.cn/v1",             "model": "Qwen/Qwen3.5-397B-A17B"},
}

# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------

def _detect_provider(options: dict[str, Any], env: dict[str, str]) -> str:
    """Detect the LLM provider from options and environment variables."""
    # Explicit override wins
    explicit = options.get("provider") or env.get("SOURCE2LAUNCH_PROVIDER", "")
    if explicit:
        return explicit.lower().strip()

    # Key-based detection
    if options.get("api_key", "").startswith("sk-ant-") or env.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if env.get("GOOGLE_API_KEY") or env.get("GEMINI_API_KEY"):
        return "gemini"
    if env.get("OLLAMA_BASE_URL") or env.get("OLLAMA_HOST"):
        return "ollama"
    if env.get("SOURCE2LAUNCH_MODELSCOPE_API_KEY") or env.get("MODELSCOPE_API_KEY"):
        return "modelscope"

    # Model-name hints
    model = options.get("model") or env.get("SOURCE2LAUNCH_MODEL") or ""
    if re.match(r"^claude", model, re.I):
        return "anthropic"
    if re.match(r"^gemini", model, re.I):
        return "gemini"
    if re.match(r"^(llama|mistral|qwen|phi|deepseek).*:?", model, re.I) and not env.get("SOURCE2LAUNCH_API_KEY"):
        return "ollama"

    # Base URL hints
    base_url = options.get("base_url") or env.get("SOURCE2LAUNCH_BASE_URL") or ""
    if "anthropic" in base_url:
        return "anthropic"
    if "googleapis" in base_url or "generativelanguage" in base_url:
        return "gemini"
    if "localhost:11434" in base_url or "ollama" in base_url:
        return "ollama"
    if "modelscope" in base_url:
        return "modelscope"

    return "openai"  # default


# ---------------------------------------------------------------------------
# Unified config builder
# ---------------------------------------------------------------------------

def ai_config(options: dict[str, Any] | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Build a unified AI configuration dict, auto-detecting the provider."""
    options = options or {}
    env = env or os.environ

    provider = _detect_provider(options, env)
    defaults = _PROVIDER_DEFAULTS.get(provider, _PROVIDER_DEFAULTS["openai"])

    # API key — each provider uses different env var names
    if provider == "anthropic":
        api_key = options.get("api_key") or env.get("ANTHROPIC_API_KEY") or env.get("SOURCE2LAUNCH_API_KEY")
    elif provider == "gemini":
        api_key = options.get("api_key") or env.get("GOOGLE_API_KEY") or env.get("GEMINI_API_KEY") or env.get("SOURCE2LAUNCH_API_KEY")
    elif provider == "ollama":
        api_key = options.get("api_key") or env.get("OLLAMA_API_KEY") or ""  # Ollama usually needs no key
    elif provider == "modelscope":
        api_key = options.get("api_key") or env.get("SOURCE2LAUNCH_MODELSCOPE_API_KEY") or env.get("MODELSCOPE_API_KEY") or env.get("SOURCE2LAUNCH_API_KEY")
    else:  # openai and compatible
        api_key = options.get("api_key") or env.get("SOURCE2LAUNCH_API_KEY") or env.get("OPENAI_API_KEY") or env.get("MODELSCOPE_API_KEY")

    base_url = (
        options.get("base_url")
        or env.get("SOURCE2LAUNCH_BASE_URL")
        or (env.get("OLLAMA_BASE_URL") or env.get("OLLAMA_HOST") if provider == "ollama" else None)
        or defaults["base_url"]
    ).rstrip("/")

    model = (
        options.get("model")
        or env.get("SOURCE2LAUNCH_MODEL")
        or defaults["model"]
    )

    return {
        "provider": provider,
        "apiKey": api_key,
        "baseUrl": base_url,
        "model": model,
        "maxTokens": int(options.get("max_tokens") or env.get("SOURCE2LAUNCH_MAX_TOKENS") or 4096),
        "temperature": float(options.get("temperature") if options.get("temperature") is not None else env.get("SOURCE2LAUNCH_TEMPERATURE") or 0.7),
        "timeout": float(options.get("timeout") or env.get("SOURCE2LAUNCH_TIMEOUT_MS") or 120_000) / 1000,
    }


def has_ai_key(env: dict[str, str] | None = None) -> bool:
    env = env or os.environ
    return bool(
        env.get("SOURCE2LAUNCH_API_KEY")
        or env.get("SOURCE2LAUNCH_MODELSCOPE_API_KEY")
        or env.get("OPENAI_API_KEY")
        or env.get("MODELSCOPE_API_KEY")
        or env.get("ANTHROPIC_API_KEY")
        or env.get("GOOGLE_API_KEY")
        or env.get("GEMINI_API_KEY")
        or env.get("OLLAMA_BASE_URL")
        or env.get("OLLAMA_HOST")
    )


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
    stream: bool | None = None,
    validate: bool = True,
    auto_fix: bool = True,
    compare_with_examples: bool = True,  # auto-compare with Stage 1 examples
) -> dict[str, Any]:
    """Stage 2: generate promotional content with streaming, validation, auto-fix, and example comparison."""
    config = ai_config(options, env)
    provider = config.get("provider", "openai")
    if not config["apiKey"] and provider not in ("ollama",):
        raise RuntimeError(
            f"Missing API key for provider '{provider}'. "
            "Set one of: SOURCE2LAUNCH_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY / "
            "GOOGLE_API_KEY / GEMINI_API_KEY, or use OLLAMA_BASE_URL for local models."
        )

    # Streaming: env var or explicit param
    env = env or os.environ
    use_stream = stream if stream is not None else env.get("SOURCE2LAUNCH_STREAM", "").lower() == "true"

    messages = build_promo_messages(result, platform=platform, brief_section=brief_section, examples=examples)
    provider = config.get("provider", "openai")
    print(f"source2launch: generating content [{provider} / {config['model']}]…", file=sys.stderr)

    # --- Call AI (streaming only for OpenAI-compatible) ---
    if use_stream and provider in ("openai", "modelscope"):
        url = f"{config['baseUrl']}/chat/completions"
        headers = {"Authorization": f"Bearer {config['apiKey']}"}
        base_body: dict[str, Any] = {
            "model": config["model"],
            "messages": messages,
            "temperature": config["temperature"],
            "max_tokens": config["maxTokens"],
        }
        raw_content = _stream_and_collect(url, base_body, headers=headers, timeout=config["timeout"])
    else:
        raw_content = dispatch_chat(messages, config)

    parsed = parse_json_content(raw_content)

    # --- Validate output ---
    if validate:
        issues = validate_content(parsed, result)
        if issues:
            print(f"source2launch: found {len(issues)} issue(s) in generated content:", file=sys.stderr)
            for issue in issues:
                print(f"  ⚠ [{issue['platform']}] {issue['message']}", file=sys.stderr)
            if auto_fix:
                fixed = _auto_fix(parsed, issues, messages, config)
                if fixed:
                    parsed = fixed
                    print("source2launch: ✓ issues fixed automatically", file=sys.stderr)

    # --- Stage 3: compare with examples and auto-improve ---
    if compare_with_examples and examples and parsed:
        improved = _compare_and_improve(parsed, examples, messages, config)
        if improved:
            parsed = improved

    return {
        "content": parsed,
        "rawContent": raw_content,
        "messages": messages,       # saved for multi-turn refinement
        "model": config["model"],
        "baseUrl": config["baseUrl"],
    }


# ---------------------------------------------------------------------------
# Stage 3: compare generated content with reference examples and improve
# ---------------------------------------------------------------------------

_COMPARE_PROMPT = """\
你刚刚生成了以下推广内容（JSON 格式）。
我们还有一些同类优质内容的参考示例。

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


def _compare_and_improve(
    content: dict[str, Any],
    examples: list[str],
    original_messages: list[dict[str, str]],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    """Compare generated content with examples and run one improvement pass."""
    examples_text = "\n\n---\n\n".join(ex[:600] for ex in examples[:2])
    compare_messages = [
        *original_messages,
        {"role": "assistant", "content": json.dumps(content, ensure_ascii=False)},
        {"role": "user", "content": _COMPARE_PROMPT.format(examples_text=examples_text)},
    ]
    print("source2launch: comparing with examples and refining…", file=sys.stderr)
    try:
        raw = dispatch_chat(compare_messages, config)
        improved = parse_json_content(raw)
        if isinstance(improved, dict) and improved.get("promotions"):
            return improved
    except Exception:  # noqa: BLE001
        pass
    return None


# ---------------------------------------------------------------------------
# Multi-turn refinement
# ---------------------------------------------------------------------------

def refine_content(
    previous_result: dict[str, Any],
    feedback: str,
    *,
    platform: str | None = None,
    options: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Refine previously generated content based on user feedback.

    previous_result must contain 'messages' (the conversation so far)
    and 'content' (the previous AI output).
    """
    config = ai_config(options, env)
    if not config["apiKey"]:
        raise RuntimeError("Missing AI API key.")

    messages = previous_result.get("messages") or []
    prev_content = previous_result.get("content") or {}

    if not messages:
        raise ValueError(
            "No conversation context found. "
            "Run promote/optimize first to generate content before refining."
        )

    platform_hint = f"重点修改 {platform} 平台的内容。" if platform else "可以修改任何平台的内容。"
    refine_message = (
        f"{feedback}\n\n"
        f"{platform_hint}"
        "保持 JSON 结构不变，输出完整修改后的 JSON。"
    )

    refine_messages = [
        *messages,
        {"role": "assistant", "content": json.dumps(prev_content, ensure_ascii=False)},
        {"role": "user", "content": refine_message},
    ]

    print("source2launch: refining content…", file=sys.stderr)
    raw = dispatch_chat(refine_messages, config)
    refined = parse_json_content(raw)
    return {
        "content": refined,
        "rawContent": raw,
        "messages": refine_messages,
        "model": config["model"],
        "baseUrl": config["baseUrl"],
    }


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------

def _stream_and_collect(url: str, base_body: dict[str, Any], *, headers: dict[str, str], timeout: float) -> str:
    """Call the streaming API and print tokens as they arrive. Returns full content."""
    body = {**base_body, "stream": True}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                  headers={"Content-Type": "application/json", **headers})
    buffer = ""
    print("source2launch: generating", end=" ", file=sys.stderr, flush=True)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                delta = (chunk.get("choices") or [{}])[0].get("delta", {}).get("content") or ""
                if delta:
                    buffer += delta
                    # Print a dot every ~200 chars as progress indicator
                    if len(buffer) % 200 < len(delta):
                        print(".", end="", file=sys.stderr, flush=True)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"AI stream request failed with HTTP {exc.code}: {detail}") from exc
    print(" done", file=sys.stderr)
    return buffer


# ---------------------------------------------------------------------------
# Validation — structural only, no hardcoded rules
# ---------------------------------------------------------------------------

def validate_content(content: dict[str, Any], result: dict[str, Any]) -> list[dict[str, str]]:
    """Check structural completeness of the generated content.

    Validates structure only (are required fields present?).
    Quality judgment is delegated to the AI's own qualityRubric.
    """
    issues: list[dict[str, str]] = []
    promotions = content.get("promotions") or {}

    # At least one platform must have a non-empty markdown
    has_any_content = any(
        isinstance(post, dict) and post.get("markdown")
        for post in promotions.values()
    )
    if not has_any_content:
        issues.append({"platform": "all", "message": "没有生成任何平台内容"})

    # qualityRubric should exist
    rubric = (content.get("promotionStrategy") or {}).get("qualityRubric") or {}
    if not rubric:
        issues.append({"platform": "all", "message": "qualityRubric 缺失，无法进行三轴审核"})

    return issues


# ---------------------------------------------------------------------------
# Auto-fix
# ---------------------------------------------------------------------------

def _auto_fix(
    original: dict[str, Any],
    issues: list[dict[str, str]],
    original_messages: list[dict[str, str]],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    """Send one follow-up message to fix specific quality issues."""
    issue_lines = "\n".join(f"- [{i['platform']}] {i['message']}" for i in issues)
    fix_request = (
        "以下是上面输出中发现的问题，请修正并输出完整的 JSON（与上次格式相同）：\n\n"
        f"{issue_lines}\n\n"
        "直接输出 JSON，不要其他解释。"
    )
    fix_messages = [
        *original_messages,
        {"role": "assistant", "content": json.dumps(original, ensure_ascii=False)},
        {"role": "user", "content": fix_request},
    ]
    try:
        raw = dispatch_chat(fix_messages, config)
        return parse_json_content(raw)
    except Exception:  # noqa: BLE001
        return None


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


# ---------------------------------------------------------------------------
# Provider-specific chat callers
# ---------------------------------------------------------------------------

def _chat_openai(messages: list[dict], config: dict[str, Any]) -> str:
    """Call OpenAI-compatible /chat/completions (OpenAI, ModelScope, Ollama-OpenAI, etc.)."""
    url = f"{config['baseUrl']}/chat/completions"
    headers = {"Authorization": f"Bearer {config['apiKey']}"}
    body: dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "temperature": config["temperature"],
        "max_tokens": config["maxTokens"],
    }
    try:
        resp = post_json(url, {**body, "response_format": {"type": "json_object"}}, headers=headers, timeout=config["timeout"])
    except RuntimeError as exc:
        err = str(exc).lower()
        if any(kw in err for kw in ("response_format", "json_object", "unsupported", "invalid")):
            resp = post_json(url, body, headers=headers, timeout=config["timeout"])
        else:
            raise
    return extract_chat_content(resp)


def _chat_anthropic(messages: list[dict], config: dict[str, Any]) -> str:
    """Call Anthropic Messages API (claude-* models)."""
    # Anthropic separates system message from the messages array
    system_content = ""
    user_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_content = msg["content"]
        else:
            user_messages.append({"role": msg["role"], "content": msg["content"]})

    url = f"{config['baseUrl']}/v1/messages"
    headers = {
        "x-api-key": config["apiKey"],
        "anthropic-version": "2023-06-01",
    }
    body: dict[str, Any] = {
        "model": config["model"],
        "max_tokens": config["maxTokens"],
        "messages": user_messages,
    }
    if system_content:
        body["system"] = system_content

    resp = post_json(url, body, headers=headers, timeout=config["timeout"])
    content_blocks = resp.get("content") or []
    text = "".join(block.get("text", "") for block in content_blocks if block.get("type") == "text")
    if not text:
        raise RuntimeError(f"Anthropic response contained no text content: {resp}")
    return text


def _chat_gemini(messages: list[dict], config: dict[str, Any]) -> str:
    """Call Google Gemini generateContent API."""
    # Gemini uses 'contents' with 'parts', and a separate 'systemInstruction'
    system_content = ""
    contents = []
    for msg in messages:
        if msg["role"] == "system":
            system_content = msg["content"]
            continue
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    model = config["model"]
    api_key = config["apiKey"]
    url = f"{config['baseUrl']}/v1beta/models/{model}:generateContent?key={api_key}"

    body: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": config["maxTokens"],
            "temperature": config["temperature"],
        },
    }
    if system_content:
        body["systemInstruction"] = {"parts": [{"text": system_content}]}

    resp = post_json(url, body, headers={}, timeout=config["timeout"])
    candidates = resp.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {resp}")
    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts)
    if not text:
        raise RuntimeError(f"Gemini response had no text: {resp}")
    return text


def _chat_ollama(messages: list[dict], config: dict[str, Any]) -> str:
    """Call Ollama local API (/api/chat)."""
    url = f"{config['baseUrl']}/api/chat"
    body: dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": config["temperature"],
            "num_predict": config["maxTokens"],
        },
    }
    # Ollama needs no auth header
    resp = post_json(url, body, headers={}, timeout=config["timeout"])
    text = (resp.get("message") or {}).get("content") or ""
    if not text:
        raise RuntimeError(f"Ollama returned no content: {resp}")
    return text


def dispatch_chat(messages: list[dict], config: dict[str, Any]) -> str:
    """Route to the correct provider based on config['provider']."""
    provider = config.get("provider", "openai")
    if provider == "anthropic":
        return _chat_anthropic(messages, config)
    if provider == "gemini":
        return _chat_gemini(messages, config)
    if provider == "ollama":
        return _chat_ollama(messages, config)
    # openai / modelscope / any other OpenAI-compatible
    return _chat_openai(messages, config)


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

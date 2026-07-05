from __future__ import annotations

import json
import os
import re
import sys
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
    stream: bool | None = None,      # None = auto-detect from env
    validate: bool = True,           # run post-generation validation
    auto_fix: bool = True,           # attempt one auto-fix call if issues found
) -> dict[str, Any]:
    """Stage 2: generate promotional content with optional streaming, validation, and auto-fix."""
    config = ai_config(options, env)
    if not config["apiKey"]:
        raise RuntimeError("Missing AI API key. Set SOURCE2LAUNCH_API_KEY or SOURCE2LAUNCH_MODELSCOPE_API_KEY.")

    # Streaming: env var or explicit param
    env = env or os.environ
    use_stream = stream if stream is not None else env.get("SOURCE2LAUNCH_STREAM", "").lower() == "true"

    messages = build_promo_messages(result, platform=platform, brief_section=brief_section, examples=examples)
    url = f"{config['baseUrl']}/chat/completions"
    headers = {"Authorization": f"Bearer {config['apiKey']}"}
    base_body: dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "temperature": config["temperature"],
        "max_tokens": config["maxTokens"],
    }

    # --- Call AI (with streaming or not) ---
    if use_stream:
        raw_content = _stream_and_collect(url, base_body, headers=headers, timeout=config["timeout"])
    else:
        print("source2launch: generating content…", file=sys.stderr)
        try:
            response = post_json(url, {**base_body, "response_format": {"type": "json_object"}}, headers=headers, timeout=config["timeout"])
        except RuntimeError as exc:
            err = str(exc).lower()
            if "response_format" in err or "json_object" in err or "unsupported" in err or "invalid" in err:
                response = post_json(url, base_body, headers=headers, timeout=config["timeout"])
            else:
                raise
        raw_content = extract_chat_content(response)

    parsed = parse_json_content(raw_content)

    # --- Validate output ---
    if validate:
        issues = validate_content(parsed, result)
        if issues:
            print(f"source2launch: found {len(issues)} issue(s) in generated content:", file=sys.stderr)
            for issue in issues:
                print(f"  ⚠ [{issue['platform']}] {issue['message']}", file=sys.stderr)

            # Auto-fix: one follow-up call to address the issues
            if auto_fix:
                fixed = _auto_fix(parsed, issues, messages, base_body, url, headers, config)
                if fixed:
                    parsed = fixed
                    print("source2launch: ✓ issues fixed automatically", file=sys.stderr)

    return {
        "content": parsed,
        "rawContent": raw_content,
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
# Validation
# ---------------------------------------------------------------------------

_BANNED_WORDS = ["必备", "神器", "高质量", "颠覆", "最强", "完美", "爆款", "轻松搞定", "一键", "秒变"]


def validate_content(content: dict[str, Any], result: dict[str, Any]) -> list[dict[str, str]]:
    """Check common quality issues in the generated content.

    Returns a list of issue dicts: {"platform": ..., "message": ...}
    """
    issues: list[dict[str, str]] = []
    promotions = content.get("promotions") or {}
    project = result.get("project", {})
    evidence = result.get("evidence", {})

    cta = (
        project.get("cta")
        or project.get("installCommand")
        or project.get("homepage")
        or project.get("repositoryUrl")
    )

    for platform, post in promotions.items():
        if not isinstance(post, dict):
            continue
        md = post.get("markdown") or ""
        if not md:
            continue

        # Check banned words
        found_banned = [w for w in _BANNED_WORDS if w in md]
        if found_banned:
            issues.append({"platform": platform, "message": f"含禁用词：{', '.join(found_banned)}"})

        # Check CTA is referenced (only if we have one)
        if cta and len(cta) > 5 and cta not in md:
            issues.append({"platform": platform, "message": f"CTA 未被引用（应包含：{cta[:40]}）"})

    # XHS title length
    xhs = promotions.get("xiaohongshu") or {}
    for title in xhs.get("titles") or []:
        if len(str(title)) > 20:
            issues.append({"platform": "xhs", "message": f"标题超过20字（{len(title)}字）：{title}"})

    # qualityRubric must be filled
    rubric = (content.get("promotionStrategy") or {}).get("qualityRubric") or {}
    for axis in ["fidelity", "engagement", "alignment"]:
        if not (rubric.get(axis) or {}).get("checks"):
            issues.append({"platform": "all", "message": f"qualityRubric.{axis}.checks 为空"})

    return issues


# ---------------------------------------------------------------------------
# Auto-fix
# ---------------------------------------------------------------------------

def _auto_fix(
    original: dict[str, Any],
    issues: list[dict[str, str]],
    original_messages: list[dict[str, str]],
    base_body: dict[str, Any],
    url: str,
    headers: dict[str, str],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    """Send one follow-up message to fix specific quality issues."""
    issue_lines = "\n".join(f"- [{i['platform']}] {i['message']}" for i in issues)
    fix_request = (
        "以下是上面输出中发现的问题，请修正并输出完整的 JSON（与上次格式相同）：\n\n"
        f"{issue_lines}\n\n"
        "修正要求：\n"
        "- 删除所有禁用词（必备/神器/颠覆等），用具体描述代替\n"
        "- 确保 CTA 在主要平台文案中被引用\n"
        "- 小红书标题控制在20字以内\n"
        "- 填写 qualityRubric 三轴审核\n"
        "直接输出 JSON，不要其他解释。"
    )

    fix_messages = [
        *original_messages,
        {"role": "assistant", "content": json.dumps(original, ensure_ascii=False)},
        {"role": "user", "content": fix_request},
    ]

    fix_body = {**base_body, "messages": fix_messages}
    try:
        response = post_json(url, fix_body, headers=headers, timeout=config["timeout"])
        raw = extract_chat_content(response)
        return parse_json_content(raw)
    except Exception:  # noqa: BLE001
        return None  # Fix failed, keep original


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

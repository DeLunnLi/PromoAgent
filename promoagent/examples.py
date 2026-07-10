"""Two-stage promotional content generation: find reference examples first.

Stage 1 (this module): find 1-2 high-quality reference examples for the
                        detected content category and target platform.
Stage 2 (ai.py):       use those examples as few-shot context when generating
                        the actual promotional content.

Three example sources, tried in order:
  1. Tavily web search  — keyword search, real examples (requires TAVILY_API_KEY)
  2. Exa neural search  — semantic search, better for English/PH/Show HN content
                          (requires EXA_API_KEY)
  3. AI self-generation — the AI generates reference examples from its training
                          knowledge (zero external dependencies)
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
EXA_SEARCH_URL    = "https://api.exa.ai/search"
FETCH_TIMEOUT = 15

# ---------------------------------------------------------------------------
# Category detection
# ---------------------------------------------------------------------------

def detect_category(result: dict[str, Any], ai_options: dict[str, Any] | None = None, env: dict[str, str] | None = None) -> str:
    """Detect the promotional content category using AI understanding.

    Falls back to a lightweight source-type heuristic when no AI key is available.
    """
    project = result.get("project", {})
    evidence = result.get("evidence", {})

    # Build a concise description for classification
    description = " ".join(filter(None, [
        project.get("name", ""),
        project.get("description", ""),
        evidence.get("opening", "") or evidence.get("readmeOpening", ""),
        " ".join(project.get("topics", [])),
    ])).strip()[:300]

    if not description:
        description = str(result.get("target", ""))[:200]

    # Fast heuristic: if no AI key, use source type
    env = env or os.environ
    has_key = bool(
        env.get("PROMOAGENT_API_KEY") or env.get("PROMOAGENT_MODELSCOPE_API_KEY")
        or env.get("OPENAI_API_KEY") or env.get("MODELSCOPE_API_KEY")
    )
    if not has_key:
        source = result.get("source", "")
        if source in ("github", "local"):
            return "科技/开源项目"
        if source in ("file",) and result.get("inputType") in ("pdf", "document"):
            return "学术研究/文档"
        return "通用产品/服务"

    # AI-based classification
    from .ai import ai_config, post_json
    config = ai_config(ai_options, env)
    prompt = (
        f"请用2-5个字说明以下内容属于什么推广类型（例如：餐饮美食、科技工具、学术论文、教育课程、电商产品…）。\n"
        f"只回答类型名称，不要其他内容。\n\n内容描述：{description}"
    )
    try:
        resp = post_json(
            f"{config['baseUrl']}/chat/completions",
            {
                "model": config["model"],
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 20,
                "temperature": 0,
            },
            headers={"Authorization": f"Bearer {config['apiKey']}"},
            timeout=10,
        )
        # Extract text from response
        choices = resp.get("choices") or []
        if choices and choices[0].get("message"):
            return str(choices[0]["message"].get("content", "")).strip()[:30]
        return "通用产品/服务"
    except (RuntimeError, urllib.error.URLError, json.JSONDecodeError, KeyError, ValueError):
        # AI failed → fall back to source-type heuristic
        source = result.get("source", "")
        if source in ("github", "local"):
            return "科技/开源项目"
        if source == "file" and result.get("inputType") in ("pdf", "document"):
            return "学术研究/文档"
        return "通用产品/服务"


# ---------------------------------------------------------------------------
# Platform-specific search queries
# ---------------------------------------------------------------------------

def _build_search_query(category: str, platform: str) -> str:
    """Build a search query for finding promotional examples."""
    label = _platform_label(platform)
    if platform in ("all", "", "通用"):
        return f"{category} 推广文案 优质示例"
    return f"{label} {category} 推广 优质案例 示例"


# ---------------------------------------------------------------------------
# Source 1: Tavily web search
# ---------------------------------------------------------------------------

def _search_tavily(query: str, api_key: str, max_results: int = 3) -> list[str]:
    """Call Tavily API and return a list of content snippets."""
    body = json.dumps({
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": False,
        "include_raw_content": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        TAVILY_SEARCH_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            data = json.loads(resp.read())
    except (urllib.error.HTTPError, urllib.error.URLError, Exception) as exc:  # noqa: BLE001
        print(f"promoagent: Tavily search failed: {exc}", file=sys.stderr)
        return []

    snippets = []
    for item in (data.get("results") or []):
        snippet = item.get("content") or item.get("snippet") or ""
        title = item.get("title") or ""
        if snippet:
            snippets.append(f"【{title}】\n{snippet[:500]}")
    return snippets[:2]


# ---------------------------------------------------------------------------
# Source 2: Exa neural / semantic search
# ---------------------------------------------------------------------------

def _search_exa(query: str, api_key: str, max_results: int = 3) -> list[str]:
    """Call Exa neural search API and return a list of content snippets.

    Exa uses semantic / neural search rather than keyword matching, which
    surfaces posts that are conceptually similar even when wording differs.
    Particularly effective for English-language platforms (Show HN, Product
    Hunt, LinkedIn, Reddit) and for academic content.
    """
    body = json.dumps({
        "query": query,
        "numResults": max_results,
        "type": "neural",
        "useAutoprompt": True,
        "contents": {
            "text": {"maxCharacters": 500},
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        EXA_SEARCH_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            data = json.loads(resp.read())
    except (urllib.error.HTTPError, urllib.error.URLError, Exception) as exc:  # noqa: BLE001
        print(f"promoagent: Exa search failed: {exc}", file=sys.stderr)
        return []

    snippets = []
    for item in (data.get("results") or []):
        text = (item.get("text") or "").strip()
        title = (item.get("title") or "").strip()
        if text:
            snippets.append(f"【{title}】\n{text[:500]}" if title else text[:500])
    return snippets[:2]


# ---------------------------------------------------------------------------
# Source 3: AI self-generation (zero external dependencies)
# ---------------------------------------------------------------------------

_EXAMPLE_GENERATION_PROMPT = """\
你是推广内容专家，熟悉各平台的优质内容风格。

请为以下场景生成 2 个高质量的参考示例：
- 内容类型：{category}
- 目标平台：{platform_label}
- 用途：作为写作风格参考（不是最终内容）

要求：
1. 每个示例真实可发布，具有平台原生感，不像模板
2. 第一句话具体有画面感或数据感，不要以「介绍」「推荐」开头
3. 符合平台字数和格式要求
4. 两个示例视角不同（例如：一个侧重体验，一个侧重数据或功能）

只输出两个示例，用 === 分隔，不要其他解释。
"""

def _platform_label(platform: str) -> str:
    """Derive a human-readable label from the platform key."""
    return platform if platform else "通用"


def _generate_examples_via_ai(
    category: str,
    platform: str,
    ai_options: dict[str, Any],
    env: dict[str, str] | None = None,
) -> list[str]:
    """Ask the AI to generate reference examples (self-play / self-instruct)."""
    from .ai import ai_config, post_json  # local import to avoid circular

    env = env or os.environ
    config = ai_config(ai_options, env)
    if not config.get("apiKey"):
        return []

    platform_label = _platform_label(platform)
    prompt = _EXAMPLE_GENERATION_PROMPT.format(
        category=category,
        platform_label=platform_label,
    )

    body: dict[str, Any] = {
        "model": config["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9,          # higher temperature = more diverse examples
        "max_tokens": 1200,
    }
    headers = {"Authorization": f"Bearer {config['apiKey']}"}

    try:
        response = post_json(
            f"{config['baseUrl']}/chat/completions",
            body,
            headers=headers,
            timeout=config["timeout"],
        )
    except (RuntimeError, urllib.error.URLError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"promoagent: example generation failed: {exc}", file=sys.stderr)
        return []

    choices = response.get("choices") or []
    if not choices:
        return []
    content = (choices[0].get("message") or {}).get("content") or ""

    # Split by separator
    parts = re.split(r"\n===+\n?|\n---+\n?", content.strip())
    examples = [p.strip() for p in parts if len(p.strip()) > 30]
    return examples[:2]


# ---------------------------------------------------------------------------
# Parallel search helper
# ---------------------------------------------------------------------------

def _search_parallel(query: str, env: dict[str, str]) -> list[str]:
    """Search Tavily and Exa in parallel, return first successful result.

    Uses ThreadPoolExecutor to run both searches concurrently.
    Returns empty list if neither source has API keys configured.
    """
    tavily_key = env.get("TAVILY_API_KEY", "")
    exa_key = env.get("EXA_API_KEY", "")

    if not tavily_key and not exa_key:
        return []

    # If only one key is available, skip the thread pool overhead
    if tavily_key and not exa_key:
        return _search_tavily(query, tavily_key)
    if exa_key and not tavily_key:
        return _search_exa(query, exa_key)

    # Both keys available — run in parallel
    futures: dict = {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures[executor.submit(_search_tavily, query, tavily_key)] = "tavily"
        futures[executor.submit(_search_exa, query, exa_key)] = "exa"

        for future in as_completed(futures):
            source = futures[future]
            try:
                result = future.result()
                if result:
                    # Cancel remaining futures if we got a result
                    for f in futures:
                        if f is not future:
                            f.cancel()
                    return result
            except Exception:
                continue

    return []


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def find_examples(
    result: dict[str, Any],
    *,
    platform: str = "all",
    ai_options: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
    verbose: bool = True,
) -> list[str]:
    """Find 1-2 reference examples for the given result and platform.

    Tries Tavily and Exa searches in parallel (if API keys are set),
    then falls back to AI self-generation.

    Returns a list of example strings (may be empty if all sources fail).
    """
    env = env or os.environ
    ai_options = ai_options or {}
    category = detect_category(result, ai_options=ai_options, env=env)

    if verbose:
        print(f"promoagent: finding reference examples [{category} / {platform}]…", file=sys.stderr)

    query = _build_search_query(category, platform)

    # Source 1 & 2: Tavily + Exa (parallel)
    examples = _search_parallel(query, env)
    if examples:
        if verbose:
            print(f"promoagent: found {len(examples)} example(s) via search", file=sys.stderr)
        return examples

    # Source 3: AI self-generation (zero external dependencies)
    examples = _generate_examples_via_ai(category, platform, ai_options, env)
    if examples:
        if verbose:
            print(f"promoagent: generated {len(examples)} reference example(s) via AI", file=sys.stderr)
    else:
        if verbose:
            print("promoagent: no examples found, continuing without few-shot context", file=sys.stderr)

    return examples


# ---------------------------------------------------------------------------
# Format examples for prompt injection
# ---------------------------------------------------------------------------

def format_examples_for_prompt(examples: list[str]) -> str:
    """Format reference examples into a prompt fragment.

    Returns an empty string for an empty list so callers can unconditionally
    interpolate the result without producing stray headings.
    """
    if not examples:
        return ""
    blocks = [f"--- 参考示例 {i + 1} ---\n{ex}" for i, ex in enumerate(examples)]
    return "参考广告/示例（仅作风格参考，不要复制内容）：\n" + "\n\n".join(blocks)

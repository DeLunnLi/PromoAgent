"""Improved 3-stage promotional content generation pipeline.

Stages:
1. RESEARCH: Extract facts, positioning, and strategy
2. BLUEPRINT: Structured editable content elements (Tweet Space)
3. PRODUCE: Platform-native content generation

Features:
- Stage caching with automatic recovery
- Parallel platform generation
- Dynamic element types in Blueprint
- Visual editing support
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ai import ai_config, dispatch_chat, parse_json_content
from .examples import find_examples, format_examples_for_prompt
from .logger import logger
from .platforms import get_platform, to_prompt_dict, format_playbook_for_prompt

# ---------------------------------------------------------------------------
# Quality modes — control how much enrichment each produce call gets.
# ---------------------------------------------------------------------------

QUALITY_FAST = "fast"
QUALITY_BALANCED = "balanced"
QUALITY_POLISHED = "polished"
QUALITY_MODES = (QUALITY_FAST, QUALITY_BALANCED, QUALITY_POLISHED)


def _resolve_quality_mode(options: dict[str, Any] | None) -> str:
    mode = (options or {}).get("quality_mode", QUALITY_BALANCED)
    return mode if mode in QUALITY_MODES else QUALITY_BALANCED


def _build_facts_block(research_data: dict[str, Any]) -> str:
    """Render research facts into a prompt block. Empty string if no facts."""
    facts = research_data.get("facts", {}) or {}
    parts: list[str] = []
    if facts.get("core_claim"):
        parts.append(f"核心主张：{facts['core_claim']}")
    if facts.get("key_facts"):
        parts.append("关键事实：\n" + "\n".join(f"- {f}" for f in facts["key_facts"][:5]))
    if facts.get("target_users"):
        tu = [f"- {u.get('segment', '')}：痛点「{u.get('pain', '')}」/ 欲望「{u.get('desire', '')}」"
              for u in facts["target_users"][:3] if isinstance(u, dict)]
        if tu:
            parts.append("目标用户：\n" + "\n".join(tu))
    if facts.get("unique_angles"):
        parts.append("独特角度：" + "、".join(facts["unique_angles"][:3]))
    if facts.get("use_cases"):
        parts.append("使用场景：" + "、".join(facts["use_cases"][:3]))
    return "\n\n".join(parts) if parts else ""


def _build_context_blocks(state: "PipelineState", *, clarifications_intro: str) -> tuple[str, str]:
    """Build the (references, clarifications) prompt blocks shared by research
    and blueprint stages.

    ``clarifications_intro`` is the stage-specific lead-in line — research
    frames them as "fact requirements to cover", blueprint as "user-supplied
    facts to honor". Returns empty strings when the underlying state is absent.
    """
    refs = state.get("references")
    references_block = format_examples_for_prompt(refs["examples"]) if refs and refs.get("examples") else ""

    clarifications_block = ""
    clar = state.get("clarifications")
    if clar and clar.get("answers"):
        lines = [f"- {q}: {a}" for q, a in clar["answers"].items() if a]
        if lines:
            clarifications_block = f"{clarifications_intro}\n" + "\n".join(lines)

    return references_block, clarifications_block


# Cap and flatten text sourced from LLM output before injecting it back into a
# prompt (e.g. critic descriptions written into research clarifications). This
# limits prompt-injection blast radius — a malicious description can't smuggle
# long instructions or newlines into the research prompt.
_SANITIZED_TEXT_LIMIT = 200


def _sanitize_for_prompt(text: Any) -> str:
    """Trim, flatten, and cap LLM-sourced text before prompt injection."""
    flat = " ".join(str(text or "").split())
    if len(flat) > _SANITIZED_TEXT_LIMIT:
        flat = flat[:_SANITIZED_TEXT_LIMIT] + "…"
    return flat


# ---------------------------------------------------------------------------
# Critic prompt + normalization helpers
#
# The problem-type tuple is the single source of truth shared by the critic
# prompt text and the output-normalization gate — joining it reproduces the
# old literal "fact_insufficient|structure_issue|expression_weak" byte-for-byte,
# so prompt and gate can never drift apart.
# ---------------------------------------------------------------------------

_CRITIC_SCORE_AXES = ("fidelity", "engagement", "alignment")
_CRITIC_PROBLEM_TYPES = ("fact_insufficient", "structure_issue", "expression_weak")
_CRITIC_PRIMARY_TYPES = _CRITIC_PROBLEM_TYPES + ("none",)  # primary_problem_type also allows "none"
_CRITIC_DEGRADE_PRIMARY = "expression_weak"  # conservative fallback when the critic output is malformed

_CRITIC_SYSTEM_PROMPT_TEMPLATE = (
    "你是{platform}内容质量评审。对生成内容按三轴打分（1-5）并给出具体问题。"
    "输出严格 JSON。"
)

# Prompt-side renderings of the type lists — derived from the same tuples the
# normalization gate uses, so the prompt and the gate cannot disagree.
_CRITIC_PROBLEM_TYPES_PROMPT = "|".join(_CRITIC_PROBLEM_TYPES)
_CRITIC_PRIMARY_TYPES_PROMPT = "|".join(_CRITIC_PRIMARY_TYPES)


def _build_critic_user_prompt(platform: str, content: dict[str, Any],
                              facts_block: str, spec: dict[str, Any]) -> str:
    """Render the critic's user prompt (static schema/definitions + dynamic payload)."""
    facts_section = f"【研究事实】\n{facts_block}" if facts_block else "【研究事实】（无）"
    weights = _get_critic_weights(platform)
    weight_note = ""
    if any(w != 1.0 for w in weights.values()):
        heavy = [f"{k}({v})" for k, v in weights.items() if v > 1.0]
        if heavy:
            weight_note = f"\n\n注意：{platform}的内容特性决定了评分权重不同——{'、'.join(heavy)}权重更高，请重点审视这些维度。"
    return f"""评审以下{platform}内容：

{facts_section}

【平台规格】
{json.dumps(spec, ensure_ascii=False)}

【待评内容】
标题：{content.get('title', '')}
正文：{content.get('markdown', '')}
标签：{content.get('hashtags', [])}

请按以下 JSON 格式输出评分：
{{
  "scores": {{
    "fidelity": 1-5,
    "engagement": 1-5,
    "alignment": 1-5
  }},
  "classified_issues": [
    {{
      "type": "{_CRITIC_PROBLEM_TYPES_PROMPT}",
      "description": "具体问题描述",
      "suggested_edit": {{"_selectVariant": {{"hook-main": 1}}}} or null
    }}
  ],
  "primary_problem_type": "{_CRITIC_PRIMARY_TYPES_PROMPT}",
  "issues": ["具体问题1：哪里偏离了事实/开头不够抓人/不像平台原生", "..."],
  "improvements": ["对应改进建议1", "..."]
}}

三轴定义：
- fidelity（事实保真）：内容是否可核验、是否包含研究关键事实、有无编造
- engagement（吸引力）：开头3秒是否抓人、是否有具体场景/数字、是否避免模板腔
- alignment（平台原生感）：是否符合平台风格/结构/长度、是否像广告感而非真实分享{weight_note}

问题分类：
- fact_insufficient：事实不足/编造 → 需要回 research 补证据
- structure_issue：结构/顺序/变体选择不对 → 需要回 blueprint 调结构（suggested_edit 给出 edit_blueprint 格式的编辑，如 _selectVariant/_setStructure/_reorder）
- expression_weak：表达/语气/用词不佳 → 只需重写 produce
- none：无明显问题

primary_problem_type 选最严重的一类。suggested_edit 仅 structure_issue 时给，其他填 null。"""


def _get_critic_weights(platform: str) -> dict[str, float]:
    """Return per-axis critic weights for a platform (from PlatformSpec)."""
    from .platforms import get_platform
    spec = get_platform(platform)
    if spec and spec.critic_weights:
        return spec.critic_weights
    return {"fidelity": 1.0, "engagement": 1.0, "alignment": 1.0}


def _weighted_critic_total(scores: dict[str, Any], weights: dict[str, float]) -> float:
    """Calculate weighted total: sum(score[k] * weight[k]) for each axis."""
    return sum(int(scores.get(k, 0) or 0) * weights.get(k, 1.0) for k in _CRITIC_SCORE_AXES)


def _critic_should_rewrite(scores: dict[str, Any], total: float) -> bool:
    """Rewrite when any axis drops below 3 (absolute hard line) or weighted total < 10."""
    return any(int(scores.get(k, 0) or 0) < 3 for k in _CRITIC_SCORE_AXES) or total < 10


def _normalize_critique(critique: dict[str, Any]) -> dict[str, Any]:
    """Tolerate non-standard critic output.

    Coalesces the two old ad-hoc guards (classified_issues shape + primary
    problem type) into one place. MUST NOT touch scores/total/should_rewrite —
    those are computed by the caller after this returns.
    """
    classified = critique.get("classified_issues")
    if not isinstance(classified, list) or not classified:
        critique["classified_issues"] = []
    primary = critique.get("primary_problem_type")
    if primary not in _CRITIC_PRIMARY_TYPES:
        # Conservative degradation: only rewrite produce, never trigger an
        # upstream backflow on an ambiguous signal.
        primary = _CRITIC_DEGRADE_PRIMARY
    critique["primary_problem_type"] = primary
    return critique


@dataclass
class _ProduceContext:
    """Aggregates backflow prerequisites so they flow as one object instead of
    six separate kwargs through ``_generate_single_platform`` →
    ``_review_and_rewrite`` → ``_backflow_*``.

    ``None`` fields mean the prerequisite is absent — backflow degrades to
    produce-only rewrite. The predicate methods keep that gating logic in one
    place instead of scattered ``and ... is not None`` chains.
    """
    state: "PipelineState | None" = None
    result: dict[str, Any] | None = None
    full_research: dict[str, Any] | None = None
    full_blueprint: dict[str, Any] | None = None
    blueprint_data: dict[str, Any] | None = None
    references: list[str] | None = None
    quality_mode: str = QUALITY_BALANCED

    def can_backflow_research(self) -> bool:
        return self.state is not None and self.result is not None and self.full_research is not None

    def can_backflow_blueprint(self) -> bool:
        return self.full_blueprint is not None and self.blueprint_data is not None


# ---------------------------------------------------------------------------
# Pipeline State Management
# ---------------------------------------------------------------------------

class PipelineState:
    """Manages pipeline execution state with caching."""

    def __init__(self, source_id: str, cache_dir: Path | None = None):
        self.source_id = source_id
        self.cache_dir = cache_dir or Path(
            os.environ.get("PROMOAGENT_CACHE_DIR")
            or Path.home() / ".cache" / "promoagent" / "pipeline"
        )
        self.state_file = self.cache_dir / f"pipeline_{source_id}.json"
        self.stages: dict[str, Any] = {}
        self.metadata: dict[str, Any] = {
            "created": time.time(),
            "updated": time.time(),
            "version": "2.0",
        }
        # Guards the in-memory stages dict. Parallel produce workers can trigger
        # cross-stage backflow (which re-runs research/blueprint and calls
        # state.set) concurrently — without this lock, concurrent dict mutation
        # corrupts state. The atomic file write (os.replace) handles disk; this
        # handles the shared Python object.
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                self.stages = data.get("stages", {})
                self.metadata = data.get("metadata", self.metadata)
            except (json.JSONDecodeError, IOError):
                pass

    def save(self) -> None:
        """Atomically persist state to disk.

        Writes to a sibling temp file then ``os.replace`` swaps it into place.
        ``os.replace`` is atomic on POSIX and Windows, so concurrent writers
        (e.g. parallel MCP requests sharing a source_id) never leave a
        half-written state file — readers see either the old or the new
        version, never a truncated one.
        """
        self.metadata["updated"] = time.time()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"source_id": self.source_id, "stages": self.stages, "metadata": self.metadata},
            ensure_ascii=False,
            indent=2,
        )
        tmp = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, self.state_file)

    def get(self, stage: str) -> dict[str, Any] | None:
        with self._lock:
            return self.stages.get(stage)

    def set(self, stage: str, data: dict[str, Any]) -> None:
        with self._lock:
            self.stages[stage] = data
            self.save()

    def has(self, stage: str) -> bool:
        with self._lock:
            return stage in self.stages

    def is_stale(self, stage: str, upstream: str) -> bool:
        """Return True if ``stage``'s cached ``_upstream`` snapshot is older than
        the current ``upstream`` output — i.e. the upstream was regenerated
        after this stage was last built, so the cache is stale.

        Returns False when either side is missing (no cache, or old cache
        without the ``_upstream`` field), so the first run self-heals without
        forcing a recompute.
        """
        with self._lock:
            cached = self.stages.get(stage)
            if not isinstance(cached, dict):
                return False
            recorded = (cached.get("_upstream") or {}).get(upstream)
            if recorded is None:
                return False  # old cache without upstream tracking — tolerate it
            upstream_out = self.stages.get(upstream)
            if not isinstance(upstream_out, dict):
                return False
            actual = upstream_out.get("timestamp")
            if actual is None:
                return False
            return recorded != actual

    def clear(self) -> None:
        self.stages = {}
        self.save()


def _source_id(result: dict[str, Any]) -> str:
    """Generate unique ID for source content."""
    target = str(result.get("target", ""))
    name = result.get("project", {}).get("name", "")
    content = f"{name}:{target}".encode("utf-8")
    return hashlib.sha256(content).hexdigest()[:16]


def _classify_example_source(examples: list[str]) -> str:
    """Classify where reference examples came from, for state metadata."""
    if not examples:
        return "none"
    # find_examples falls back to AI generation when no search key is present;
    # otherwise results came from Tavily/Exa. We cannot tell the exact provider
    # after the fact, so "search" covers any non-empty web/AI result.
    return "search"


def _gather_references(result: dict[str, Any], options: dict[str, Any] | None) -> dict[str, Any]:
    """Search for reference ads/examples; never raises."""
    try:
        examples = find_examples(result, platform="all", ai_options=options, verbose=False)
    except Exception as exc:  # noqa: BLE001 — search must never break research
        logger.warning("reference search failed", error=str(exc))
        examples = []
    return {
        "examples": examples,
        "searched": True,
        "source": _classify_example_source(examples),
        "timestamp": time.time(),
    }


# ---------------------------------------------------------------------------
# Stage 1: RESEARCH - Extract facts and strategy
# ---------------------------------------------------------------------------

def stage_research(
    result: dict[str, Any],
    state: PipelineState,
    options: dict[str, Any] | None = None,
    force: bool = False,
    search: bool = True,
) -> dict[str, Any]:
    """Research stage: Extract facts, positioning, and strategy in one call.

    When ``search`` is true, reference ads are fetched via :func:`find_examples`
    and injected into the prompt. Results are stored under ``state["references"]``
    so downstream stages and ``--resume`` can reuse them without re-searching.
    """
    if not force and state.has("research"):
        logger.info("using cached research stage")
        return state.get("research")

    config = ai_config(options)
    project = result.get("project", {})
    evidence = result.get("evidence", {})

    # Gather reference ads (skipped when --no-search). On force, re-search.
    if search:
        references = _gather_references(result, options)
    else:
        references = {"examples": [], "searched": False, "source": "disabled", "timestamp": time.time()}
    state.set("references", references)
    references_block = format_examples_for_prompt(references["examples"])

    # Clarifications: user answers from --interactive gaps prompting, OR
    # fact-gap feedback written by a produce-stage backflow. Either way, the
    # research stage should treat them as "please cover these" hints.
    _, clarifications_block = _build_context_blocks(
        state, clarifications_intro="用户/评审补充的事实要求（请重点补充这些信息，缺失则记入 gaps）"
    )

    # Build concise source summary
    source_summary = {
        "name": project.get("name", ""),
        "description": project.get("description", ""),
        "topics": project.get("topics", []),
        "source_type": result.get("source", ""),
        "readme_opening": (evidence.get("readmeOpening") or evidence.get("opening") or "")[:400],
        "first_screen": (evidence.get("firstScreen") or "")[:400],
        "key_features": evidence.get("keyFeatures", [])[:5],
        "key_actions": [a for a in (evidence.get("keyActions") or [])[:5] if a],
        "proof_points": [p for p in (evidence.get("proofPoints") or [])[:5] if p],
        "headings": [h.get("text", "") for h in (evidence.get("headings") or [])[:6]
                     if isinstance(h, dict) and h.get("text")],
        "target_audience": evidence.get("targetAudience", []),
    }

    system_prompt = """你是推广研究专家。从来源材料中提取关键信息并制定推广策略。
只使用来源中明确的信息，标记缺失部分。
输出严格 JSON。"""

    references_section = f"\n{references_block}\n" if references_block else ""
    clarifications_section = f"\n{clarifications_block}\n" if clarifications_block else ""
    user_prompt = f"""分析以下项目/内容，提取关键信息并制定推广策略：

{json.dumps(source_summary, ensure_ascii=False, indent=2)}
{references_section}{clarifications_section}
请输出以下格式的 JSON：
{{
  "facts": {{
    "core_claim": "一句话核心主张（基于证据）",
    "key_facts": ["事实1", "事实2", "事实3"],
    "unique_angles": ["独特角度1", "独特角度2"],
    "target_users": [{{"segment": "人群", "pain": "痛点", "desire": "欲望"}}],
    "use_cases": ["场景1", "场景2"],
    "evidence_strength": "high|medium|low",
    "gaps": ["信息缺口1", "信息缺口2"],
    "risks": ["推广风险1"]
  }},
  "strategy": {{
    "positioning": {{
      "one_liner": "25字以内定位",
      "promise": "用户能得到什么",
      "differentiator": "核心差异点"
    }},
    "creative_direction": {{
      "main_hook": "主推角度",
      "hook_variants": ["变体1", "变体2", "变体3"],
      "tone": "语气风格",
      "key_message": "核心信息"
    }},
    "recommended_platforms": ["平台1", "平台2", "平台3"],
    "platform_rationale": "选择理由",
    "content_sequence": ["首发平台", "后续平台"]
  }}
}}

要求：
- 所有信息必须基于来源材料
- key_facts 优先使用 proof_points 和 key_actions 中的可核验事实（带数字/场景/具体动作）
- 明确标记无法验证的内容
- 策略要具体可执行，避免空泛"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    logger.info("running research stage")
    response = dispatch_chat(messages, config)
    parsed = parse_json_content(response)

    output = {
        "stage": "research",
        "data": parsed,
        "raw": response,
        "messages": messages,
        "timestamp": time.time(),
        "_upstream": {},  # research is the source — downstream tracks its timestamp
    }

    state.set("research", output)
    return output


# ---------------------------------------------------------------------------
# Stage 2: BLUEPRINT - Structured editable content (Tweet Space)
# ---------------------------------------------------------------------------

# Dynamic element templates
ELEMENT_TEMPLATES = {
    "hook": {
        "label": "开场钩子",
        "description": "前3秒抓住注意力的开场",
        "char_limit": 100,
        "required": True,
        "variants_required": 3,
    },
    "context": {
        "label": "背景/场景",
        "description": "建立共鸣的场景描述",
        "char_limit": 200,
        "required": True,
    },
    "problem": {
        "label": "痛点/问题",
        "description": "用户面临的挑战",
        "char_limit": 150,
        "required": False,
    },
    "solution": {
        "label": "解决方案",
        "description": "产品/服务如何解决",
        "char_limit": 200,
        "required": True,
    },
    "proof": {
        "label": "证据/数据",
        "description": "支持主张的事实",
        "char_limit": 150,
        "required": False,
    },
    "benefit": {
        "label": "用户收益",
        "description": "用户能得到什么价值",
        "char_limit": 150,
        "required": True,
    },
    "objection": {
        "label": "顾虑回应",
        "description": "常见疑虑及解答",
        "char_limit": 150,
        "required": False,
    },
    "story": {
        "label": "故事片段",
        "description": "具体使用场景故事",
        "char_limit": 250,
        "required": False,
    },
    "cta": {
        "label": "行动号召",
        "description": "明确的下一步行动",
        "char_limit": 80,
        "required": True,
        "variants_required": 3,
    },
}


def stage_blueprint(
    research: dict[str, Any],
    state: PipelineState,
    result: dict[str, Any],
    options: dict[str, Any] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Blueprint stage: Generate structured content elements.

    Creates editable Tweet Space with dynamic element selection.
    """
    if not force and state.has("blueprint") and not state.is_stale("blueprint", "research"):
        logger.info("using cached blueprint stage")
        return state.get("blueprint")

    config = ai_config(options)
    research_data = research.get("data", {})
    facts = research_data.get("facts", {})
    strategy = research_data.get("strategy", {})

    project = result.get("project", {})

    # Determine which elements to include based on content type
    default_elements = ["hook", "context", "solution", "benefit", "cta"]
    if facts.get("key_facts"):
        default_elements.insert(3, "proof")
    if strategy.get("creative_direction", {}).get("tone") == "problem_solution":
        default_elements.insert(2, "problem")

    element_types = default_elements

    # Build element generation prompt
    element_specs = []
    for elem_type in element_types:
        template = ELEMENT_TEMPLATES.get(elem_type, {})
        spec = {
            "type": elem_type,
            "label": template.get("label", elem_type),
            "description": template.get("description", ""),
            "char_limit": template.get("char_limit", 200),
            "required": template.get("required", False),
        }
        if template.get("variants_required"):
            spec["variants_count"] = template["variants_required"]
        element_specs.append(spec)

    system_prompt = """你是内容结构专家。将推广策略转化为可编辑的内容元素。
每个元素要有明确目的和字数限制，为关键元素提供多个变体。
输出严格 JSON。"""

    # Optional context blocks: reference ads + user clarifications.
    references_block, clarifications_block = _build_context_blocks(
        state, clarifications_intro="用户补充信息（请优先纳入这些事实，不要与来源冲突时忽略参考示例）"
    )

    context_blocks = "\n\n".join(b for b in (references_block, clarifications_block) if b)
    context_section = f"\n{context_blocks}\n" if context_blocks else ""

    user_prompt = f"""基于以下研究和策略，生成 Blueprint 结构化内容：

项目名称：{project.get('name', 'N/A')}
定位：{strategy.get('positioning', {}).get('one_liner', 'N/A')}
核心主张：{facts.get('core_claim', 'N/A')}
主推角度：{strategy.get('creative_direction', {}).get('main_hook', 'N/A')}
钩子变体：{json.dumps(strategy.get('creative_direction', {}).get('hook_variants', []), ensure_ascii=False)}
{context_section}
需要生成的内容元素：
{json.dumps(element_specs, ensure_ascii=False, indent=2)}

请输出以下格式的 JSON：
{{
  "version": "2.0",
  "source": {{
    "project_name": "{project.get('name', '')}",
    "source_url": ""
  }},
  "positioning": {{
    "one_liner": "{strategy.get('positioning', {}).get('one_liner', '')}",
    "core_promise": "{strategy.get('positioning', {}).get('promise', '')}",
    "key_message": "{strategy.get('creative_direction', {}).get('key_message', '')}"
  }},
  "elements": [
    {{
      "id": "元素ID（如hook-main）",
      "type": "元素类型",
      "label": "显示标签",
      "content": "具体内容文案",
      "variants": ["变体1", "变体2"],
      "char_limit": 字数限制,
      "purpose": "该元素的作用",
      "editable": true,
      "required": true|false
    }}
  ],
  "structure": {{
    "recommended_order": ["元素ID1", "元素ID2"],
    "alternative_structures": [
      {{"name": "故事型", "order": ["hook", "story", "solution", "cta"]}},
      {{"name": "问题型", "order": ["hook", "problem", "solution", "proof", "cta"]}}
    ]
  }},
  "metrics": {{
    "estimated_read_time": "预估阅读时间",
    "emotion_profile": "情感画像",
    "complexity_score": "复杂度评分1-10"
  }}
}}

要求：
1. 生成所有指定的元素类型
2. hook 和 cta 必须提供3个变体
3. 内容必须基于研究和策略
4. 每个元素都要有明确 purpose"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    logger.info("running blueprint stage")
    response = dispatch_chat(messages, config)
    parsed = parse_json_content(response)

    # Validate and enrich blueprint
    elements = parsed.get("elements", [])
    for element in elements:
        element["editable"] = True
        if element.get("id") in ["hook-main", "cta-main"]:
            element["variants"] = element.get("variants", [])[:3]

    research_ts = research.get("timestamp") if isinstance(research, dict) else None
    output = {
        "stage": "blueprint",
        "data": parsed,
        "raw": response,
        "messages": messages,
        "timestamp": time.time(),
        "_upstream": {"research": research_ts},
    }

    state.set("blueprint", output)
    return output


# ---------------------------------------------------------------------------
# Blueprint Editing Functions
# ---------------------------------------------------------------------------

def edit_blueprint(
    blueprint: dict[str, Any],
    edits: dict[str, Any],
) -> dict[str, Any]:
    """Apply edits to blueprint.

    Edit formats:
    - {element_id: new_content} - Update element content
    - {"_selectVariant": {"element_id": variant_index}} - Select variant
    - {"_reorder": [element_id1, element_id2]} - Reorder elements
    - {"_addElement": element_def} - Add new element
    - {"_removeElement": element_id} - Remove element
    - {"_setStructure": structure_name} - Apply alternative structure
    """
    data = blueprint.get("data", {}).copy()
    if "edit_history" not in data:
        data["edit_history"] = []

    def record(entry: dict[str, Any]) -> None:
        entry.setdefault("timestamp", time.time())
        data["edit_history"].append(entry)

    # 1. Content edits (keys not starting with "_").
    elements_by_id = {e["id"]: e for e in data.get("elements", [])}
    for key, value in edits.items():
        if key.startswith("_"):
            continue
        if key in elements_by_id:
            old = elements_by_id[key].get("content", "")
            elements_by_id[key]["content"] = value
            elements_by_id[key]["edited"] = True
            record({"type": "content", "element_id": key, "old": old, "new": value})

    # 2. Special commands — each handler re-reads data["elements"] so it sees
    #    the effect of earlier handlers (e.g. _addElement then _reorder).
    if "_selectVariant" in edits:
        _apply_select_variant(data, edits["_selectVariant"], record)
    if "_reorder" in edits:
        _apply_reorder(data, edits["_reorder"], record)
    if "_addElement" in edits:
        _apply_add_element(data, edits["_addElement"], record)
    if "_removeElement" in edits:
        _apply_remove_element(data, edits["_removeElement"], record)
    if "_setStructure" in edits:
        _apply_set_structure(data, edits["_setStructure"], record)

    blueprint["data"] = data
    return blueprint


def _apply_select_variant(data: dict, selections: dict, record) -> None:
    by_id = {e["id"]: e for e in data.get("elements", [])}
    for elem_id, idx in selections.items():
        element = by_id.get(elem_id)
        if element is None:
            continue
        variants = element.get("variants", [])
        if 0 <= idx < len(variants):
            old = element.get("content", "")
            element["content"] = variants[idx]
            element["selected_variant"] = idx
            record({"type": "variant_select", "element_id": elem_id,
                    "variant_index": idx, "old": old, "new": variants[idx]})


def _apply_reorder(data: dict, new_order: list, record) -> None:
    by_id = {e["id"]: e for e in data.get("elements", [])}
    valid_ids = set(by_id)
    if all(eid in valid_ids for eid in new_order):
        data["elements"] = [by_id[eid] for eid in new_order]
        record({"type": "reorder", "new_order": new_order})


def _apply_add_element(data: dict, new_elem: dict, record) -> None:
    elements = data.get("elements", [])
    new_elem["id"] = new_elem.get("id", f"custom-{len(elements)}")
    new_elem["editable"] = True
    elements.append(new_elem)
    data["elements"] = elements  # ensure key exists / stays in sync
    record({"type": "add", "element": new_elem})


def _apply_remove_element(data: dict, elem_id: str, record) -> None:
    data["elements"] = [e for e in data.get("elements", []) if e.get("id") != elem_id]
    record({"type": "remove", "element_id": elem_id})


def _apply_set_structure(data: dict, structure_name: str, record) -> None:
    structures = data.get("structure", {}).get("alternative_structures", [])
    by_id = {e["id"]: e for e in data.get("elements", [])}
    for struct in structures:
        if struct.get("name") != structure_name:
            continue
        order = struct.get("order", [])
        if all(eid in by_id for eid in order):
            data["elements"] = [by_id[eid] for eid in order]
            record({"type": "structure_change", "structure": structure_name})
        break


def preview_blueprint(blueprint: dict[str, Any], format: str = "markdown") -> str:
    """Generate preview of blueprint content.

    Formats: markdown, plain, platform_hint
    """
    data = blueprint.get("data", {})
    elements = data.get("elements", [])

    if format == "plain":
        return "\n\n".join([e.get("content", "") for e in elements if e.get("content")])

    lines = [f"# {data.get('source', {}).get('project_name', 'Preview')}", ""]
    lines.append(f"**定位**: {data.get('positioning', {}).get('one_liner', '')}")
    lines.append("")

    for element in elements:
        if not element.get("content"):
            continue

        label = element.get("label", element.get("type", ""))
        content = element.get("content", "")

        lines.append(f"## {label}")
        lines.append(content)

        # Show available variants
        variants = element.get("variants", [])
        selected = element.get("selected_variant")
        if variants:
            lines.append("")
            for i, v in enumerate(variants, 1):
                marker = "✓" if selected == i - 1 else " "
                lines.append(f"  [{marker}] {i}. {v}")
        lines.append("")

    # Show metrics
    metrics = data.get("metrics", {})
    if metrics:
        lines.append("---")
        lines.append(f"预估阅读时间: {metrics.get('estimated_read_time', 'N/A')}")
        lines.append(f"情感画像: {metrics.get('emotion_profile', 'N/A')}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage 3: PRODUCE - Platform content generation (Parallel)
# ---------------------------------------------------------------------------

def _generate_single_platform(
    platform: str,
    blueprint_data: dict[str, Any],
    research_data: dict[str, Any],
    options: dict[str, Any],
    quality_mode: str = QUALITY_BALANCED,
    references: list[str] | None = None,
    ctx: _ProduceContext | None = None,
) -> tuple[str, dict[str, Any]]:
    """Generate content for a single platform.
    ``quality_mode`` controls enrichment:
    - fast: facts only (1 LLM call)
    - balanced: facts + platform playbook + few-shot references (1 call)
    - polished: balanced + critic review + conditional rewrite (2-3 calls)
    """
    config = ai_config(options)

    # Get platform spec from centralized config
    spec_obj = get_platform(platform)
    if spec_obj is None:
        logger.warning(f"Unknown platform: {platform}, using default")
        spec_obj = get_platform("xiaohongshu")

    spec = to_prompt_dict(spec_obj)

    # Order elements by the blueprint's recommended_order when present, so that
    # user edits to structure (reorder / setStructure) actually affect the
    # produced content instead of being cosmetic metadata.
    elements = list(blueprint_data.get("elements", []))
    order = (blueprint_data.get("structure") or {}).get("recommended_order") or []
    if order:
        by_id = {e.get("id"): e for e in elements if isinstance(e, dict)}
        ordered = [by_id[eid] for eid in order if eid in by_id]
        # Append any elements not listed in the order (e.g. added via _addElement).
        ordered.extend(e for e in elements if e.get("id") not in set(order))
        elements = ordered or elements

    elements_text = "\n\n".join([
        f"[{e.get('label', e.get('type'))}]\n{e.get('content', '')}"
        for e in elements if isinstance(e, dict)
    ])

    # --- Enrichment blocks (all modes get facts; balanced+ get more) ---
    facts_block = _build_facts_block(research_data)

    playbook_block = ""
    if quality_mode in (QUALITY_BALANCED, QUALITY_POLISHED):
        playbook_block = format_playbook_for_prompt(platform)

    examples_block = ""
    if quality_mode in (QUALITY_BALANCED, QUALITY_POLISHED) and references:
        examples_block = format_examples_for_prompt(references)

    system_extra = f"\n\n{playbook_block}" if playbook_block else ""

    # Polished mode: front-load the critic's quality standard so the model
    # generates to target on the first try, reducing rewrite passes.
    quality_constraints = ""
    if quality_mode == QUALITY_POLISHED:
        weights = _get_critic_weights(platform)
        weight_hint = ""
        heavy = max(weights, key=weights.get) if weights else ""
        if heavy and weights.get(heavy, 1.0) > 1.0:
            weight_hint = f"\n{platform}尤其重视{heavy}（权重更高），请确保该维度达到4分以上。"
        quality_constraints = f"""

【质量标准】你的输出将按以下三轴评分（1-5），请生成时即对标：
- fidelity（事实保真）≥4：内容可核验，包含「关键事实」中至少2条，无编造。
- engagement（吸引力）≥4：开头3秒抓人，有具体场景/数字，避免模板腔。
- alignment（平台原生感）≥4：符合{platform}的风格/结构/长度，像真实分享非广告感。{weight_hint}
未达标的内容会被重写，请一次做好。"""

    system_prompt = f"""你是{platform}内容专家。将 Blueprint 转换为该平台原生格式。
平台特点：{spec['style']}，{spec['tone']}
{system_extra}{quality_constraints}
输出严格 JSON。""".strip()

    facts_section = f"\n\n{facts_block}\n" if facts_block else ""
    examples_section = f"\n\n{examples_block}\n" if examples_block else ""
    user_prompt = f"""将以下内容转换为{platform}格式：

定位：{blueprint_data.get('positioning', {}).get('one_liner', '')}{facts_section}{examples_section}

内容元素：
{elements_text}

平台规格：{json.dumps(spec, ensure_ascii=False)}

请输出以下格式的 JSON：
{{
  "platform": "{platform}",
  "title": "标题（如有）",
  "markdown": "完整内容（{spec['length']}）",
  "hashtags": ["标签1", "标签2"],
  "thread": ["推文1", "推文2"],
  "publish_notes": "发布建议"
}}

要求：
- 严格遵循平台风格和字数限制
- 按内容元素的给定顺序组织正文（这是用户编辑后的结构，不要自行重排）
- 基于 Blueprint 元素和研究事实，不要添加未提及的信息
- markdown 正文必须包含「关键事实」中至少 2 条可核验信息，不要泛泛而谈
- hashtags 要符合平台习惯"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = dispatch_chat(messages, config)
        parsed = parse_json_content(response)
    except Exception as e:
        logger.error(f"platform generation failed", platform=platform, error=str(e))
        return platform, {"error": str(e)}

    # --- Polished: critic review + conditional backflow ---
    if quality_mode == QUALITY_POLISHED and "error" not in parsed:
        parsed = _review_and_rewrite(
            platform, parsed, research_data, spec, messages, response, options, ctx,
        )

    return platform, parsed


def _review_and_rewrite(
    platform: str,
    content: dict[str, Any],
    research_data: dict[str, Any],
    spec: dict[str, Any],
    original_messages: list[dict[str, str]],
    original_response: str,
    options: dict[str, Any],
    ctx: _ProduceContext | None = None,
) -> dict[str, Any]:
    """Critic pass + cross-stage backflow. At most one backflow attempt.

    Routes the critic's primary_problem_type via :func:`_route_backflow`:
    - fact_insufficient → re-run research (via clarifications) + blueprint + this platform
    - structure_issue  → edit_blueprint with suggested_edits + re-run this platform
    - expression_weak  → existing _rewrite_platform (produce-only)
    """
    ctx = ctx or _ProduceContext()
    critique = _critic_platform(platform, content, research_data, spec, options)
    meta: dict[str, Any] = {
        "quality_mode": ctx.quality_mode,
        "critique": critique,
        "rewritten": False,
        "backflow": None,
    }

    if not critique.get("should_rewrite"):
        content["_meta"] = meta
        return content

    # If the critic returned no usable scores AND no structured issues, the
    # output was malformed — rewriting off a zero score can't improve anything
    # and just wastes a call. Keep the original and record the skip.
    scores = critique.get("scores") or {}
    has_scores = any(int(scores.get(k, 0) or 0) > 0 for k in ("fidelity", "engagement", "alignment"))
    has_classified = bool(critique.get("classified_issues"))
    if not has_scores and not has_classified:
        meta["skipped"] = "critic_output_unusable"
        content["_meta"] = meta
        return content

    problem_type = critique.get("primary_problem_type", "expression_weak")
    pre_score = critique.get("total", 0)

    # Route to a cross-stage backflow when applicable. `routed` distinguishes
    # "no branch matched" (→ fall through to produce-only rewrite) from
    # "a branch matched but the upstream rerun failed" (→ keep original, do NOT
    # rewrite). The elif chain in the old code implied this; the triple makes
    # it explicit so a failed backflow isn't mistaken for an un-routed case.
    new_content, backflow_stage, routed = _route_backflow(
        platform, problem_type, critique, research_data,
        original_messages, original_response, options, ctx,
    )
    if new_content is not None:
        content = new_content
    if not routed:
        # expression_weak or missing prerequisites — produce-only rewrite.
        rewritten = _rewrite_platform(original_messages, original_response, critique, options)
        if rewritten and "error" not in rewritten:
            content = rewritten
            meta["rewritten"] = True

    # One more critic pass after backflow (no recursion). Records final score.
    if backflow_stage != "none":
        post_critique = _critic_platform(platform, content, research_data, spec, options)
        meta["backflow"] = {
            "attempted": True,
            "stage": backflow_stage,
            "pre_backflow_score": pre_score,
            "post_backflow_score": post_critique.get("total", 0),
            "reason": problem_type,
        }
        meta["critique"] = post_critique

    content["_meta"] = meta
    return content


def _route_backflow(
    platform: str,
    problem_type: str,
    critique: dict[str, Any],
    research_data: dict[str, Any],
    original_messages: list[dict[str, str]],
    original_response: str,
    options: dict[str, Any],
    ctx: _ProduceContext,
) -> tuple[dict[str, Any] | None, str, bool]:
    """Pick a cross-stage backflow branch based on ``problem_type``.

    Returns ``(new_content, stage, routed)``:
    - ``routed=False`` → no branch matched (or prerequisites missing); caller
      should fall back to produce-only rewrite.
    - ``routed=True``  → a branch matched; ``new_content`` may still be ``None``
      if the upstream rerun failed (caller keeps the original, does NOT rewrite).
    """
    if problem_type == "fact_insufficient" and ctx.can_backflow_research():
        return _backflow_platform("research", platform, critique, ctx, research_data, options), "research", True
    if problem_type == "structure_issue" and ctx.can_backflow_blueprint():
        return _backflow_platform("blueprint", platform, critique, ctx, research_data, options), "blueprint", True
    return None, "none", False


def _collect_suggested_edits(critique: dict[str, Any]) -> dict[str, Any]:
    """Extract edit_blueprint-compatible edits from the critique's classified_issues."""
    edits: dict[str, Any] = {}
    for issue in critique.get("classified_issues") or []:
        if not isinstance(issue, dict):
            continue
        if issue.get("type") != "structure_issue":
            continue
        suggested = issue.get("suggested_edit")
        if isinstance(suggested, dict):
            for k, v in suggested.items():
                # Don't overwrite an earlier edit of the same key.
                edits.setdefault(k, v)
    return edits


def _backflow_platform(
    stage: str,
    platform: str,
    critique: dict[str, Any],
    ctx: _ProduceContext,
    research_data: dict[str, Any],
    options: dict[str, Any],
) -> dict[str, Any] | None:
    """Re-run an upstream stage, then regenerate this platform's content.

    ``stage`` is "research" (re-run research + blueprint) or "blueprint"
    (apply suggested edits). Returns the regenerated content, or ``None`` if
    the upstream rerun failed (caller keeps the original).
    """
    if stage == "research":
        return _rerun_upstream_research(platform, critique, ctx, options)

    # stage == "blueprint"
    edits = _collect_suggested_edits(critique)
    if not edits:
        # No actionable edits → nothing to change upstream. Silent (no warning):
        # this isn't a failure, just an un-actionable critique.
        return None
    try:
        new_blueprint = edit_blueprint({"data": ctx.blueprint_data}, edits)
    except Exception as exc:  # noqa: BLE001
        logger.warning("backflow edit_blueprint failed", platform=platform, error=str(exc))
        return None
    return _regenerate_platform(platform, new_blueprint.get("data") or {},
                                research_data, ctx.references, options, ctx.quality_mode)


def _rerun_upstream_research(
    platform: str,
    critique: dict[str, Any],
    ctx: _ProduceContext,
    options: dict[str, Any],
) -> dict[str, Any] | None:
    """Re-run research with fact-gap hints, then blueprint, then this platform.

    NOTE: ``stage_research(force=True)`` and ``stage_blueprint(force=True)``
    write their results back to the shared ``state`` (their own ``state.set``
    calls). Under parallel produce with multiple platforms triggering this
    backflow simultaneously, research/blueprint get re-run once per platform
    and the last writer wins — the RLock on PipelineState prevents dict
    corruption, but the semantic overlap is an accepted trade-off (each
    platform still regenerates from its own freshly-returned ``new_research``
    / ``new_blueprint`` local reference).
    """
    # Write fact-gap hints into clarifications (merged, not overwriting user answers).
    # Sanitize each description before injection — it's LLM-sourced text going
    # back into the research prompt, so cap length and strip newlines.
    fact_gaps = [
        _sanitize_for_prompt(i.get("description", ""))
        for i in (critique.get("classified_issues") or [])
        if isinstance(i, dict) and i.get("type") == "fact_insufficient" and i.get("description")
    ]
    clar = dict(ctx.state.get("clarifications") or {})
    answers = dict(clar.get("answers") or {})
    for gap in fact_gaps[:3]:
        answers.setdefault(gap, "请补充可核验的事实或数据")
    clar["answers"] = answers
    clar["timestamp"] = time.time()
    # Write to state so stage_research can read it (research reads state).
    ctx.state.set("clarifications", clar)

    try:
        new_research = stage_research(ctx.result, ctx.state, options, force=True, search=False)
        new_blueprint = stage_blueprint(new_research, ctx.state, ctx.result, options, force=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("backflow research rerun failed", platform=platform, error=str(exc))
        return None

    return _regenerate_platform(platform, new_blueprint.get("data") or {},
                                new_research.get("data") or {}, ctx.references, options, ctx.quality_mode)


def _regenerate_platform(
    platform: str,
    blueprint_data: dict[str, Any],
    research_data: dict[str, Any],
    references: list[str] | None,
    options: dict[str, Any],
    quality_mode: str,
) -> dict[str, Any] | None:
    """Re-run a single platform's produce with fresh blueprint/research data.

    Uses balanced quality (no critic) so the regeneration itself doesn't
    recurse into another backflow — the caller does the final critic pass.
    """
    try:
        _, content = _generate_single_platform(
            platform, blueprint_data, research_data, options,
            quality_mode=QUALITY_BALANCED, references=references,
        )
        return content
    except Exception as exc:  # noqa: BLE001
        logger.warning("backflow regenerate failed", platform=platform, error=str(exc))
        return None


def _critic_platform(
    platform: str,
    content: dict[str, Any],
    research_data: dict[str, Any],
    spec: dict[str, Any],
    options: dict[str, Any],
) -> dict[str, Any]:
    """Score content on fidelity/engagement/alignment (1-5 each)."""
    config = ai_config(options)
    facts_block = _build_facts_block(research_data)

    messages = [
        {"role": "system", "content": _CRITIC_SYSTEM_PROMPT_TEMPLATE.format(platform=platform)},
        {"role": "user", "content": _build_critic_user_prompt(platform, content, facts_block, spec)},
    ]

    try:
        response = dispatch_chat(messages, config)
        critique = parse_json_content(response)
    except Exception as exc:  # noqa: BLE001 — critic failure must not break generation
        logger.warning("critic failed", platform=platform, error=str(exc))
        return {"scores": {}, "issues": [], "improvements": [], "total": 0,
                "should_rewrite": False, "primary_problem_type": _CRITIC_DEGRADE_PRIMARY,
                "classified_issues": [], "error": str(exc)}

    _normalize_critique(critique)

    scores = critique.get("scores", {}) or {}
    weights = _get_critic_weights(platform)
    total = _weighted_critic_total(scores, weights)
    critique["total"] = round(total, 1)  # weighted, may be non-integer
    critique["critic_weights"] = weights  # record for transparency
    critique["should_rewrite"] = _critic_should_rewrite(scores, total)
    return critique


def _rewrite_platform(
    original_messages: list[dict[str, str]],
    original_response: str,
    critique: dict[str, Any],
    options: dict[str, Any],
) -> dict[str, Any] | None:
    """Rewrite content based on critic feedback. At most one rewrite pass."""
    config = ai_config(options)
    issues = critique.get("issues", [])[:4]
    improvements = critique.get("improvements", [])[:4]
    feedback = (
        "评审发现以下问题，请修正后重新输出完整 JSON：\n\n"
        f"问题：\n- " + "\n- ".join(issues) +
        f"\n\n改进建议：\n- " + "\n- ".join(improvements) +
        "\n\n请输出修正后的完整 JSON，保持原格式。"
    )
    messages = original_messages + [
        {"role": "assistant", "content": original_response},
        {"role": "user", "content": feedback},
    ]
    try:
        response = dispatch_chat(messages, config)
        return parse_json_content(response)
    except Exception as exc:  # noqa: BLE001
        logger.warning("rewrite failed", error=str(exc))
        return None


def stage_produce(
    blueprint: dict[str, Any],
    research: dict[str, Any],
    state: PipelineState,
    options: dict[str, Any] | None = None,
    force: bool = False,
    platforms: list[str] | None = None,
    parallel: bool = True,
    quality_mode: str | None = None,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce stage: Generate platform-native content.

    Supports parallel generation for multiple platforms. ``quality_mode``
    (fast/balanced/polished) controls enrichment; a mode change bypasses cache.
    ``result`` (the original analyze_target output) enables polished-mode
    backflow to re-run research when the critic flags fact insufficiency.
    """
    quality_mode = quality_mode or _resolve_quality_mode(options)

    # Cache: hit only when the stored quality_mode matches AND no upstream
    # stage was regenerated since this produce was built.
    if not force and state.has("produce"):
        cached = state.get("produce")
        cached_mode = (cached.get("_meta") or {}).get("quality_mode", QUALITY_FAST)
        stale = (state.is_stale("produce", "research")
                 or state.is_stale("produce", "blueprint"))
        if cached_mode == quality_mode and not stale:
            logger.info("using cached produce stage")
            return cached
        logger.info("regenerating produce", cached_mode=cached_mode, requested=quality_mode, stale=stale)

    research_data = research.get("data", {})
    blueprint_data = blueprint.get("data", {})

    # Determine platforms to generate
    target_platforms = platforms or research_data.get("strategy", {}).get("recommended_platforms", ["xiaohongshu", "twitter"])

    # Reference ads for balanced/polished few-shot injection.
    references = (state.get("references") or {}).get("examples") or []

    # Bundle backflow prerequisites into one context object so they flow
    # through _generate_single_platform → _review_and_rewrite without a
    # six-kwargs parameter list.
    ctx = _ProduceContext(
        state=state, result=result,
        full_research=research, full_blueprint=blueprint,
        blueprint_data=blueprint_data, references=references,
        quality_mode=quality_mode,
    )

    logger.info("running produce stage", platforms=target_platforms, parallel=parallel, quality_mode=quality_mode)

    results = {}

    if parallel and len(target_platforms) > 1:
        # Parallel generation
        # Parallel produce: default 3 workers, configurable via env for large platform sets.
        max_workers = min(len(target_platforms), int(os.environ.get("PROMOAGENT_PRODUCE_WORKERS", "3")))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _generate_single_platform,
                    platform,
                    blueprint_data,
                    research_data,
                    options or {},
                    quality_mode,
                    references,
                    ctx,
                ): platform
                for platform in target_platforms
            }

            for future in as_completed(futures):
                platform = futures[future]
                try:
                    _, content = future.result()
                    results[platform] = content
                except Exception as e:
                    logger.error(f"parallel generation failed", platform=platform, error=str(e))
                    results[platform] = {"error": str(e)}
    else:
        # Sequential generation
        for platform in target_platforms:
            _, content = _generate_single_platform(
                platform, blueprint_data, research_data, options or {},
                quality_mode, references, ctx,
            )
            results[platform] = content

    output = {
        "stage": "produce",
        "data": results,
        "timestamp": time.time(),
        "platforms": list(results.keys()),
        "_meta": {"quality_mode": quality_mode},
        "_upstream": {
            "research": research.get("timestamp") if isinstance(research, dict) else None,
            "blueprint": blueprint.get("timestamp") if isinstance(blueprint, dict) else None,
        },
    }

    state.set("produce", output)
    return output


# ---------------------------------------------------------------------------
# Asset Generation
# ---------------------------------------------------------------------------

def generate_assets(
    blueprint: dict[str, Any],
    produce: dict[str, Any],
    platforms: list[str] | None = None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate image/asset suggestions for platforms."""
    config = ai_config(options)
    blueprint_data = blueprint.get("data", {})

    # Extract key visual themes from blueprint
    visual_elements = [
        e.get("content", "")
        for e in blueprint_data.get("elements", [])
        if e.get("type") in ("hook", "solution", "benefit")
    ]

    platforms = platforms or ["xiaohongshu", "twitter"]

    system_prompt = "你是视觉创意专家。基于内容生成配图建议。输出严格 JSON。"

    user_prompt = f"""基于以下内容，生成配图建议：

定位：{blueprint_data.get('positioning', {}).get('one_liner', '')}
视觉元素：{json.dumps(visual_elements[:3], ensure_ascii=False)}
目标平台：{', '.join(platforms)}

请输出各平台的配图建议 JSON：
{{
  "xiaohongshu": {{
    "aspect_ratio": "3:4",
    "hero_subject": "主视觉",
    "scene": "场景描述",
    "color_mood": "配色氛围",
    "text_overlay": "文字叠加建议"
  }},
  ...其他平台
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = dispatch_chat(messages, config)
        return parse_json_content(response)
    except Exception as e:
        logger.error(f"asset generation failed", error=str(e))
        return {}


# ---------------------------------------------------------------------------
# Main Pipeline Runner
# ---------------------------------------------------------------------------

def run_pipeline(
    result: dict[str, Any],
    options: dict[str, Any] | None = None,
    stop_after: str | None = None,
    state: PipelineState | None = None,
    search: bool = True,
    platforms: list[str] | None = None,
) -> dict[str, Any]:
    """Run the complete pipeline.

    Args:
        result: Source analysis result
        options: Generation options
        stop_after: Stop after this stage for interactive editing
        state: Optional existing state for resuming
        search: Whether to search reference ads during research
        platforms: Optional platform list to override research recommendations

    Returns:
        All stage outputs
    """
    if state is None:
        state = PipelineState(_source_id(result))

    outputs = {}

    # Stage 1: Research
    outputs["research"] = stage_research(result, state, options, search=search)
    if stop_after == "research":
        return outputs

    # Stage 2: Blueprint (interactive)
    outputs["blueprint"] = stage_blueprint(outputs["research"], state, result, options)
    if stop_after == "blueprint":
        return outputs

    # Stage 3: Produce
    outputs["produce"] = stage_produce(
        outputs["blueprint"],
        outputs["research"],
        state,
        options,
        parallel=True,
        platforms=platforms,
        result=result,
    )

    return outputs

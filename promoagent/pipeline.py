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
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .ai import ai_config, dispatch_chat, parse_json_content
from .examples import find_examples, format_examples_for_prompt
from .logger import logger
from .platforms import get_platform, to_prompt_dict, get_primary_platforms

# ---------------------------------------------------------------------------
# Pipeline State Management
# ---------------------------------------------------------------------------

class PipelineState:
    """Manages pipeline execution state with caching."""

    def __init__(self, source_id: str, cache_dir: Path | None = None):
        self.source_id = source_id
        self.cache_dir = cache_dir or Path.home() / ".cache" / "promoagent" / "pipeline"
        self.state_file = self.cache_dir / f"pipeline_{source_id}.json"
        self.stages: dict[str, Any] = {}
        self.metadata: dict[str, Any] = {
            "created": time.time(),
            "updated": time.time(),
            "version": "2.0",
        }
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
        return self.stages.get(stage)

    def set(self, stage: str, data: dict[str, Any]) -> None:
        self.stages[stage] = data
        self.save()

    def has(self, stage: str) -> bool:
        return stage in self.stages

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

    # Build concise source summary
    source_summary = {
        "name": project.get("name", ""),
        "description": project.get("description", ""),
        "topics": project.get("topics", []),
        "source_type": result.get("source", ""),
        "readme_opening": evidence.get("readmeOpening", "")[:400],
        "key_features": evidence.get("keyFeatures", [])[:5],
        "target_audience": evidence.get("targetAudience", []),
    }

    system_prompt = """你是推广研究专家。从来源材料中提取关键信息并制定推广策略。
只使用来源中明确的信息，标记缺失部分。
输出严格 JSON。"""

    references_section = f"\n{references_block}\n" if references_block else ""
    user_prompt = f"""分析以下项目/内容，提取关键信息并制定推广策略：

{json.dumps(source_summary, ensure_ascii=False, indent=2)}
{references_section}
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
    custom_elements: list[str] | None = None,
) -> dict[str, Any]:
    """Blueprint stage: Generate structured content elements.

    Creates editable Tweet Space with dynamic element selection.
    """
    if not force and state.has("blueprint"):
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

    element_types = custom_elements or default_elements

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
    references_block = ""
    refs = state.get("references")
    if refs and refs.get("examples"):
        references_block = format_examples_for_prompt(refs["examples"])

    clarifications_block = ""
    clar = state.get("clarifications")
    if clar and clar.get("answers"):
        lines = [f"- 问题: {q}\n  补充: {a}" for q, a in clar["answers"].items()]
        clarifications_block = "用户补充信息（请优先纳入这些事实，不要与来源冲突时忽略参考示例）：\n" + "\n".join(lines)

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

    output = {
        "stage": "blueprint",
        "data": parsed,
        "raw": response,
        "messages": messages,
        "timestamp": time.time(),
        "interactive": True,
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
    elements = data.get("elements", [])
    elements_by_id = {e["id"]: e for e in elements}

    # Track edit history
    if "edit_history" not in data:
        data["edit_history"] = []

    # Apply content edits
    for key, value in edits.items():
        if key.startswith("_"):
            continue  # Handle special commands below

        if key in elements_by_id:
            old_content = elements_by_id[key].get("content", "")
            elements_by_id[key]["content"] = value
            elements_by_id[key]["edited"] = True
            data["edit_history"].append({
                "type": "content",
                "element_id": key,
                "old": old_content,
                "new": value,
                "timestamp": time.time(),
            })

    # Handle special commands
    if "_selectVariant" in edits:
        for elem_id, variant_idx in edits["_selectVariant"].items():
            if elem_id in elements_by_id:
                element = elements_by_id[elem_id]
                variants = element.get("variants", [])
                if 0 <= variant_idx < len(variants):
                    old_content = element.get("content", "")
                    element["content"] = variants[variant_idx]
                    element["selected_variant"] = variant_idx
                    data["edit_history"].append({
                        "type": "variant_select",
                        "element_id": elem_id,
                        "variant_index": variant_idx,
                        "old": old_content,
                        "new": variants[variant_idx],
                    })

    if "_reorder" in edits:
        new_order = edits["_reorder"]
        valid_ids = set(e["id"] for e in elements)
        if all(eid in valid_ids for eid in new_order):
            data["elements"] = [elements_by_id[eid] for eid in new_order]
            data["edit_history"].append({
                "type": "reorder",
                "new_order": new_order,
            })

    if "_addElement" in edits:
        new_elem = edits["_addElement"]
        new_elem["id"] = new_elem.get("id", f"custom-{len(elements)}")
        new_elem["editable"] = True
        elements.append(new_elem)
        data["edit_history"].append({
            "type": "add",
            "element": new_elem,
        })

    if "_removeElement" in edits:
        elem_id = edits["_removeElement"]
        data["elements"] = [e for e in elements if e.get("id") != elem_id]
        data["edit_history"].append({
            "type": "remove",
            "element_id": elem_id,
        })

    if "_setStructure" in edits:
        structure_name = edits["_setStructure"]
        structures = data.get("structure", {}).get("alternative_structures", [])
        for struct in structures:
            if struct.get("name") == structure_name:
                order = struct.get("order", [])
                valid_ids = set(e["id"] for e in elements)
                if all(eid in valid_ids for eid in order):
                    data["elements"] = [elements_by_id[eid] for eid in order if eid in elements_by_id]
                    data["edit_history"].append({
                        "type": "structure_change",
                        "structure": structure_name,
                    })
                break

    blueprint["data"] = data
    return blueprint


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
) -> tuple[str, dict[str, Any]]:
    """Generate content for a single platform."""
    config = ai_config(options)

    # Get platform spec from centralized config
    spec_obj = get_platform(platform)
    if spec_obj is None:
        logger.warning(f"Unknown platform: {platform}, using default")
        spec_obj = get_platform("xiaohongshu")

    spec = to_prompt_dict(spec_obj)

    elements_text = "\n\n".join([
        f"[{e.get('label', e.get('type'))}]\n{e.get('content', '')}"
        for e in blueprint_data.get("elements", [])
    ])

    system_prompt = f"""你是{platform}内容专家。将 Blueprint 转换为该平台原生格式。
平台特点：{spec['style']}，{spec['tone']}
输出严格 JSON。"""

    user_prompt = f"""将以下内容转换为{platform}格式：

定位：{blueprint_data.get('positioning', {}).get('one_liner', '')}

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
- 基于 Blueprint 元素，不要添加未提及的信息
- hashtags 要符合平台习惯"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = dispatch_chat(messages, config)
        parsed = parse_json_content(response)
        return platform, parsed
    except Exception as e:
        logger.error(f"platform generation failed", platform=platform, error=str(e))
        return platform, {"error": str(e)}


def stage_produce(
    blueprint: dict[str, Any],
    research: dict[str, Any],
    state: PipelineState,
    options: dict[str, Any] | None = None,
    force: bool = False,
    platforms: list[str] | None = None,
    parallel: bool = True,
) -> dict[str, Any]:
    """Produce stage: Generate platform-native content.

    Supports parallel generation for multiple platforms.
    """
    if not force and state.has("produce"):
        logger.info("using cached produce stage")
        return state.get("produce")

    research_data = research.get("data", {})
    blueprint_data = blueprint.get("data", {})

    # Determine platforms to generate
    target_platforms = platforms or research_data.get("strategy", {}).get("recommended_platforms", ["xiaohongshu", "twitter"])

    logger.info("running produce stage", platforms=target_platforms, parallel=parallel)

    results = {}

    if parallel and len(target_platforms) > 1:
        # Parallel generation
        with ThreadPoolExecutor(max_workers=min(len(target_platforms), 3)) as executor:
            futures = {
                executor.submit(
                    _generate_single_platform,
                    platform,
                    blueprint_data,
                    research_data,
                    options or {},
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
            _, content = _generate_single_platform(platform, blueprint_data, research_data, options or {})
            results[platform] = content

    output = {
        "stage": "produce",
        "data": results,
        "timestamp": time.time(),
        "platforms": list(results.keys()),
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
) -> dict[str, Any]:
    """Run the complete pipeline.

    Args:
        result: Source analysis result
        options: Generation options
        stop_after: Stop after this stage for interactive editing
        state: Optional existing state for resuming
        search: Whether to search reference ads during research

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
    )

    return outputs

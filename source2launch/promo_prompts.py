from __future__ import annotations

import json
from typing import Any


# ---------------------------------------------------------------------------
# Minimal JSON schema — structure only, platforms decided by AI
# ---------------------------------------------------------------------------

PROMO_JSON_SCHEMA = """{
  "positioning": "一句话定位（结果导向，具体可验证）",
  "targetUsers": ["目标用户"],
  "strongestAngles": ["最适合推广的切入点"],
  "promotionStrategy": {
    "coreAngle": "基于来源证据的主推广角度",
    "contentGraph": [{"node": "problem|evidence|action", "claim": "内容", "source": "来源"}],
    "qualityRubric": {
      "fidelity": {"checks": ["..."], "risks": ["..."], "improvements": ["..."]},
      "engagement": {"checks": ["..."], "risks": ["..."], "improvements": ["..."]},
      "alignment": {"checks": ["..."], "risks": ["..."], "improvements": ["..."]}
    }
  },
  "promotions": {
    "<platform_key>": {
      "markdown": "完整可发布的 Markdown 正文",
      "publishNotes": "发布建议"
    }
  },
  "launchSequence": [{"order": 1, "channel": "渠道", "reason": "原因"}]
}"""

# platform_key 示例：xiaohongshu / zhihu / wechatMoments / wechatArticle /
# twitter / showHn / productHunt / linkedin / reddit / weibo
# 只生成适合这份内容的平台，不需要覆盖全部


# ---------------------------------------------------------------------------
# Preset expansion — no hardcoded content, treats preset names as intent hints
# ---------------------------------------------------------------------------

def expand_presets(names: list[str]) -> str:
    """Convert preset names into intent hints for the AI.

    No hardcoded instructions — just passes the names as context so the AI
    can interpret them based on its own understanding.
    """
    if not names:
        return ""
    hint = "、".join(n.strip() for n in names if n.strip())
    return (
        f"写作风格偏好（请根据自己的理解应用）：{hint}\n"
        "以上是用户希望的写作风格参考，请在保证内容基于来源证据的前提下，适当融入这些风格。"
    )


# ---------------------------------------------------------------------------
# System prompt — principles only, no hardcoded platform rules
# ---------------------------------------------------------------------------

def build_promo_system_prompt() -> str:
    return "\n".join([
        "你是推广内容主编，把任何来源（开源项目、论文、餐厅、产品、活动、服务…）转成各平台推广文案。",
        "你已经熟悉各平台的内容风格、格式要求和用户习惯，请自主运用这些知识。",
        "",
        "## 核心原则",
        "- 只使用来源证据中可核实的事实。无法验证的内容写 caveat，不要补编。",
        "- 根据内容特点和受众，自主判断哪些平台最适合，选择 2-5 个平台生成内容。",
        "- 每个平台的内容要有明显差异：结构、语气、长度都要符合该平台的原生风格。",
        "- 三轴审核（fidelity/engagement/alignment）必须填写，作为人工审核的参考。",
        "",
        "只输出严格 JSON，不要 Markdown 代码块，不要 JSON 之外的内容。",
    ])


# ---------------------------------------------------------------------------
# User prompt
# ---------------------------------------------------------------------------

def build_promo_user_prompt(
    payload: dict[str, Any],
    *,
    platform: str = "all",
    brief_section: str = "",
    examples: list[str] | None = None,
) -> str:
    platform_hint = (
        "请为这份内容选择最合适的 2-5 个平台，生成完整的 markdown 内容。"
        if platform == "all"
        else f"重点生成 {platform} 的内容，同时为 1-2 个其他合适的平台生成简短版本。"
    )

    parts = [
        "请基于以下来源证据，生成各平台可直接使用的推广内容。",
        "",
        "## 来源证据（必须引用，不可违背）",
        build_evidence_brief(payload),
        "",
    ]

    if brief_section:
        parts.extend([brief_section, ""])

    # Few-shot examples from Stage 1
    if examples:
        from .examples import format_examples_for_prompt
        example_section = format_examples_for_prompt(examples, platform)
        if example_section:
            parts.extend([example_section, ""])

    parts.extend([
        "## 写作流程",
        "",
        "1. **提取核心角度**：从来源证据中找最独特的卖点，写入 promotionStrategy.coreAngle",
        "2. **选择合适平台**：根据内容性质和目标受众，判断哪些平台最适合",
        "3. **按平台改写**：充分利用你对各平台风格的了解，让每个平台的内容都有原生感",
        "4. **三轴审核**：检查事实准确性（fidelity）、吸引力（engagement）、平台适配（alignment）",
        "",
        platform_hint,
        "",
        "JSON 输出结构：",
        PROMO_JSON_SCHEMA,
        "",
        "完整来源数据：",
        json.dumps(payload, ensure_ascii=False, indent=2),
    ])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Evidence brief
# ---------------------------------------------------------------------------

def build_evidence_brief(payload: dict[str, Any]) -> str:
    project = payload.get("project", {})
    evidence = payload.get("evidence", {})
    ctx = evidence.get("additionalContext", {})

    lines = [f"- 推广主体：{project.get('name', '（未命名）')}"]

    desc = project.get("description") or ""
    if desc:
        lines.append(f"- 核心描述：{desc[:400]}")

    cta = project.get("cta") or project.get("installCommand")
    if cta:
        lines.append(f"- 行动号召（必须原样使用）：{cta}")

    if project.get("repositoryUrl"):
        lines.append(f"- 代码仓库：{project['repositoryUrl']}")
    if project.get("homepage"):
        lines.append(f"- 主页/网站：{project['homepage']}")

    if project.get("topics"):
        lines.append(f"- 关键词：{', '.join(project['topics'][:8])}")

    if project.get("stars") is not None:
        lines.append(f"- GitHub Stars：{project['stars']}")

    opening = evidence.get("opening") or evidence.get("readmeOpening") or ""
    if opening and opening != desc:
        lines.append(f"- 内容概述：{opening[:300]}")

    headings = evidence.get("headings") or []
    h2 = [h["text"] for h in headings if isinstance(h, dict) and h.get("level") == 2][:8]
    if h2:
        lines.append(f"- 主要章节/功能：{' / '.join(h2)}")

    key_actions = evidence.get("keyActions") or evidence.get("installCommands") or []
    extra = [a for a in key_actions if a != cta][:3]
    if extra:
        lines.append(f"- 使用方式示例：{' | '.join(extra)}")

    proofs = evidence.get("proofPoints") or []
    if proofs:
        lines.append("- 质量证明：")
        for p in proofs[:3]:
            lines.append(f"  - {p}")

    if ctx:
        ctx_items = []
        for k, v in ctx.items():
            if v and k != "interactiveQA":
                ctx_items.append(f"{k}：{v}")
        if ctx_items:
            lines.append(f"- 补充信息：{' / '.join(ctx_items)}")

    # Interactive Q&A from user
    qa = ctx.get("interactiveQA")
    if qa:
        lines.extend(["- 用户补充的信息：", qa])

    clips = evidence.get("documentClips") or []
    if clips:
        lines.append("- 文档摘要：")
        for clip in clips[:2]:
            text = clip.get("text", "") if isinstance(clip, dict) else str(clip)
            lines.append(f"  > {text[:150].replace(chr(10), ' ')}")

    risks = evidence.get("launchRisks") or []
    if risks:
        lines.append("- 注意事项（可用于 limitations）：")
        for risk in risks[:3]:
            msg = risk.get("message") if isinstance(risk, dict) else str(risk)
            lines.append(f"  - {msg}")

    return "\n".join(lines)

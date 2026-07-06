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
        "## 好内容 vs 平庸内容",
        "平庸内容：描述产品特征，告诉读者「这个东西很好」。",
        "好内容：让目标读者在特定场景下产生「这说的就是我」的感觉，知道下一步该做什么。",
        "",
        "## 写作前必须想清楚",
        "- 目标读者是谁？他们在什么场景下看到这条内容？看完之后你希望他们做什么？",
        "- 来源证据里最有力的一个事实是什么？（价格、效果、独特性、反差感…）",
        "- 第一句话如何让目标读者停下来？（具体场景 > 数字反差 > 情绪共鸣 > 悬念问题）",
        "",
        "## 核心原则",
        "- 只使用来源证据中可核实的事实。无法验证的内容写 caveat，不要补编。",
        "- 根据内容特点和受众，自主判断哪些平台最适合，选择 2-5 个平台生成内容。",
        "- 每个平台的内容要有明显差异：不只是改改措辞，结构和切入角度都要不同。",
        "- 三轴审核（fidelity / engagement / alignment）必须填写。",
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

    brief = build_evidence_brief(payload)
    source_type = payload.get("inputType") or payload.get("source") or ""
    is_sparse = source_type == "text" or len(brief) < 200

    parts = [
        "请基于以下来源证据，生成各平台可直接使用的推广内容。",
        "",
        "## 来源证据（必须引用，不可违背）",
        brief,
        "",
    ]

    if is_sparse:
        parts.extend([
            "## 证据稀薄时的处理方式",
            "当前来源信息较少，但这不意味着无法写出好内容。",
            "请从已有信息中挖掘隐含价值：",
            "- 价格/时间/地点信息背后的「读者意义」是什么？",
            "- 产品/服务名称里有没有暗示的受众、场景或差异化？",
            "- 能从描述词语中推断出哪些体验性细节？",
            "对于无法从证据推断的内容，在 reviewGate 里标注「需要补充」，不要编造。",
            "",
        ])

    if brief_section:
        parts.extend([brief_section, ""])

    # Few-shot examples from Stage 1
    if examples:
        example_section = format_examples_for_prompt(examples, platform)
        if example_section:
            parts.extend([example_section, ""])

    parts.extend([
        "## 写作流程（按顺序执行）",
        "",
        "**Step 1 — 挖掘真正的推广角度**",
        "不要直接描述产品特征，而是找到它背后的「读者价值」：",
        "- 它解决了一个什么具体的烦恼？还是满足了一个什么具体的欲望？",
        "- 目标读者在什么场景下最需要这个？",
        "- 来源证据里有没有一个数字、细节或反差，能让人一眼记住？",
        "把找到的最强角度写入 promotionStrategy.coreAngle。",
        "",
        "**Step 2 — 策划内容图谱**",
        "用证据中的具体材料（命令/价格/地址/图片/数据/评价）填充 contentGraph，",
        "标注每个 claim 来自哪里，确保每个平台都有可引用的原始证据。",
        "",
        "**Step 3 — 按平台写，真正有差异**",
        "不同平台的差异不只是语气——核心切入角度也应该不同：",
        "- 同一家餐厅：小红书切「隐藏宝藏发现感」，知乎切「性价比分析」，微信切「这个周末去哪吃」",
        "- 同一个工具：Show HN 切「解决了什么技术痛点」，小红书切「这个命令帮我省了多少时间」",
        "",
        "**Step 4 — 三轴审核**",
        "- Fidelity：每个 claim 都能在来源证据中找到依据？",
        "- Engagement：第一句话是否具体？读者能否在 3 秒内判断「这和我有关」？",
        "- Alignment：语气、节奏、格式是否真的像这个平台的原生内容？",
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
# Payload builder  (moved here from ai.py — data prep belongs in promo layer)
# ---------------------------------------------------------------------------

def build_promo_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Extract the fields that AI prompts need from a full analyze_target() result."""
    return {
        "project":   result.get("project", {}),
        "evidence":  result.get("evidence", {}),
        "target":    result.get("target"),
        "source":    result.get("source"),
        "inputType": result.get("inputType"),
    }


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


# ---------------------------------------------------------------------------
# Stateless refinement messages  (used by mcp_server.s2l_refine)
# ---------------------------------------------------------------------------

def build_refine_messages(
    content: str,
    feedback: str,
    platform: str = "",
) -> list[dict[str, str]]:
    """Build a one-shot message list for stateless content refinement.

    Unlike ``ai.refine_content()`` (which requires saved conversation history),
    this is suitable for stateless callers such as the MCP server tools.
    """
    platform_hint = f"（目标平台：{platform}）" if platform else ""
    return [
        {"role": "system", "content": build_promo_system_prompt()},
        {
            "role": "user",
            "content": (
                f"以下是已生成的推广文案{platform_hint}，请根据反馈进行改进。\n\n"
                f"**原文案：**\n{content}\n\n"
                f"**改进要求：**\n{feedback}\n\n"
                "请直接输出改进后的完整文案，无需解释修改原因。"
            ),
        },
    ]


# ---------------------------------------------------------------------------
# Few-shot example formatter  (moved here from examples.py to break the
# promo_prompts → examples → ai → promo_prompts import cycle)
# ---------------------------------------------------------------------------

def format_examples_for_prompt(examples: list[str], platform: str = "all") -> str:
    """Format Stage-1 reference examples as a few-shot section for the user prompt."""
    if not examples:
        return ""
    platform_label = platform if platform else "通用"
    lines = [
        f"## 参考示例（{platform_label} 优质内容风格参考）",
        "",
        "请学习以下示例的写作风格、结构和语感，但**不要复制内容**。",
        "你的输出必须完全基于来源证据，与示例内容无关。",
        "",
    ]
    for i, example in enumerate(examples, 1):
        lines += [f"### 示例 {i}", "", example.strip(), ""]
    lines += ["---", ""]
    return "\n".join(lines)

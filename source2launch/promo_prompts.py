from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------------------
# Prompt presets — each entry is the actual instruction injected into the prompt.
# ---------------------------------------------------------------------------
PROMPT_PRESETS: dict[str, str] = {
    "grounded": (
        "Every claim must be traceable to a specific source: README text, paper abstract, "
        "figure caption, result table, code comment, CLI command, or screenshot. "
        "If a claim cannot be verified from the provided evidence, write a caveat instead of inventing support."
    ),
    "author": (
        "Write in the voice of the project maintainer or paper author — someone sharing a useful artifact, "
        "not a marketing team. Prefer concrete descriptions ('reads a local repo, outputs Markdown') "
        "over superlatives ('powerful', 'seamless', 'revolutionary'). "
        "First-person is fine where the evidence supports it."
    ),
    "realworld": (
        "Before finalising any platform copy, internally compare it against real technical promotion patterns: "
        "does the first line name the project, problem, command, or result immediately? "
        "Is there exactly one concrete artifact (link, command, figure, table) near the top? "
        "Is there one clear reason for the target reader to act? "
        "If not, revise before outputting."
    ),
    "autopr": (
        "Follow the AutoPR promotion workflow:\n"
        "1. Extract source material — title, task definition, method, evidence clips, code or demo path, visual assets, caveats, audience signals.\n"
        "2. Synthesise a single core angle grounded in that evidence and write it into promotionStrategy.coreAngle.\n"
        "3. Adapt the angle to each platform's format, length, tone, and visual conventions.\n"
        "4. Review fidelity (source faithfulness), engagement (concrete hook, clear CTA), "
        "and alignment (platform-native tone and format) before outputting."
    ),
    "scholardag": (
        "Build a content graph (Scholar-DAG) before writing:\n"
        "- Problem node: what gap or pain does this address?\n"
        "- Method node: what is the core approach or technique?\n"
        "- Evidence nodes: which figures, tables, benchmarks, or demo outputs prove the claim?\n"
        "- Visual proof nodes: which screenshots, paper figures, or generated cards should appear?\n"
        "- Caveat nodes: what are honest limitations or missing evidence?\n"
        "- Audience nodes: who benefits and on which platform?\n"
        "- Action node: what should the reader do next?\n"
        "All platform variants must draw from this shared graph; do not let individual platform copy drift into different claims."
    ),
    "human": (
        "Each post should read as though one person is sharing one concrete observation. "
        "Limit each post to a single angle. "
        "Avoid opening with a feature inventory or platform list. "
        "Use casual but precise language; skip empty filler phrases like 'In today's fast-paced world'."
    ),
    "tweet": (
        "For Twitter / X output:\n"
        "- One angle per tweet or thread — do not pack every feature into one post.\n"
        "- Place a concrete artifact (command, URL, figure reference, or key result) "
        "within the first 20 English or 40 Chinese characters.\n"
        "- Target 140–220 Chinese or 200–280 English characters per post.\n"
        "- At most two hashtags; prefer the project name and one topic tag.\n"
        "- If writing a thread, use hook → context → mechanism → evidence → caveat → action structure."
    ),
    "paper": (
        "For paper-based sources:\n"
        "- Surface the problem the paper addresses, the method or model used, "
        "key evidence (benchmark tables, figures, ablations), why it matters to the reader, "
        "and honest limitations.\n"
        "- Do not reduce the paper to a rewritten abstract — show at least one figure, table, or result number.\n"
        "- Distinguish claims the paper proves from claims it suggests or leaves to future work."
    ),
    "launch": (
        "For open-source code launches:\n"
        "- Show what the tool reads as input and what it produces as output.\n"
        "- Include the shortest working install or run command from the README.\n"
        "- Name the target user ('useful for researchers who…', 'designed for maintainers who…').\n"
        "- Include one concrete proof: screenshot, README excerpt, terminal output, or live demo link.\n"
        "- Mention the current maturity level honestly (alpha, beta, production-ready)."
    ),
    "launchkit": (
        "Generate structured launch material:\n"
        "- Product Hunt: tagline (≤60 chars), description, maker first comment (personal story + limitation + feedback ask), gallery plan (what each image shows).\n"
        "- Show HN: plain title ('Show HN: Name — one-sentence description'), what it does, how to try it right now, key implementation choice, two honest limitations. No vote request.\n"
        "- LinkedIn: build-note format — problem encountered, what was built, one concrete artifact, who should try it, modest discussion prompt."
    ),
    "technical": (
        "Keep technical boundaries explicit:\n"
        "- Name the input format, output format, CLI command or API route, and configuration requirements.\n"
        "- Show the workflow as a sequence of concrete steps rather than abstract benefits.\n"
        "- Do not hide implementation choices behind marketing language."
    ),
    "zhihu": (
        "Structure Zhihu output as a credible technical answer:\n"
        "- Conclusion first (one sentence direct answer), then background, method or workflow, "
        "evidence with source citations, limitations, and reader fit.\n"
        "- Tone: analytical and restrained — reads like a useful answer to a question, not a sales page.\n"
        "- Cite source material explicitly: paper abstract crop, method figure, result table, README excerpt, command, or demo screenshot."
    ),
    "xhs": (
        "Structure Xiaohongshu output as a carousel note:\n"
        "- Generate 2–3 title options (≤20 Chinese characters each) and cover text before writing the body.\n"
        "- Body: one takeaway per card, one visual suggestion per card — treat it as a slide deck.\n"
        "- Tags: 3–6 concise relevant tags; do not use generic filler tags.\n"
        "- Do not invent user counts, star numbers, award wins, or benchmark results."
    ),
    "wechat": (
        "Structure WeChat output with full article packaging:\n"
        "- Title, one-line summary, cover text, section outline, and body.\n"
        "- Preferred sections: introduction, problem, method or workflow, evidence or results, limitations, who should read.\n"
        "- Place paper screenshots or repository evidence near the claim they support.\n"
        "- Also generate a compact Moments post (≤140 Chinese characters): one takeaway + one reason to open the source."
    ),
    "visual": (
        "For every major claim, identify the corresponding source clip:\n"
        "- Paper figure (name the figure number or caption), result table, README screenshot, terminal output, or architecture diagram.\n"
        "- Output a visualNarrative plan in the JSON before writing platform copy.\n"
        "- Do not suggest AI-generated images for claims that should use real evidence screenshots.\n"
        "- Carousel order suggestion: hook/cover, source proof, simplified takeaway, method or workflow, caveat, call to read or try."
    ),
    "paper2web": (
        "Check presentation completeness for paper sources:\n"
        "- Visual anchor: is there at least one figure, table, or screenshot that a reader can scan before reading the text?\n"
        "- Reader path: does the output tell the reader who should read, why, and what to do next?\n"
        "- Source proof: is every major claim tied to a specific paper section, figure, or appendix?\n"
        "Revise if any of these are missing."
    ),
    "thread": (
        "Structure threaded output (Twitter thread, Zhihu series, or carousel) as:\n"
        "1. Hook — surprising result, concrete problem, or direct question.\n"
        "2. Context — why this matters and who it affects.\n"
        "3. Mechanism — how it works (method, algorithm, or workflow).\n"
        "4. Evidence — one or two concrete artifacts (command, figure, benchmark, screenshot).\n"
        "5. Caveat — one honest limitation or open question.\n"
        "6. Action — what the reader should do next (try, read, follow, or contribute)."
    ),
}

def expand_presets(names: list[str]) -> str:
    """Return the combined instruction text for the given preset names.

    Unknown names are silently skipped so callers don't need to guard.
    """
    parts: list[str] = []
    for name in names:
        instruction = PROMPT_PRESETS.get(name.strip().lower())
        if instruction:
            parts.append(f"### Preset: {name}\n{instruction}")
    return "\n\n".join(parts)


PROMO_JSON_SCHEMA = "\n".join([
    "{",
    '  "positioning": "一句话定位（结果导向，不是功能列表）",',
    '  "targetUsers": ["目标用户1", "目标用户2"],',
    '  "strongestAngles": ["最适合推广的切入点1", "切入点2"],',
    '  "promotionStrategy": {',
    '    "coreAngle": "基于来源证据的主推广角度",',
    '    "contentGraph": [{"node": "problem|method|evidence|visual|caveat|action", "claim": "内容节点", "source": "README/PDF/figure/table/demo/command"}],',
    '    "audienceSegments": [{"audience": "目标读者", "platform": "适合平台", "reason": "为什么"}],',
    '    "platformAdaptation": [{"platform": "xhs|zhihu|wechat|showHn|twitter|productHunt", "format": "格式", "tone": "语气", "visual": "配图/截图建议", "avoid": ["不要写什么"]}],',
    '    "visualNarrative": [{"asset": "来源截图/论文图/生成图", "supportsClaim": "支撑的观点"}],',
    '    "qualityRubric": {',
    '      "fidelity": {"checks": ["事实准确性/核心贡献/术语一致性检查"], "risks": ["可能失真的点"], "improvements": ["发布前如何补证据"]},',
    '      "engagement": {"checks": ["开头钩子/叙事清晰/CTA/受众吸引力检查"], "risks": ["可能太泛或太像模板的点"], "improvements": ["如何让读者更愿意点开"]},',
    '      "alignment": {"checks": ["平台语气/节奏/标签/图文配合检查"], "risks": ["平台不适配的点"], "improvements": ["如何按平台改写或换图"]}',
    "    },",
    '    "reviewGate": {"fidelityQuestions": ["事实核查问题"], "engagementQuestions": ["吸引力检查"], "platformQuestions": ["平台适配检查"]}',
    "  },",
    '  "promotions": {',
    '    "xiaohongshu": {"titles": ["标题1≤20字", "标题2", "标题3"], "markdown": "完整 Markdown 文件正文", "tags": ["#标签1"], "publishNotes": "发布建议"},',
    '    "wechatMoments": {"markdown": "完整 Markdown（含2-3种朋友圈风格）"},',
    '    "zhihu": {"suggestedQuestions": ["适合回答的知乎问题1"], "markdown": "完整 Markdown 回答/专栏正文"},',
    '    "showHn": {"title": "Show HN: Name - plain English description", "markdown": "完整 Markdown"},',
    '    "twitter": {"markdown": "完整 Markdown thread"},',
    '    "reddit": {"markdown": "Reddit/V2EX 标题+正文"},',
    '    "productHunt": {"markdown": "tagline + maker first comment"}',
    "  },",
    '  "launchSequence": [{"order": 1, "channel": "渠道", "reason": "为什么先在这个渠道发", "ready": true}]',
    "}",
])


def build_promo_system_prompt() -> str:
    return "\n".join([
        "你是推广内容主编，把任何来源（开源项目、论文、餐厅、产品、活动、服务…）转成各平台推广文案。",
        "你会收到来源描述、核心卖点、行动号召、图片引用、证明材料和风险提示等。请基于这些真实证据写作，不要补编。",
        "",
        "## 可信度铁律",
        "- 禁止编造数据、用户数量、媒体报道、他人评价、奖项或任何未经证实的信息。",
        "- 只使用来源证据中可核实的事实（描述、图片、命令、网址、价格、地址等）。",
        "- 若来源证据不足，写 caveat 或在 reviewGate 里标注，不要补编。",
        "- 不要使用「必备」「神器」「颠覆」「最强」「完美」「爆款」等空泛词。",
        "",
        "## 各平台写作标准",
        "**小红书**：2-3 个标题备选（≤20字）+ 转盘结构正文。每张卡片一个具体结论 + 一个来源证据。口语化，有画面感，避免广告腔。",
        "**知乎**：结论先行 → 背景/痛点 → 方法/特色 → 具体证据 → 局限 → 适合谁。像一篇有用的回答，不像推广稿。",
        "**微信**：公众号结构（标题/摘要/章节/正文）+ 朋友圈短文（≤140字，一个亮点 + 一个行动）。",
        "**Show HN**：Plain English 标题 → 做了什么 → 怎么试 → 关键细节 → 2 条真实局限。不要求投票。",
        "**Product Hunt**：Tagline（≤60字）+ maker comment（故事 + 局限 + 反馈请求）。",
        "**Twitter/X**：一个角度 + 一个具体证据 + ≤2 个标签，140-220 中文字或 200-280 英文字。",
        "",
        "## 三轴审核",
        "- Fidelity：所有事实都能从来源证据中找到依据。",
        "- Engagement：开头具体有画面感，CTA 清晰，读者知道下一步做什么。",
        "- Alignment：语气、节奏、格式和标签与平台调性匹配。",
        "- 每次输出都要填写 promotionStrategy.qualityRubric。",
        "",
        "只输出严格 JSON，不要 Markdown 代码块，不要解释 JSON 之外的内容。",
    ])


def build_promo_user_prompt(payload: dict[str, Any], *, platform: str = "all", brief_section: str = "") -> str:
    platform_hint = (
        "请生成所有平台的完整 markdown 字段。launchSequence 按准备度给出发布顺序。"
        if platform == "all"
        else f"重点打磨 {platform} 对应平台，其他平台给出简短可用 markdown。"
    )
    parts = [
        "请基于以下来源证据，生成各平台可直接使用的推广 Markdown 内容。",
        "",
        "## 来源证据（必须引用，不可违背）",
        build_evidence_brief(payload),
        "",
    ]
    if brief_section:
        parts.extend([brief_section, ""])
    parts.extend([
        "## 写作要求",
        "",
        "**第一步：提取核心推广角度**",
        "- 从来源证据中找出最独特的卖点：解决了什么具体问题/满足了什么需求？有什么可验证的证明？",
        "- 写入 promotionStrategy.coreAngle，作为所有平台内容的统一基础。",
        "",
        "**第二步：按平台改写**",
        "- 每个平台结构不同，不要跨平台复用同一段话。",
        "- 第一句话必须具体有画面感：不要写「介绍一个产品/项目」，而要直接展示核心价值或具体场景。",
        "- CTA 清晰指向真实下一步：联系方式、购买链接、安装命令、地址等，不要写泛泛的「欢迎关注」。",
        "",
        "**第三步：三轴审核**",
        "- 每条内容都自问：所有事实能从来源证据中找到？开头够具体吗？语气和格式匹配平台吗？",
        "- 将审核结果写入 promotionStrategy.qualityRubric。",
        "",
        "**禁止**：编造数据、使用「必备/神器/高质量/颠覆」等空泛词、所有平台用同一段话。",
        "",
        "JSON 输出结构：",
        PROMO_JSON_SCHEMA,
        "",
        platform_hint,
        "",
        "完整来源数据：",
        json.dumps(payload, ensure_ascii=False, indent=2),
    ])
    return "\n".join(parts)


def build_evidence_brief(payload: dict[str, Any]) -> str:
    """Build a concise evidence brief for the AI prompt.

    Works for any subject: repos, restaurants, products, events, papers, etc.
    Reads from both legacy (README-specific) and new universal evidence fields.
    """
    project = payload.get("project", {})
    evidence = payload.get("evidence", {})
    ctx = evidence.get("additionalContext", {})

    lines = [f"- 推广主体：{project.get('name', '（未命名）')}"]

    # Description
    desc = project.get("description") or ""
    if desc:
        lines.append(f"- 核心描述：{desc[:400]}")

    # CTA / contact / install command (unified)
    cta = (
        project.get("cta")
        or project.get("installCommand")
    )
    if cta:
        lines.append(f"- 行动号召（必须原样使用）：{cta}")

    # Links
    if project.get("repositoryUrl"):
        lines.append(f"- 代码仓库：{project['repositoryUrl']}")
    if project.get("homepage"):
        lines.append(f"- 主页/网站：{project['homepage']}")

    # Keywords / tags
    if project.get("topics"):
        lines.append(f"- 关键词：{', '.join(project['topics'][:8])}")

    # Stars (tech projects)
    if project.get("stars") is not None:
        lines.append(f"- GitHub Stars：{project['stars']}")

    # Opening paragraph / content overview
    opening = evidence.get("opening") or evidence.get("readmeOpening") or ""
    if opening and opening != desc:
        lines.append(f"- 内容概述：{opening[:300]}")

    # Key headings / sections
    headings = evidence.get("headings") or []
    h2 = [h["text"] for h in headings if isinstance(h, dict) and h.get("level") == 2][:8]
    if h2:
        lines.append(f"- 主要章节/功能：{' / '.join(h2)}")

    # Key actions / commands
    key_actions = evidence.get("keyActions") or evidence.get("installCommands") or []
    extra = [a for a in key_actions if a != cta][:3]
    if extra:
        lines.append(f"- 使用方式示例：{' | '.join(extra)}")

    # Proof points (testimonials, awards, stats, etc.)
    proofs = evidence.get("proofPoints") or []
    if proofs:
        lines.append("- 质量证明：")
        for p in proofs[:3]:
            lines.append(f"  - {p}")

    # Additional context (location, price, hours, audience, etc.)
    if ctx:
        ctx_items = []
        if ctx.get("price"):
            ctx_items.append(f"价格：{ctx['price']}")
        if ctx.get("location"):
            ctx_items.append(f"地址：{ctx['location']}")
        if ctx.get("audience") or ctx.get("target_audience"):
            ctx_items.append(f"目标受众：{ctx.get('audience') or ctx.get('target_audience')}")
        for k, v in ctx.items():
            if k not in ("price", "location", "audience", "target_audience") and v:
                ctx_items.append(f"{k}：{v}")
        if ctx_items:
            lines.append(f"- 补充信息：{' / '.join(ctx_items)}")

    # Document clips (PDF/doc sources)
    clips = evidence.get("documentClips") or []
    if clips:
        lines.append("- 文档摘要：")
        for clip in clips[:2]:
            text = clip.get("text", "") if isinstance(clip, dict) else str(clip)
            lines.append(f"  > {text[:150].replace(chr(10), ' ')}")

    # Launch risks
    risks = evidence.get("launchRisks") or []
    if risks:
        lines.append("- 注意事项（可用于 limitations）：")
        for risk in risks[:3]:
            msg = risk.get("message") if isinstance(risk, dict) else str(risk)
            lines.append(f"  - {msg}")

    return "\n".join(lines)

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
        "你是项目/论文发布内容策划 + 多平台内容主编，专门把开源仓库、论文 PDF、README 和来源证据转成可人工审核的推广 Markdown 文件。",
        "你会收到项目描述、安装命令、README 章节、文档片段和 launchRisks 等。请独立阅读 evidence，基于真实证据写作。",
        "",
        "## 可信度铁律",
        "- 禁止编造 star 数量、用户数量、媒体报道、他人评价、benchmark 或论文结果。",
        "- 只使用 README、PDF、截图、命令、代码或用户提供材料中可核实的事实。",
        "- 若来源证据不足，请写 caveat 或审核问题，不要补编。",
        "- 不要使用「必备」「神器」「高质量」「提升效率」「打造完整」「颠覆」「最强」等空泛词。",
        "",
        "## 各平台写作标准",
        "**小红书**：2-3 个标题备选（≤20字）+ 转盘结构正文。每张卡片一个结论 + 一个来源证据。轻松口语化，避免广告腔。",
        "**知乎**：结论先行 → 背景 → 方法/工作流 → 来源证据 → 局限 → 适合谁读。像技术答案，不像推广稿。",
        "**微信**：公众号文章结构（标题/摘要/章节/正文）+ 朋友圈短文（≤140字，一个结论 + 一个行动）。",
        "**Show HN**：Plain English 标题 → 做了什么 → 怎么试用 → 关键实现细节 → 2 条真实局限。不要求投票。",
        "**Product Hunt**：Tagline（≤60字）+ 首条 maker comment（个人故事 + 局限 + 反馈请求）。",
        "**Twitter/X**：一个角度 + 一个具体证据（命令/图/数据）+ ≤2 个标签，140-220 中文字或 200-280 英文字。",
        "",
        "## AutoPR-style 三轴审核",
        "- Fidelity：事实准确性、核心贡献覆盖、术语/命令是否与来源一致。",
        "- Engagement：开头是否具体、叙事是否清楚、CTA 是否指向试命令/看仓库/读论文。",
        "- Alignment：平台语气、节奏、标签、图文配合是否匹配。",
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
        "请基于以下来源数据，生成各平台可直接使用的推广 Markdown 内容。",
        "",
        "## 项目来源证据（必须引用，不可违背）",
        build_evidence_brief(payload),
        "",
    ]
    if brief_section:
        parts.extend([brief_section, ""])
    parts.extend([
        "## 写作要求",
        "",
        "**第一步：提取核心推广角度**",
        "- 从来源证据中找出最独特的卖点：解决了什么具体问题？用什么方法？有什么可验证的证明？",
        "- 写入 promotionStrategy.coreAngle，作为所有平台内容的统一基础。",
        "",
        "**第二步：按平台改写**",
        "- 每个平台结构不同，不要跨平台复用同一段话。",
        "- 第一句话必须具体：不要写「介绍一个工具」，而是写「用一条命令把 GitHub 仓库变成小红书文案」。",
        "- CTA 指向真实下一步：`pip install`、试命令、看仓库、读论文，不要写泛泛的「欢迎关注」。",
        "",
        "**第三步：三轴审核**",
        "- 每条内容都要自问：事实能否从 README/论文/命令中找到来源？开头是否具体到一个场景？语气是否匹配这个平台？",
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
    project = payload.get("project", {})
    evidence = payload.get("evidence", {})
    lines = [f"- 项目名：{project.get('name', 'unknown')}"]

    if project.get("description"):
        lines.append(f"- 一句话描述：{project['description']}")

    if project.get("installCommand"):
        lines.append(f"- 安装/运行命令（必须原样使用）：`{project['installCommand']}`")

    if project.get("repositoryUrl"):
        lines.append(f"- 仓库地址：{project['repositoryUrl']}")

    if project.get("homepage"):
        lines.append(f"- 主页：{project['homepage']}")

    if project.get("topics"):
        lines.append(f"- 关键词/Topics：{', '.join(project['topics'])}")

    if project.get("stars") is not None:
        lines.append(f"- Stars：{project['stars']}")

    opening = evidence.get("readmeOpening", "")
    if opening:
        lines.append(f"- README 开头（项目定位）：{opening[:300]}")

    # Key headings — shows what the README covers
    headings = evidence.get("headings") or []
    h2 = [h["text"] for h in headings if h.get("level") == 2][:8]
    if h2:
        lines.append(f"- README 章节：{' / '.join(h2)}")

    # Install commands — concrete proof
    cmds = evidence.get("installCommands") or []
    extra_cmds = [c for c in cmds if c != project.get("installCommand")][:3]
    if extra_cmds:
        lines.append(f"- 其他命令示例：{' | '.join(f'`{c}`' for c in extra_cmds)}")

    # Document clips (for PDF/doc sources)
    clips = evidence.get("documentClips") or []
    if clips:
        lines.append("- 文档摘要片段：")
        for clip in clips[:2]:
            text = clip.get("text", "") if isinstance(clip, dict) else str(clip)
            lines.append(f"  > {text[:150].replace(chr(10), ' ')}")

    # Launch risks (honest limitations / Show HN material)
    risks = evidence.get("launchRisks") or []
    if risks:
        lines.append("- 发布前注意（可用于 Show HN limitations）：")
        for risk in risks[:3]:
            msg = risk.get("message") if isinstance(risk, dict) else str(risk)
            lines.append(f"  - {msg}")

    return "\n".join(lines)

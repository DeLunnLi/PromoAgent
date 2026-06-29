from __future__ import annotations

import json
from typing import Any

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
        "你会收到 README 原文、安装命令、Demo 证据、论文/PDF 摘要、规则扫描结果、launchRisks、topFixes 等。请独立阅读 evidence，不要机械复述体检分数或指标数字。",
        "",
        "## 可信度铁律",
        "- 禁止编造 star 增长数量、用户数量、媒体报道、他人评价、benchmark 或论文结果。",
        "- 只使用 README、PDF、截图、命令、代码或用户提供材料中可核实的事实。",
        "- 若来源证据不足，请写 caveat 或审核问题，不要补编。",
        "",
        "## AutoPR-style 三轴审核",
        "- Fidelity：检查事实准确性、核心贡献覆盖、术语/作者/标题/命令是否与来源一致。",
        "- Engagement：检查开头是否具体、叙事是否清楚、CTA 是否指向读论文/试命令/看仓库。",
        "- Alignment：检查平台语气、节奏、标签、图片比例和图文配合是否匹配。",
        "- 每次输出都要填写 promotionStrategy.qualityRubric。",
        "",
        "只输出严格 JSON，不要 Markdown 代码块，不要解释 JSON 之外的内容。",
    ])


def build_promo_user_prompt(payload: dict[str, Any], *, platform: str = "all", brief_section: str = "") -> str:
    platform_hint = "请生成所有平台的完整 markdown 字段。launchSequence 按准备度给出发布顺序。" if platform == "all" else f"重点打磨 {platform} 对应平台，其他平台给出简短可用 markdown。"
    parts = [
        "请基于以下来源数据，生成各平台可直接发布的推广 Markdown 文件内容。",
        "",
        "## 写作时必须引用的真实证据（不可违背）",
        build_evidence_brief(payload),
        "",
    ]
    if brief_section:
        parts.extend([brief_section, ""])
    parts.extend([
        "写作时请参考优秀开源项目的 Launch Kit 写法：",
        "- 规划层：先抽取来源材料，再合成主推广角度，最后按平台改写，并给出 fidelity / engagement / platform alignment 三轴审核。",
        "- 三轴审核必须写入 promotionStrategy.qualityRubric，不要只给笼统建议。",
        "- Show HN：个人故事 + 具体问题 + 技术切入点 + 首条评论 + 2 条 limitations。",
        "- 小红书：像记录一次排查 README 的过程，不要写虚假 star 增长。",
        "",
        "JSON 输出结构必须是：",
        PROMO_JSON_SCHEMA,
        "",
        platform_hint,
        "",
        "完整仓库数据：",
        json.dumps(payload, ensure_ascii=False, indent=2),
    ])
    return "\n".join(parts)


def build_evidence_brief(payload: dict[str, Any]) -> str:
    project = payload.get("project", {})
    evidence = payload.get("evidence", {})
    lines = [f"- 项目：{project.get('name', 'unknown')}"]
    if project.get("description"):
        lines.append(f"- 描述：{project['description']}")
    if project.get("installCommand"):
        lines.append(f"- 安装命令（必须原样使用）：`{project['installCommand']}`")
    if project.get("repositoryUrl"):
        lines.append(f"- 仓库：{project['repositoryUrl']}")
    if project.get("topics"):
        lines.append(f"- Topics：{', '.join(project['topics'])}")
    if payload.get("heuristicScore"):
        lines.append("- 本地资料检查：已完成，仅作 CI / 资料完整度参考；推广正文不要展示分数或等级")
    if evidence.get("readmeOpening"):
        lines.append(f"- README 开头片段：{str(evidence['readmeOpening']).strip()[:200]}…")
    risks = evidence.get("launchRisks") or []
    if risks:
        lines.append("- launchRisks（可诚实提及或用于 Show HN limitations）：")
        for risk in risks[:3]:
            lines.append(f"  - {risk.get('message') if isinstance(risk, dict) else risk}")
    top_fixes = payload.get("topFixes") or []
    if top_fixes:
        lines.append("- 优先改进项（可用于「我还在完善…」）：")
        for fix in top_fixes[:3]:
            lines.append(f"  - {fix.get('fix') or fix.get('message') if isinstance(fix, dict) else fix}")
    strong_checks = [
        item for item in payload.get("checks", [])
        if item.get("max") and item.get("score", 0) / item["max"] >= 0.75
    ][:3]
    if strong_checks:
        lines.append("- 可引用的真实亮点（转成场景句，不要照搬 summary）：")
        for check in strong_checks:
            lines.append(f"  - {check.get('label')}：{check.get('summary')}")
    return "\n".join(lines)

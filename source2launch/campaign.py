from __future__ import annotations

from typing import Any

PLATFORM_FILES = {
    "xhs": "platform/xhs.md",
    "zhihu": "platform/zhihu.md",
    "wechat": "platform/wechat.md",
    "showHn": "platform/show-hn.md",
    "productHunt": "platform/producthunt-kit.md",
}


def build_campaign(result: dict[str, Any], manifest: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or {}
    ai_content = context.get("aiPromoContent")
    project = result.get("project", {})
    return {
        "version": "0.2",
        "status": "review_required" if ai_content else "needs_model_config",
        "project": {
            "name": project.get("name"),
            "description": project.get("description"),
            "repositoryUrl": project.get("repositoryUrl"),
            "installCommand": project.get("installCommand"),
            "topics": project.get("topics") or [],
        },
        "source": {
            "summarySource": manifest.get("summarySource", "local"),
            "summaryModel": manifest.get("summaryModel"),
            "hasPdfContext": bool(context.get("hasPdfContext")),
            "hasDocContext": bool(context.get("hasDocContext")),
        },
        "generation": {
            "promoSource": manifest.get("promoSource"),
            "promoModel": manifest.get("promoModel"),
            "imageStatus": "generated" if manifest.get("images") else "not_generated",
            "mode": manifest.get("mode"),
            "skipped": list(manifest.get("skipped", [])),
        },
        "files": {
            "index": "INDEX.md",
            "sourceSummary": "project-summary.md",
            "contentReview": "content-review.md",
            "promoCopy": "promo-copy.md",
            "platforms": PLATFORM_FILES,
            "images": manifest.get("images", {}),
        },
        "reviewGate": build_review_gate(result, manifest, ai_content),
        "publish": {
            "defaultMode": "review",
            "execution": "not_executed",
            "note": "Generated content must be reviewed by a human before platform API calls or browser-assisted filling.",
        },
        "generatedFiles": list(manifest.get("generated", [])),
    }


def format_content_review(result: dict[str, Any], manifest: dict[str, Any], context: dict[str, Any] | None = None) -> str:
    context = context or {}
    review_gate = build_review_gate(result, manifest, context.get("aiPromoContent"))
    lines = [
        f"# {result.get('project', {}).get('name', 'Project')} · 内容审核清单",
        "",
        "> 由 Source2Launch 自动生成。发布前请人工确认，不代表平台已发布。",
        "",
        f"状态：**{'待人工审核' if review_gate['status'] == 'ready_for_review' else '需要补充配置'}**",
        "",
        "## 必查事实",
        "",
    ]
    for item in review_gate["mustVerify"]:
        lines.append(f"- [ ] {item}")
    lines.extend(["", "## 三轴审核", ""])
    append_rubric_axis(lines, review_gate["qualityRubric"]["fidelity"])
    append_rubric_axis(lines, review_gate["qualityRubric"]["engagement"])
    append_rubric_axis(lines, review_gate["qualityRubric"]["alignment"])
    lines.extend(["", "## 平台草稿", ""])
    for platform in review_gate["platforms"]:
        lines.append(f"- [{'x' if platform['ready'] else ' '}] {platform['label']}：{platform['file']} — {platform['note']}")
    lines.extend(["", "## 风险提示", ""])
    for item in review_gate["risks"]:
        lines.append(f"- {item}")
    lines.extend(["", "## 下一步", ""])
    if context.get("aiPromoContent"):
        lines.extend([
            "1. 逐个平台检查 `platform/` 中的草稿。",
            "2. 删除无法从 README、论文、截图、命令或代码中验证的表述。",
            "3. 确认图片、链接、标签和账号后，再运行 `source2launch publish promotion.json --publish-mode review` 生成发布计划。",
        ])
    else:
        lines.extend([
            "1. 配置 `SOURCE2LAUNCH_MODELSCOPE_API_KEY` 或 `SOURCE2LAUNCH_API_KEY`。",
            "2. 重新运行 `source2launch optimize . --output launch-assets/`。",
            "3. 再审核平台文案、配图和发布计划。",
        ])
    return "\n".join(lines) + "\n"


def format_show_hn_draft(result: dict[str, Any], promotions: dict[str, Any] | None = None) -> str:
    promotions = promotions or {}
    show_hn = promotions.get("showHn", {})
    if show_hn.get("markdown"):
        return show_hn["markdown"].strip() + "\n"
    project = result.get("project", {})
    return "\n".join([
        f"# {project.get('name', 'Project')} · Show HN",
        "",
        "> 发布前请确认标题、仓库链接和演示路径。",
        "",
        f"**Title:** Show HN: {project.get('name', 'Project')} - {project.get('description', 'source-grounded launch workflow')}",
        "",
        "配置 API Key 后重新生成 Show HN 草稿。",
        "",
    ])


def format_product_hunt_kit(result: dict[str, Any], promotions: dict[str, Any] | None = None) -> str:
    promotions = promotions or {}
    product_hunt = promotions.get("productHunt", {})
    if product_hunt.get("markdown"):
        return product_hunt["markdown"].strip() + "\n"
    project = result.get("project", {})
    return "\n".join([
        f"# {project.get('name', 'Project')} · Product Hunt Kit",
        "",
        "> 结构化 launch 草稿。提交前请按 Product Hunt 页面逐项复制并人工确认。",
        "",
        "## Name",
        project.get("name", "Project"),
        "",
        "## Tagline",
        project.get("description") or "配置 API Key 后重新生成 tagline。",
        "",
        "## First Comment",
        "",
        "配置 API Key 后重新生成 maker comment。",
        "",
        "## Gallery Plan",
        "",
        "- [ ] 封面图：展示真实输出或产品界面，不使用虚构数据。",
        "- [ ] 第二张：README / 论文关键图表 / 终端运行截图。",
        "- [ ] 第三张：生成的平台文案或 launch-assets 目录。",
        "",
    ])


def build_review_gate(result: dict[str, Any], manifest: dict[str, Any], ai_content: dict[str, Any] | None = None) -> dict[str, Any]:
    project = result.get("project", {})
    platforms = [
        platform_status("小红书", PLATFORM_FILES["xhs"], nested(ai_content, "promotions", "xiaohongshu")),
        platform_status("知乎", PLATFORM_FILES["zhihu"], nested(ai_content, "promotions", "zhihu")),
        platform_status("微信", PLATFORM_FILES["wechat"], nested(ai_content, "promotions", "wechatMoments")),
        platform_status("Show HN", PLATFORM_FILES["showHn"], nested(ai_content, "promotions", "showHn")),
        platform_status("Product Hunt", PLATFORM_FILES["productHunt"], nested(ai_content, "promotions", "productHunt")),
    ]
    must_verify = [
        "安装命令、仓库链接、论文标题和作者信息必须来自输入证据。",
        "不得编造 star 数、用户数、benchmark、媒体报道、录用状态或实验结论。",
        "配图必须来自真实截图、论文图表、生成封面或明确标注的视觉草案。",
        "小红书/知乎/微信正文需要符合账号口吻，不要直接保留模型解释性文字。",
    ]
    if project.get("installCommand"):
        must_verify.insert(0, f"安装命令是否仍为 `{project['installCommand']}`。")
    if project.get("repositoryUrl"):
        must_verify.insert(0, f"仓库链接是否仍为 {project['repositoryUrl']}。")
    risks = []
    if not ai_content:
        risks.append("未配置 AI Key，平台文案为占位或本地模板，需要重新生成。")
    if not manifest.get("images"):
        risks.append("未生成配图；小红书、微信、Product Hunt 发布前应补真实截图或生成封面。")
    for risk in (result.get("evidence", {}).get("launchRisks") or [])[:4]:
        risks.append(risk.get("message") if isinstance(risk, dict) else str(risk))
    if not risks:
        risks.append("未发现自动化层面的明显风险；仍需人工确认事实和平台语气。")
    return {
        "status": "ready_for_review" if ai_content else "needs_model_config",
        "qualityRubric": build_quality_rubric(ai_content),
        "mustVerify": must_verify,
        "platforms": platforms,
        "risks": risks,
    }


def build_quality_rubric(ai_content: dict[str, Any] | None = None) -> dict[str, Any]:
    provided = nested(ai_content, "promotionStrategy", "qualityRubric") or {}
    return {
        "fidelity": normalize_axis(provided.get("fidelity"), {
            "label": "Fidelity",
            "checks": [
                "核心 claim 是否能在 README、论文、截图、命令或代码里找到来源。",
                "标题、作者、仓库链接、安装命令、论文结论是否准确。",
                "没有编造 benchmark、用户数、star 增长、媒体报道或录用状态。",
            ],
            "risks": ["来源证据不足时，模型可能把方法描述写成已验证结果。"],
            "improvements": ["删掉无法核实的强结论，补充来源截图、论文页码、README 片段或运行命令。"],
        }),
        "engagement": normalize_axis(provided.get("engagement"), {
            "label": "Engagement",
            "checks": [
                "开头是否具体到一个读者场景，而不是泛泛介绍项目。",
                "读者是否能在前几行看到问题、价值和下一步动作。",
                "CTA 是否指向读论文、试命令、看仓库或查看图表。",
            ],
            "risks": ["文案可能过于模板化，标题像广告而不是作者分享。"],
            "improvements": ["保留一个具体痛点、一个证据和一个行动，删除空泛形容词。"],
        }),
        "alignment": normalize_axis(provided.get("alignment"), {
            "label": "Alignment",
            "checks": [
                "小红书、知乎、微信、Show HN、Product Hunt 是否使用不同结构。",
                "标签、标题长度、图片比例和语气是否适配对应平台。",
                "配图是否支撑正文 claim，而不是只做装饰。",
            ],
            "risks": ["同一段文字跨平台复用会降低真实感和平台匹配度。"],
            "improvements": ["按平台重写开头、段落节奏、标签和配图顺序。"],
        }),
    }


def append_rubric_axis(lines: list[str], axis: dict[str, Any]) -> None:
    lines.extend([f"### {axis['label']}", ""])
    for item in axis["checks"]:
        lines.append(f"- [ ] {item}")
    if axis.get("risks"):
        lines.extend(["", f"风险：{'；'.join(axis['risks'])}"])
    if axis.get("improvements"):
        lines.append(f"改进：{'；'.join(axis['improvements'])}")
    lines.append("")


def normalize_axis(value: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    value = value if isinstance(value, dict) else {}
    return {
        "label": value.get("label") or fallback["label"],
        "checks": normalize_list(value.get("checks"), fallback["checks"]),
        "risks": normalize_list(value.get("risks"), fallback["risks"]),
        "improvements": normalize_list(value.get("improvements"), fallback["improvements"]),
    }


def normalize_list(value: Any, fallback: list[str]) -> list[str]:
    items = value if isinstance(value, list) else [value] if value else fallback
    return [str(item).strip() for item in items if str(item).strip()][:5]


def platform_status(label: str, file: str, content: Any) -> dict[str, Any]:
    ready = has_platform_content(content)
    return {"label": label, "file": file, "ready": ready, "note": "已生成草稿，待人工审核" if ready else "未生成 AI 草稿"}


def has_platform_content(value: Any) -> bool:
    if not value:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(value.get(key) for key in ["markdown", "body", "title", "tagline", "firstComment"])
    return False


def nested(value: dict[str, Any] | None, *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current

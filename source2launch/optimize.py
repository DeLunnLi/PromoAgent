from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .campaign import build_campaign, format_content_review, format_product_hunt_kit, format_show_hn_draft
from .markdown import generate_markdown_document

DEFAULT_OUTPUT_DIR = "launch-assets"


def run_optimize(
    result: dict[str, Any],
    *,
    cwd: str | Path | None = None,
    output_dir: str | Path | None = None,
    llm_only: bool = False,
    with_heuristic: bool = False,
    ai_content: dict[str, Any] | None = None,
    ai_model: str | None = None,
) -> dict[str, Any]:
    root = Path(cwd or ".").resolve()
    out = Path(output_dir or DEFAULT_OUTPUT_DIR)
    if not out.is_absolute():
        out = root / out
    (out / "platform").mkdir(parents=True, exist_ok=True)
    (out / "images").mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "project": result.get("project", {}).get("name"),
        "outputDir": str(out),
        "score": result.get("score"),
        "grade": result.get("grade"),
        "generated": [],
        "skipped": [],
        "promoSource": "ai" if ai_content else "unavailable",
        "promoModel": ai_model,
        "images": {},
        "mode": "llm" if llm_only else "full",
        "summarySource": "local",
    }

    write_asset(out, "project-summary.md", generate_markdown_document(result, markdown_type="project"), manifest)

    if with_heuristic or not llm_only:
        write_asset(out, "heuristic-audit.md", format_heuristic_report(result), manifest)
        write_asset(out, "readme-suggestions.md", format_readme_suggestions(result), manifest)
    else:
        manifest["skipped"].append("本地资料检查包：已跳过（默认 LLM 模式；需要时用 --with-heuristic）")

    promotions = (ai_content or {}).get("promotions", {})
    xhs = platform_markdown_or_unavailable(result, promotions.get("xiaohongshu"), "小红书")
    zhihu = platform_markdown_or_unavailable(result, promotions.get("zhihu"), "知乎")
    wechat = platform_markdown_or_unavailable(result, promotions.get("wechatMoments") or promotions.get("wechat"), "微信")
    show_hn = format_show_hn_draft(result, promotions)
    product_hunt = format_product_hunt_kit(result, promotions)

    write_asset(out, "promo-xhs.md", xhs, manifest)
    write_asset(out, "promo-zhihu.md", zhihu, manifest)
    write_asset(out, "promo-wechat.md", wechat, manifest)
    write_asset(out, "promo-en.md", format_english_unavailable(result), manifest)
    write_asset(out, "promo-copy.md", format_promo_copy_index(result, ai_content), manifest)
    write_asset(out, "platform/xhs.md", xhs, manifest)
    write_asset(out, "platform/zhihu.md", zhihu, manifest)
    write_asset(out, "platform/wechat.md", wechat, manifest)
    write_asset(out, "platform/show-hn.md", show_hn, manifest)
    write_asset(out, "platform/producthunt-kit.md", product_hunt, manifest)
    write_asset(out, "content-review.md", format_content_review(result, manifest, {"aiPromoContent": ai_content}), manifest)
    write_asset(out, "campaign.json", json.dumps(build_campaign(result, manifest, {"aiPromoContent": ai_content}), ensure_ascii=False, indent=2) + "\n", manifest)
    write_asset(out, "INDEX.md", format_optimize_index(manifest, result), manifest)
    return manifest


def write_asset(output_dir: Path, relative: str, content: str, manifest: dict[str, Any]) -> None:
    path = output_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    manifest["generated"].append(relative)


def format_optimize_index(manifest: dict[str, Any], result: dict[str, Any]) -> str:
    lines = [
        f"# {manifest.get('project') or 'Project'} · Launch Assets",
        "",
        "> 由 `source2launch optimize` Python implementation 自动生成",
        "",
        "资料检查：**已生成本地检查报告**" if "heuristic-audit.md" in manifest["generated"] else "资料检查：**已跳过本地规则检查**",
        "项目理解：**本地证据摘要**（Python 迁移版）",
        f"AI 平台文案：**{'已生成' if manifest.get('promoSource') == 'ai' else '未生成（需配置 API Key）'}**",
        "",
        "## 文件清单",
        "",
    ]
    for file in manifest["generated"]:
        lines.append(f"- [{file}](./{file}){promo_file_note(file)}")
    lines.extend([
        "",
        "## 推荐使用顺序",
        "",
        "1. 阅读 `project-summary.md`（项目理解，推荐起点）",
        "2. 阅读 `content-review.md`，确认事实、图片、链接和平台语气",
        "3. 到 `platform/` 选择要发布的平台草稿",
        "4. 英文渠道优先看 `platform/show-hn.md` 和 `platform/producthunt-kit.md`",
        "5. 需要自动化对接时读取 `campaign.json`",
        "",
        "## 项目信息",
        "",
        f"- 项目：{result.get('project', {}).get('name')}",
    ])
    project = result.get("project", {})
    if project.get("repositoryUrl"):
        lines.append(f"- 仓库：{project['repositoryUrl']}")
    if project.get("installCommand"):
        lines.append(f"- 安装：`{project['installCommand']}`")
    return "\n".join(lines) + "\n"


def promo_file_note(file: str) -> str:
    notes = {
        "content-review.md": " — 人工审核清单",
        "campaign.json": " — 机器可读 campaign",
        "platform/xhs.md": " — 小红书草稿",
        "platform/zhihu.md": " — 知乎草稿",
        "platform/wechat.md": " — 微信草稿",
        "platform/show-hn.md": " — Show HN 草稿",
        "platform/producthunt-kit.md": " — Product Hunt Kit",
    }
    return notes.get(file, "")


def format_platform_unavailable(result: dict[str, Any], platform_label: str) -> str:
    project = result.get("project", {})
    return "\n".join([
        f"# {project.get('name', 'Project')} · {platform_label}",
        "",
        "> 尚未生成 AI 平台正文",
        "",
        "Python 迁移版已生成证据、审核清单和平台文件结构；配置 AI Key 后可接入后续 Python AI 生成模块。",
        "",
        "```sh",
        "source2launch optimize . --output launch-assets/",
        "```",
        "",
    ])


def platform_markdown_or_unavailable(result: dict[str, Any], content: Any, platform_label: str) -> str:
    if isinstance(content, dict):
        markdown = content.get("markdown") or content.get("body")
        if markdown:
            return str(markdown).strip() + "\n"
        title = content.get("title") or ((content.get("titles") or [None])[0])
        if title:
            return "\n".join([
                f"# {result.get('project', {}).get('name', 'Project')} · {platform_label}",
                "",
                f"## {title}",
                "",
                str(content.get("summary") or content.get("publishNotes") or "待补充正文。"),
                "",
            ])
    if isinstance(content, str) and content.strip():
        return content.strip() + "\n"
    return format_platform_unavailable(result, platform_label)


def format_english_unavailable(result: dict[str, Any]) -> str:
    project = result.get("project", {})
    return "\n".join([
        f"# {project.get('name', 'Project')} · English Launch Drafts",
        "",
        "> AI platform copy has not been generated yet in the Python migration path.",
        "",
        "Use `platform/show-hn.md` and `platform/producthunt-kit.md` as reviewable placeholders.",
        "",
    ])


def format_promo_copy_index(result: dict[str, Any], ai_content: dict[str, Any] | None = None) -> str:
    project = result.get("project", {})
    lines = [
        f"# {project.get('name', 'Project')} · 推广文案索引",
        "",
        "> Python 迁移版 · 各平台完整正文见对应文件",
        "",
        f"**定位：** {(ai_content or {}).get('positioning') or project.get('description') or '待 AI 根据来源证据生成'}",
        "",
    ]
    if ai_content and ai_content.get("promotionStrategy", {}).get("coreAngle"):
        lines.extend([
            "## Promotion Strategy",
            "",
            f"**Core angle:** {ai_content['promotionStrategy']['coreAngle']}",
            "",
        ])
        append_quality_rubric(lines, ai_content.get("promotionStrategy", {}).get("qualityRubric"))
    lines.extend([
        "## 平台文件",
        "",
        "- [platform/xhs.md](./platform/xhs.md) — 小红书",
        "- [platform/wechat.md](./platform/wechat.md) — 微信朋友圈",
        "- [platform/zhihu.md](./platform/zhihu.md) — 知乎",
        "- [platform/show-hn.md](./platform/show-hn.md) — Show HN",
        "- [platform/producthunt-kit.md](./platform/producthunt-kit.md) — Product Hunt",
        "",
        "## Quality Rubric",
        "",
        "- Fidelity: facts must come from README, paper, screenshot, command, or code.",
        "- Engagement: hook, narrative, and next action must be concrete.",
        "- Alignment: platform format, tone, tags, and visuals must fit the channel.",
    ])
    return "\n".join(lines) + "\n"


def append_quality_rubric(lines: list[str], quality_rubric: dict[str, Any] | None) -> None:
    if not quality_rubric:
        return
    lines.append("**Quality rubric:**")
    for label, key in [("Fidelity", "fidelity"), ("Engagement", "engagement"), ("Alignment", "alignment")]:
        axis = quality_rubric.get(key) or {}
        checks = axis.get("checks") or []
        risks = axis.get("risks") or []
        improvements = axis.get("improvements") or []
        lines.append(f"- {label}: {'；'.join(map(str, checks[:2])) if checks else '待人工确认'}")
        if risks:
            lines.append(f"  - Risk: {risks[0]}")
        if improvements:
            lines.append(f"  - Improve: {improvements[0]}")
    lines.append("")


def format_heuristic_report(result: dict[str, Any]) -> str:
    lines = [
        "Source2Launch · Python 本地资料检查",
        "",
        f"目标    {result.get('target')}",
        f"项目    {result.get('project', {}).get('name')}",
        "资料检查 已生成本地检查报告（仅供 CI / 资料完整度参考）",
        "",
        "检查明细",
    ]
    for check in result.get("checks", []):
        lines.append(f"  {check.get('label', ''):<20} {check.get('summary', '')}")
    lines.extend(["", "优先改进"])
    top_fixes = result.get("topFixes") or []
    if not top_fixes:
        lines.append("  未发现明显发布资料短板。")
    else:
        for fix in top_fixes:
            lines.append(f"  [{fix.get('severity')}] {fix.get('message')}")
            lines.append(f"         → {fix.get('fix')}")
    lines.extend(["", "提示    本地资料检查仅供 CI；发布文案请用：source2launch promote . --platform all"])
    return "\n".join(lines) + "\n"


def format_readme_suggestions(result: dict[str, Any]) -> str:
    project = result.get("project", {})
    lines = [
        f"# {project.get('name', 'Project')} · README Suggestions",
        "",
        "## First Screen",
        "",
        "- Keep the one-line pitch directly under the H1.",
        "- Show one real screenshot, GIF, terminal output, or paper figure.",
        "- Put the shortest install or try command before long background sections.",
        "",
        "## Fixes From Local Evidence",
        "",
    ]
    for fix in result.get("topFixes", [])[:6]:
        lines.append(f"- **{fix.get('severity', 'medium')}**: {fix.get('fix') or fix.get('message')}")
    if len(lines) <= 10:
        lines.append("- No major README issue was detected by local checks.")
    return "\n".join(lines) + "\n"

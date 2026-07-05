"""Interactive Q&A for Source2Launch's promotion agent.

After initial source analysis, identifies the most critical missing information
and asks the user targeted questions (max 3) to fill in the gaps.
Works for any subject: repos, restaurants, products, events, papers, etc.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Gap definitions: what's important for good promotional content
# ---------------------------------------------------------------------------

GAP_QUESTIONS: dict[str, str] = {
    "description": (
        "核心价值是什么？给谁用 / 解决什么问题 / 有什么特色？"
        "（例：麻辣鲜香的火锅，主打性价比，人均80元）"
    ),
    "target_audience": (
        "目标受众是谁？"
        "（例：25-35岁上班族、开发者、学生党、餐饮从业者）"
    ),
    "cta": (
        "用户如何联系/购买/体验？"
        "（链接、电话、地址、安装命令等，可以直接回车跳过）"
    ),
    "visuals": (
        "有图片、截图或配图吗？"
        "（本地文件路径或图片链接，多个用空格分隔，回车跳过）"
    ),
    "proof": (
        "有什么能证明质量的信息？"
        "（评价、奖项、媒体报道、数据指标、用户数量等）"
    ),
    "price": (
        "价格或费用范围？"
        "（例：人均 80-120 元 / 免费开源 / 订阅制 29元/月）"
    ),
}

# Priority order for gap detection
GAP_PRIORITY = ["description", "target_audience", "cta", "visuals", "proof"]


# ---------------------------------------------------------------------------
# Gap identification
# ---------------------------------------------------------------------------

def identify_gaps(result: dict[str, Any]) -> list[str]:
    """Identify the most critical missing information for good promotional content.

    Returns at most 3 gap keys, in priority order.
    """
    project = result.get("project", {})
    evidence = result.get("evidence", {})
    ctx = evidence.get("additionalContext", {})
    gaps: list[str] = []

    # Description quality check
    desc = (
        project.get("description")
        or evidence.get("opening")
        or evidence.get("readmeOpening")
        or ""
    )
    if len(str(desc).strip()) < 40:
        gaps.append("description")

    # Target audience
    has_audience = (
        project.get("topics")
        or ctx.get("audience")
        or ctx.get("target_audience")
    )
    if not has_audience:
        gaps.append("target_audience")

    # Call-to-action
    has_cta = (
        project.get("cta")
        or project.get("installCommand")
        or project.get("homepage")
        or project.get("repositoryUrl")
        or evidence.get("keyActions")
        or evidence.get("installCommands")
    )
    if not has_cta:
        gaps.append("cta")

    # Visuals
    has_visuals = evidence.get("visuals") or evidence.get("visualUrls")
    if not has_visuals and "visuals" not in gaps:
        gaps.append("visuals")

    # Proof points
    has_proof = evidence.get("proofPoints")
    if not has_proof and "proof" not in gaps:
        gaps.append("proof")

    return gaps[:3]


def has_significant_gaps(result: dict[str, Any]) -> bool:
    """Return True if the result is missing enough info to warrant asking questions."""
    gaps = identify_gaps(result)
    # Always ask if description is missing or CTA is missing
    critical = {"description", "cta"}
    return bool(set(gaps) & critical) or len(gaps) >= 2


# ---------------------------------------------------------------------------
# Interactive Q&A
# ---------------------------------------------------------------------------

def ask_and_merge(
    result: dict[str, Any],
    *,
    force: bool = False,
    max_questions: int = 3,
) -> dict[str, Any]:
    """Identify gaps and ask the user up to max_questions targeted questions.

    If running non-interactively (not a TTY), silently returns the original result.
    Set force=True to ask even when there are no detected gaps (e.g., --interactive flag).
    """
    if not sys.stdin.isatty():
        return result  # Non-interactive mode: skip Q&A

    gaps = identify_gaps(result) if not force else list(GAP_QUESTIONS.keys())[:max_questions]
    if not gaps:
        return result

    project_name = result.get("project", {}).get("name") or "你的推广主体"
    print(f"\n✦ 已分析「{project_name}」，补充几个信息能让推广内容更好：\n", file=sys.stderr)

    answers: dict[str, str] = {}
    for i, gap in enumerate(gaps[:max_questions], 1):
        question = GAP_QUESTIONS.get(gap, f"关于 {gap}，有什么补充？")
        print(f"  {i}. {question}", file=sys.stderr)
        try:
            ans = input("     > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n（跳过补充，继续生成…）", file=sys.stderr)
            break
        if ans:
            answers[gap] = ans
        print(file=sys.stderr)

    if not answers:
        return result

    merged = _merge_answers(result, answers)
    print(f"✓ 信息补充完成，正在生成推广内容…\n", file=sys.stderr)
    return merged


# ---------------------------------------------------------------------------
# Answer merging
# ---------------------------------------------------------------------------

def _merge_answers(result: dict[str, Any], answers: dict[str, str]) -> dict[str, Any]:
    """Merge user answers back into the result dict."""
    merged = copy.deepcopy(result)
    project = merged.setdefault("project", {})
    evidence = merged.setdefault("evidence", {})
    ctx = evidence.setdefault("additionalContext", {})

    if "description" in answers:
        ans = answers["description"]
        project["description"] = ans
        evidence["opening"] = ans
        evidence["readmeOpening"] = ans   # keep legacy field in sync

    if "target_audience" in answers:
        ans = answers["target_audience"]
        ctx["audience"] = ans
        # Also populate topics from the audience description
        project["topics"] = [t.strip() for t in re.split(r"[、,，/]", ans) if t.strip()][:6]

    if "cta" in answers:
        ans = answers["cta"]
        project["cta"] = ans
        # Detect if it looks like an install command
        if re.match(r"^(npm|pip|cargo|go install|docker|brew|apt|curl)\b", ans, re.I):
            project["installCommand"] = ans
        elif ans.startswith(("http://", "https://")):
            project["homepage"] = project.get("homepage") or ans
        # Always store in keyActions too
        evidence.setdefault("keyActions", [])
        if ans not in evidence["keyActions"]:
            evidence["keyActions"].append(ans)
        evidence.setdefault("installCommands", [])
        if ans not in evidence["installCommands"]:
            evidence["installCommands"].append(ans)

    if "visuals" in answers:
        for item in answers["visuals"].split():
            item = item.strip()
            if not item:
                continue
            if item.startswith(("http://", "https://")):
                evidence.setdefault("visualUrls", []).append(item)
            elif Path(item).exists():
                evidence.setdefault("visuals", []).append(f"![image]({item})")

    if "proof" in answers:
        evidence.setdefault("proofPoints", []).append(answers["proof"])

    if "price" in answers:
        ctx["price"] = answers["price"]

    return merged


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

import re  # noqa: E402 — needed by _merge_answers above

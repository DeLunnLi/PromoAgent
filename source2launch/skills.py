from __future__ import annotations

from typing import Any

PROMOTION_SKILLS: dict[str, dict[str, Any]] = {
    "paper": {
        "aliases": ["paper-promo", "academic", "academic-promo", "research"],
        "label": "Paper promotion",
        "description": "Generate grounded promotion copy from a paper, PDF, abstract, or paper page.",
        "platform": "all",
        "audience": "researchers, engineers, and technical readers who may want to inspect the paper",
        "tone": "credible researcher reading note",
        "promptPresets": ["paper", "visual", "paper2web", "autopr", "scholardag"],
        "promptNotes": [
            "Treat the source as a paper-first promotion task. Extract problem, method, evidence, figures/tables, limitations, and reader fit before writing.",
            "For Chinese platforms, make Zhihu explanatory, Xiaohongshu carousel-oriented, and WeChat article-like. Do not turn the abstract into one flat paragraph.",
        ],
        "reviewFocus": ["Paper claim fidelity", "Method/result evidence", "Figure or table selection", "Limitations and missing code caveats"],
    },
    "code": {
        "aliases": ["repo", "repository", "code-launch", "open-source", "oss"],
        "label": "Open-source code launch",
        "description": "Generate launch copy from a GitHub repository or local code project.",
        "platform": "launch",
        "audience": "developers, maintainers, and technical early adopters",
        "tone": "open-source maintainer launch note",
        "promptPresets": ["launch", "launchkit", "technical", "visual", "autopr", "scholardag"],
        "promptNotes": [
            "Treat the source as an open-source launch task. Keep input, output, install command, demo path, examples, and limitations visible.",
            "Product Hunt, Show HN, and LinkedIn variants must be structurally different instead of reusing one generic paragraph.",
        ],
        "reviewFocus": ["Install or try path", "Concrete workflow", "README or demo proof", "No fake traction or production-readiness claims"],
    },
    "paper-code": {
        "aliases": ["code-paper", "repo-paper", "paper+code", "research-code", "joint"],
        "label": "Paper plus code promotion",
        "description": "Generate a unified promotion pack when a paper and its code/project are both available.",
        "platform": "all",
        "audience": "researchers, engineers, and builders who want both the idea and the runnable artifact",
        "tone": "research-to-code launch note",
        "promptPresets": ["paper", "launchkit", "technical", "visual", "paper2web", "autopr", "scholardag"],
        "promptNotes": [
            "Treat the primary target and --context sources as one release story. Explain the paper contribution and the runnable code path together.",
            "Do not merge facts blindly: say which claims come from the paper and which come from the repository, README, docs, or demo.",
            "Every platform variant should include both a research reason to read and a practical reason to try the code when evidence exists.",
        ],
        "reviewFocus": ["Paper-to-code alignment", "Claim provenance", "Runnable path", "Visual evidence from paper figures and README/demo screenshots"],
    },
    "social": {
        "aliases": ["social-pack", "cross-platform", "platform-pack"],
        "label": "Cross-platform social pack",
        "description": "Generate one source-grounded campaign across social platforms.",
        "platform": "all",
        "audience": "technical readers across social platforms",
        "tone": "platform-native technical sharing",
        "promptPresets": ["tweet", "zhihu", "xhs", "wechat", "visual", "autopr", "scholardag"],
        "promptNotes": [
            "Optimize for platform-native structure. Each platform should have its own hook, format, visual plan, and avoid-list.",
            "Keep the same factual content graph across platforms while adapting tone and layout.",
        ],
        "reviewFocus": ["Platform alignment", "Shared factual graph", "Channel-specific hooks", "No platform-inappropriate copy reuse"],
    },
    "visual": {
        "aliases": ["visual-pack", "image-pack", "asset-pack"],
        "label": "Visual promotion pack",
        "description": "Plan source-grounded visuals for paper figures, README screenshots, demos, and social cards.",
        "platform": "all",
        "audience": "readers who scan visuals before opening a source link",
        "tone": "visual-first technical explanation",
        "promptPresets": ["visual", "paper2web", "paper", "technical"],
        "promptNotes": [
            "Prioritize visualNarrative and visualPlan. Name exact source clips, figures, tables, README snippets, or demo screenshots before suggesting generated images.",
            "Do not ask image models to invent results, logos, screenshots, UI states, or benchmark numbers.",
        ],
        "reviewFocus": ["Source clip selection", "Visual-to-claim fit", "Platform image dimensions", "No fabricated visual evidence"],
    },
    "markdown": {
        "aliases": ["project-doc", "project-markdown", "readme", "docs", "markdown-doc"],
        "label": "Project markdown generator",
        "description": "Generate a local Markdown document from project, repository, paper, or related-source evidence.",
        "platform": None,
        "audience": "project maintainers and technical readers who need a reusable Markdown artifact",
        "tone": "clear source-grounded project documentation",
        "promptPresets": ["technical", "launch", "visual"],
        "promptNotes": [
            "Generate a Markdown artifact from source evidence before writing short-form social copy.",
            "Keep claims traceable to README, package metadata, examples, docs, paper, or related sources.",
        ],
        "reviewFocus": ["Source-grounded sections", "README or launch-document completeness", "Install and demo accuracy", "No invented metrics or fake project status"],
    },
}

ALIAS_TO_SKILL = {
    alias: name
    for name, skill in PROMOTION_SKILLS.items()
    for alias in [name, *skill["aliases"]]
}


def promotion_skill_names() -> list[str]:
    return list(PROMOTION_SKILLS.keys())


def promotion_skill_catalog() -> dict[str, dict[str, Any]]:
    return {name: clone_skill(skill) for name, skill in PROMOTION_SKILLS.items()}


def normalize_promotion_skill_names(value: str | list[str] | None) -> list[str]:
    values = value if isinstance(value, list) else [value]
    names: list[str] = []
    for item in values:
        names.extend(part.strip().lower() for part in str(item or "").split(",") if part.strip())
    return names


def resolve_promotion_skills(value: str | list[str] | None) -> list[dict[str, Any]]:
    resolved = []
    seen = set()
    for name in normalize_promotion_skill_names(value):
        canonical = ALIAS_TO_SKILL.get(name)
        if not canonical:
            raise ValueError(f"Unknown skill: {name}. Available skills: {', '.join(promotion_skill_names())}")
        if canonical in seen:
            continue
        seen.add(canonical)
        skill = clone_skill(PROMOTION_SKILLS[canonical])
        skill["name"] = canonical
        resolved.append(skill)
    return resolved


def build_promotion_skill_plan(value: str | list[str] | None) -> dict[str, Any]:
    skills = resolve_promotion_skills(value)
    return {
        "skills": skills,
        "promptPresets": unique([preset for skill in skills for preset in skill["promptPresets"]]),
        "promptNotes": [note for skill in skills for note in skill["promptNotes"]],
        "reviewFocus": unique([item for skill in skills for item in skill["reviewFocus"]]),
        "defaultPlatform": first_present([skill.get("platform") for skill in skills]),
        "defaultAudience": first_present([skill.get("audience") for skill in skills]),
        "defaultTone": first_present([skill.get("tone") for skill in skills]),
    }


def clone_skill(skill: dict[str, Any]) -> dict[str, Any]:
    return {
        key: list(value) if isinstance(value, list) else value
        for key, value in skill.items()
    }


def first_present(values: list[Any]) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def unique(values: list[Any]) -> list[Any]:
    seen = set()
    result = []
    for value in values:
        if value in (None, "") or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result

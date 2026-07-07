"""Reusable creative skills for ad image generation."""
from __future__ import annotations

from typing import Any


_SKILLS: dict[str, dict[str, Any]] = {
    "ad-cover": {
        "label": "Real ad cover",
        "summary": "commercial campaign key visual with one strong promise, one hero subject, and obvious conversion intent.",
        "bestFor": ("general", "software", "service", "product"),
        "directives": (
            "Start from a real paid-ad layout: desire hook, proof cue, and clean CTA-safe space.",
            "Make the subject feel photographed or art-directed, not pasted into a template.",
            "Use one conversion object in the scene, such as a product, workflow outcome, venue moment, or document result.",
        ),
        "composition": "large hero subject, clear copy-safe area, supporting props below visual priority, thumbnail-readable silhouette.",
        "palette": "premium neutrals with two controlled accent colors; avoid single-hue gradients and rainbow neon.",
        "lighting": "commercial softbox or editorial natural light, crisp edges, believable shadows, no muddy midtones.",
        "avoid": (
            "generic AI poster",
            "template-looking banner",
            "flat vector collage",
            "fake social media UI",
            "unreadable decorative text",
        ),
    },
    "xhs-lifestyle": {
        "label": "Xiaohongshu lifestyle ad",
        "summary": "creator-native Xiaohongshu cover that feels like a polished recommendation post, not a corporate banner.",
        "bestFor": ("local_food", "product", "service", "general"),
        "directives": (
            "Prioritize a close, tactile first-person discovery moment that can stop a mobile feed scroll.",
            "Keep the top area bright and simple for local Chinese overlay text.",
            "Use believable lifestyle context: hand-scale objects, table texture, neighborhood light, or real use scenario.",
        ),
        "composition": "portrait cover, hero subject fills the lower half, clean upper title zone, 2-3 supporting cues at most.",
        "palette": "warm whites, natural material colors, and one lively accent; keep saturation appetizing but not garish.",
        "lighting": "fresh daylight or warm shop light, shallow depth of field, strong foreground texture.",
        "avoid": (
            "corporate SaaS banner style",
            "tiny icon grids",
            "overly perfect stock photo",
            "fake app screenshots",
            "plastic food or product surfaces",
        ),
    },
    "food-local": {
        "label": "Local food discovery",
        "summary": "restaurant or local lifestyle recommendation with appetite-first realism and neighborhood credibility.",
        "bestFor": ("local_food",),
        "directives": (
            "Make the food or venue detail the unmistakable hero, with texture that looks edible and fresh.",
            "Suggest a real discovery context through tableware, storefront light, queue hint, or neighborhood atmosphere.",
            "Use ad composition, but keep it trustworthy and experience-led rather than discount-led.",
        ),
        "composition": "close hero dish or table moment, diagonal depth, clean overlay zone, no banquet spread.",
        "palette": "food-natural warm tones with green or red freshness accents, controlled highlights.",
        "lighting": "warm practical restaurant light, steam or gloss where appropriate, appetizing shadows.",
        "avoid": (
            "plastic-looking food",
            "fake menu prices",
            "overcrowded dining hall",
            "misleading coupon graphics",
            "messy table clutter",
        ),
    },
    "product-hero": {
        "label": "Product hero ad",
        "summary": "premium product recommendation visual with clear desirability, tactile quality, and use-case context.",
        "bestFor": ("product",),
        "directives": (
            "Show one clear product hero with believable scale, material detail, and a visible use scenario.",
            "Use supporting props only when they explain the product value or strengthen desire.",
            "Make it look like an e-commerce or launch campaign image without fake discounts or fake brand marks.",
        ),
        "composition": "hero product at 55-70% visual weight, controlled props, negative space for copy.",
        "palette": "product-led colors, neutral surface, one accent matching the product benefit.",
        "lighting": "crisp studio lighting mixed with natural lifestyle ambience, controlled reflections.",
        "avoid": (
            "impossible product geometry",
            "fake brand logo",
            "crowded marketplace grid",
            "discount sticker spam",
            "excessive glow",
        ),
    },
    "event-poster": {
        "label": "Event recruitment poster",
        "summary": "event/activity key visual that sells attendance through atmosphere, audience fit, and urgency.",
        "bestFor": ("event",),
        "directives": (
            "Show a credible event moment with stage, workshop table, screen glow, or engaged attendee silhouettes.",
            "Make the viewer understand why attending matters without inventing names, dates, sponsors, or numbers.",
            "Leave a clear information zone for local overlay text and CTA.",
        ),
        "composition": "clear venue focal point, small audience or participation cue, strong perspective depth.",
        "palette": "professional dark-neutral base with warm stage or city-light accents.",
        "lighting": "cinematic practical lights, screen glow, crisp subject separation.",
        "avoid": (
            "fake speaker names",
            "fake sponsor logos",
            "crowd chaos",
            "empty generic conference room",
            "festival poster cliché",
        ),
    },
    "b2b-saas": {
        "label": "B2B SaaS launch",
        "summary": "credible software or agent launch visual for founders, developers, and professional teams.",
        "bestFor": ("software",),
        "directives": (
            "Translate the tool's job-to-be-done into a concrete workflow scene: inputs, processing, and publish-ready output.",
            "Show product value through abstract UI fragments and real work artifacts, not fake dashboards full of numbers.",
            "Keep it polished enough for LinkedIn or Product Hunt while preserving maker energy.",
        ),
        "composition": "one central device or workflow object, source artifacts on one side, finished outputs on the other, copy-safe zone.",
        "palette": "charcoal or clean white base with cyan, green, or amber accents; avoid purple-blue gradient dominance.",
        "lighting": "premium desk or product launch lighting, crisp UI glow, realistic depth.",
        "avoid": (
            "robot mascot",
            "fake metrics",
            "dense code wall",
            "generic startup office",
            "busy card mosaic",
        ),
    },
    "research-editorial": {
        "label": "Research editorial cover",
        "summary": "research or document recommendation visual with evidence, method clarity, and academic credibility.",
        "bestFor": ("research",),
        "directives": (
            "Make the document, figure, dataset, or method artifact the hero instead of using a vague sci-fi metaphor.",
            "Use simplified charts or diagrams as texture only; do not invent readable values.",
            "Signal credibility with clean editorial layout, precise geometry, and restrained contrast.",
        ),
        "composition": "document hero, 2-3 evidence artifacts, clean analysis desk, wide or square copy-safe area.",
        "palette": "paper white, ink dark, one measured technical accent such as blue or green.",
        "lighting": "clean editorial desk light, high legibility, precise shadows.",
        "avoid": (
            "fake institution logo",
            "fake chart numbers",
            "dense unreadable paper text",
            "sci-fi laboratory",
            "abstract brain icon cliché",
        ),
    },
    "service-trust": {
        "label": "Service trust ad",
        "summary": "service, course, or consulting recommendation visual that communicates trust and transformation.",
        "bestFor": ("service",),
        "directives": (
            "Show the before-to-after value through organized work artifacts, learning materials, or client workflow.",
            "Use human presence only as non-identifiable hands or silhouettes; keep trust cues concrete.",
            "Avoid guaranteed outcome visuals and cliché handshake scenes.",
        ),
        "composition": "structured workspace, before/after or plan/outcome cue, calm copy-safe area.",
        "palette": "warm professional neutrals with green or blue trust accents, not beige-only.",
        "lighting": "calm editorial light, clear materials, no dramatic hype.",
        "avoid": (
            "fake certificates",
            "guaranteed results",
            "handshake stock photo",
            "unrealistic transformation",
            "coach guru aesthetic",
        ),
    },
}

_ALIASES = {
    "auto": "auto",
    "default": "auto",
    "ad": "ad-cover",
    "ads": "ad-cover",
    "ad-cover": "ad-cover",
    "xhs": "xhs-lifestyle",
    "xiaohongshu": "xhs-lifestyle",
    "xhs-lifestyle": "xhs-lifestyle",
    "food": "food-local",
    "restaurant": "food-local",
    "local-food": "food-local",
    "food-local": "food-local",
    "product": "product-hero",
    "product-hero": "product-hero",
    "event": "event-poster",
    "event-poster": "event-poster",
    "saas": "b2b-saas",
    "software": "b2b-saas",
    "b2b": "b2b-saas",
    "b2b-saas": "b2b-saas",
    "research": "research-editorial",
    "paper": "research-editorial",
    "research-editorial": "research-editorial",
    "service": "service-trust",
    "course": "service-trust",
    "service-trust": "service-trust",
}

_KIND_DEFAULTS = {
    "software": "b2b-saas",
    "local_food": "food-local",
    "product": "product-hero",
    "event": "event-poster",
    "service": "service-trust",
    "research": "research-editorial",
    "general": "ad-cover",
}

_PLATFORM_EXTRA = {
    "xhs": (
        "Make it feel native to a Xiaohongshu cover: strong mobile crop, tactile subject, bright title-safe area.",
        "The first 0.5 seconds should communicate category and desire without reading text.",
    ),
    "xiaohongshu": (
        "Make it feel native to a Xiaohongshu cover: strong mobile crop, tactile subject, bright title-safe area.",
        "The first 0.5 seconds should communicate category and desire without reading text.",
    ),
    "wechat": (
        "Make it calm and trustworthy enough for a WeChat article cover or Moments share preview.",
        "Favor centered balance and fewer small details because the preview may be small.",
    ),
    "twitter": (
        "Make the silhouette read instantly in a fast-moving X/Twitter feed.",
        "Use high contrast and one bold visual hook; avoid slow-to-parse details.",
    ),
    "x": (
        "Make the silhouette read instantly in a fast-moving X/Twitter feed.",
        "Use high contrast and one bold visual hook; avoid slow-to-parse details.",
    ),
    "linkedin": (
        "Make it boardroom-presentable: professional, credible, and evidence-led.",
        "Use refined structure and practical work context over playful creator aesthetics.",
    ),
    "zhihu": (
        "Make it analytical and credible, with method or evidence as the visual center.",
        "Avoid entertainment-poster drama; prefer clean explanatory editorial styling.",
    ),
    "producthunt": (
        "Make the product value obvious at launch-card size.",
        "Prioritize crisp product reveal, maker energy, and a simple memorable object.",
    ),
}


def list_image_skills() -> list[str]:
    """Return stable image skill names."""
    return sorted(_SKILLS)


def resolve_image_skill(
    *,
    requested: str | None = None,
    recommendation_kind: str = "general",
    platform: str | None = None,
) -> dict[str, Any]:
    """Resolve an explicit or automatic image creative skill."""
    raw = (requested or "auto").strip().lower()
    name = _ALIASES.get(raw, raw)
    if name == "auto":
        if platform and platform.lower() in {"xhs", "xiaohongshu"} and recommendation_kind in {"general", "local_food", "product", "service"}:
            name = "xhs-lifestyle"
        else:
            name = _KIND_DEFAULTS.get(recommendation_kind, "ad-cover")
    if name not in _SKILLS:
        name = _KIND_DEFAULTS.get(recommendation_kind, "ad-cover")
    skill = dict(_SKILLS[name])
    skill["name"] = name
    return skill


def image_skill_prompt_lines(skill: dict[str, Any], *, platform: str) -> list[str]:
    """Format a resolved image skill into prompt directives."""
    platform_key = platform.lower().strip()
    lines = [
        f"Creative skill: {skill['name']} ({skill['label']}) - {skill['summary']}",
        f"Skill composition: {skill['composition']}",
        f"Skill palette: {skill['palette']}",
        f"Skill lighting: {skill['lighting']}",
    ]
    lines.extend(f"Skill directive: {item}" for item in skill["directives"])
    lines.extend(f"Platform skill note: {item}" for item in _PLATFORM_EXTRA.get(platform_key, ()))
    lines.append(f"Skill negative constraints: avoid {', '.join(skill['avoid'])}.")
    return lines

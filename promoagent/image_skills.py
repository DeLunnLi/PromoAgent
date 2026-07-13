"""Reusable creative skills for ad image generation."""
from __future__ import annotations

import json
from typing import Any


_GLOBAL_CRAFT = (
    "Put canvas/aspect ratio and layout contract before decorative detail.",
    "Use concrete scene nouns and visible subsystems instead of vague quality adjectives.",
    "Separate materials, lighting, palette, composition, and output checks.",
    "Treat the copy-safe zone as a hard subject-exclusion zone, not optional empty space.",
    "Keep readable marketing copy out of the model image; PromoAgent renders final text locally.",
    "Make each variant test a different hook hypothesis, not just a color or camera change.",
)

_SKILLS: dict[str, dict[str, Any]] = {
    "ad-cover": {
        "label": "Real ad cover",
        "summary": "commercial campaign key visual with one strong promise, one hero subject, and obvious conversion intent.",
        "bestFor": ("general", "software", "service", "product"),
        "referenceRoute": ("Typography & Posters", "Product & Food", "Brand Systems & Identity"),
        "promptMode": "commercial-poster-spec",
        "visual_reference": "Apple keynote product reveal photography; Stripe landing page hero imagery",
        "directives": (
            "Start from a real paid-ad layout: desire hook, proof cue, and clean CTA-safe space.",
            "Make the subject feel photographed or art-directed, not pasted into a template.",
            "Use one conversion object in the scene, such as a product, workflow outcome, venue moment, or document result.",
        ),
        "schema": {
            "artifact": "paid-ad campaign key visual",
            "layout_contract": "hero-first poster with reserved overlay zone and clear conversion path",
            "hierarchy": ["hero subject", "proof cue", "CTA-safe space", "supporting context", "depth layer"],
            "scene_nouns": ["hero object", "proof artifact", "surface texture", "soft shadow", "accent prop", "rim light edge", "negative space gradient", "material micro-detail"],
            "quality_checks": ["thumbnail-readable", "not template-like", "one strong promise visible without text", "believable material depth"],
            "visual_reference": "Apple keynote product reveal photography; Stripe landing page hero imagery",
        },
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
        "referenceRoute": ("Beauty & Lifestyle", "Product & Food", "Typography & Posters"),
        "promptMode": "mobile-lifestyle-cover-spec",
        "visual_reference": "Xiaohongshu top creator cover photography; Kinfolk magazine lifestyle editorial",
        "directives": (
            "Prioritize a close, tactile first-person discovery moment that can stop a mobile feed scroll.",
            "Keep the top area bright and simple for local Chinese overlay text.",
            "Use believable lifestyle context: hand-scale objects, table texture, neighborhood light, or real use scenario.",
        ),
        "schema": {
            "artifact": "Xiaohongshu mobile recommendation cover",
            "layout_contract": "portrait feed cover with bright top overlay zone and tactile lower hero",
            "hierarchy": ["desire object", "real-use context", "creator proof cue", "negative space", "foreground bokeh"],
            "scene_nouns": ["hand-scale prop", "table texture", "window light", "foreground detail", "neighborhood cue", "warm skin tone hint", "material grain", "shallow depth blur"],
            "quality_checks": ["mobile-scroll-stopping", "not corporate", "real creator post energy", "tactile texture visible at feed size"],
            "visual_reference": "Xiaohongshu top creator cover photography; Kinfolk magazine lifestyle editorial",
        },
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
        "referenceRoute": ("Product & Food", "Beauty & Lifestyle", "Typography & Posters"),
        "promptMode": "food-photography-config",
        "visual_reference": "Bon Appétit magazine food photography; Michelin guide restaurant editorial",
        "directives": (
            "Make the food or venue detail the unmistakable hero, with texture that looks edible and fresh.",
            "Suggest a real discovery context through tableware, storefront light, queue hint, or neighborhood atmosphere.",
            "Use ad composition, but keep it trustworthy and experience-led rather than discount-led.",
        ),
        "schema": {
            "artifact": "local food discovery ad cover",
            "layout_contract": "close food hero with diagonal depth and clean overlay zone",
            "hierarchy": ["hero dish", "steam or gloss", "tableware context", "venue atmosphere", "overlay-safe zone"],
            "scene_nouns": ["dish surface", "rising steam", "glossy sauce", "fresh ingredient", "bowl or plate edge", "chopstick rest", "table condiment", "warm storefront glow"],
            "quality_checks": ["appetizing texture", "credible venue", "no fake menu/prices", "edible-looking freshness"],
            "visual_reference": "Bon Appétit magazine food photography; Michelin guide restaurant editorial",
        },
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
        "referenceRoute": ("Product & Food", "Beauty & Lifestyle", "Brand Systems & Identity"),
        "promptMode": "product-render-config",
        "visual_reference": "Apple product photography; Bang & Olufsen product hero shots; Dyson launch imagery",
        "directives": (
            "Show one clear product hero with believable scale, material detail, and a visible use scenario.",
            "Use supporting props only when they explain the product value or strengthen desire.",
            "Make it look like an e-commerce or launch campaign image without fake discounts or fake brand marks.",
        ),
        "schema": {
            "artifact": "premium product campaign render",
            "layout_contract": "hero product at 55-70% visual weight with negative space for copy",
            "hierarchy": ["hero product", "material detail", "use-case prop", "negative space", "reflection control"],
            "scene_nouns": ["product surface finish", "edge chamfer", "controlled reflection", "micro texture", "studio surface", "use-case prop", "background gradient", "soft drop shadow"],
            "quality_checks": ["real scale", "no CGI tell", "no fake trademark", "desire visible without copy", "believable material weight"],
            "visual_reference": "Apple product photography; Bang & Olufsen product hero shots; Dyson launch imagery",
        },
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
        "referenceRoute": ("Typography & Posters", "Events & Experience", "Photography"),
        "promptMode": "event-campaign-poster-spec",
        "visual_reference": "TED conference stage photography; Web Summit event key visuals",
        "directives": (
            "Show a credible event moment with stage, workshop table, screen glow, or engaged attendee silhouettes.",
            "Make the viewer understand why attending matters without inventing names, dates, sponsors, or numbers.",
            "Leave a clear information zone for local overlay text and CTA.",
        ),
        "schema": {
            "artifact": "event recruitment campaign poster",
            "layout_contract": "venue focal point plus attendee-fit cue and overlay-safe info zone",
            "hierarchy": ["venue moment", "participation cue", "time-sensitive energy", "CTA-safe area", "audience silhouette"],
            "scene_nouns": ["stage glow", "workshop table", "screen light", "lanyard detail", "city evening", "venue architecture", "crowd energy blur", "nametag close-up"],
            "quality_checks": ["credible event", "not empty room", "no fake sponsor or speaker names", "atmosphere conveys value"],
            "visual_reference": "TED conference stage photography; Web Summit event key visuals",
        },
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
        "referenceRoute": ("UI/UX Mockups", "Screen Photography", "Research Paper Figures"),
        "promptMode": "saas-product-spec",
        "visual_reference": "Linear app launch imagery; Vercel dashboard product shots; Notion workspace photography",
        "directives": (
            "Translate the tool's job-to-be-done into a concrete workflow scene: inputs, processing, and publish-ready output.",
            "Show product value through abstract UI fragments and real work artifacts, not fake dashboards full of numbers.",
            "Keep it polished enough for LinkedIn or Product Hunt while preserving maker energy.",
        ),
        "schema": {
            "artifact": "B2B SaaS launch visual",
            "layout_contract": "workflow scene with input artifacts, processing center, and output cards",
            "hierarchy": ["central workflow object", "input artifacts", "output cards", "copy-safe zone", "device context"],
            "scene_nouns": ["abstract product panel", "source document cards", "channel output cards", "status chips", "desk surface", "monitor glow", "keyboard edge", "soft device shadow"],
            "quality_checks": ["product value legible", "no fake metrics", "not a generic startup office", "workflow direction clear"],
            "visual_reference": "Linear app launch imagery; Vercel dashboard product shots; Notion workspace photography",
        },
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
        "referenceRoute": ("Research Paper Figures", "Data Visualization", "Infographics & Field Guides"),
        "promptMode": "research-diagram-grammar",
        "visual_reference": "Nature journal cover art; MIT Technology Review editorial illustration",
        "directives": (
            "Make the document, figure, dataset, or method artifact the hero instead of using a vague sci-fi metaphor.",
            "Use simplified charts or diagrams as texture only; do not invent readable values.",
            "Signal credibility with clean editorial layout, precise geometry, and restrained contrast.",
        ),
        "schema": {
            "artifact": "research/document editorial cover",
            "layout_contract": "document hero plus small evidence panels, arrows, legend shapes, and clean copy-safe area",
            "hierarchy": ["document hero", "evidence panels", "diagram texture", "copy-safe area", "legend space"],
            "scene_nouns": ["paper page", "method blocks", "dataset card", "small chart texture", "thin arrows", "panel labels", "muted legend", "white paper space"],
            "quality_checks": ["publication credible", "labels abstract or local overlay only", "no fake institution", "method clarity visible"],
            "visual_reference": "Nature journal cover art; MIT Technology Review editorial illustration",
        },
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
        "referenceRoute": ("Typography & Posters", "UI/UX Mockups", "Beauty & Lifestyle"),
        "promptMode": "service-transformation-spec",
        "visual_reference": "Harvard Business Review editorial photography; Coursera course cover design",
        "directives": (
            "Show the before-to-after value through organized work artifacts, learning materials, or client workflow.",
            "Use human presence only as non-identifiable hands or silhouettes; keep trust cues concrete.",
            "Avoid guaranteed outcome visuals and cliché handshake scenes.",
        ),
        "schema": {
            "artifact": "service/course trust ad",
            "layout_contract": "before-to-after or plan-to-outcome scene with calm overlay space",
            "hierarchy": ["transformation contrast", "trust artifacts", "workspace context", "overlay-safe zone", "progress indicator"],
            "scene_nouns": ["organized worksheet", "calendar card", "progress marker", "client-safe silhouette", "learning material", "outcome preview", "messy-to-clear contrast", "calm desk surface"],
            "quality_checks": ["trustworthy", "no guaranteed outcome", "no coach-guru aesthetic", "transformation believable"],
            "visual_reference": "Harvard Business Review editorial photography; Coursera course cover design",
        },
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
    spec = {
        "prompt_mode": skill["promptMode"],
        "reference_route": list(skill["referenceRoute"]),
        **skill["schema"],
        "text_overlay_contract": "PromoAgent adds final typography locally; generated image must reserve a clean low-detail background zone only.",
        "subject_exclusion_contract": "No hero object, face, logo, QR code, UI focus, or high-contrast detail inside the copy-safe zone.",
        "variant_contract": "If variants are requested, change the audience hook or conversion hypothesis, not just colors.",
        "material": skill["composition"],
        "lighting": skill["lighting"],
        "palette": skill["palette"],
    }
    lines = [
        f"Creative skill: {skill['name']} ({skill['label']}) - {skill['summary']}",
        "Skill craft model: reference-gallery-inspired structured prompt, not a bare descriptive paragraph.",
        "Skill craft checklist: " + " ".join(_GLOBAL_CRAFT),
    ]
    # Visual reference gives the model a concrete style benchmark.
    visual_ref = skill.get("visual_reference") or skill.get("schema", {}).get("visual_reference")
    if visual_ref:
        lines.append(f"Visual reference: {visual_ref}")
    lines.extend([
        "PROMO_RENDER_SPEC:",
        json.dumps(spec, ensure_ascii=False, indent=2),
        "Promotional hierarchy: first glance = subject/category; second glance = value promise; third glance = texture, proof cues, and platform-native detail.",
        "Ad-tool benchmark: URL-to-ad workflow, platform-native creative, brand-safe background, and clear A/B-testing intent.",
        "Overlay production contract: final words are a separate local typography layer; the model image should behave like a premium background plate.",
    ])
    lines.extend(f"Skill directive: {item}" for item in skill["directives"])
    lines.extend(f"Platform skill note: {item}" for item in _PLATFORM_EXTRA.get(platform_key, ()))
    lines.append(f"Skill negative constraints: avoid {', '.join(skill['avoid'])}.")
    return lines

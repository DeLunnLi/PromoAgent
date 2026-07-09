"""Image generation and extraction for Source2Launch.

Two image sources:
1. README visual URLs  — download existing screenshots from the project
2. AI image model     — generate a cover image from project evidence
   Supported providers:
   - OpenAI  (gpt-image-2, dall-e-3): synchronous, returns base64 or URL
   - ModelScope (Qwen/Qwen-Image):    async task + polling
"""
from __future__ import annotations

import base64
import colorsys
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .image_skills import image_skill_prompt_lines, list_image_skills, resolve_image_skill

# ---------------------------------------------------------------------------
# Platform dimensions — derived from format, configurable via env
# ---------------------------------------------------------------------------

# Format → (width, height) for ModelScope
_FORMAT_DIMS = {
    "portrait":  (1024, 1536),
    "square":    (1024, 1024),
    "landscape": (1536, 1024),
}

# Format → size string for OpenAI
_FORMAT_OPENAI_SIZES = {
    "portrait":  "1024x1536",
    "square":    "1024x1024",
    "landscape": "1536x1024",
}


def _platform_format(platform: str, env: dict[str, str] | None = None) -> str:
    """Determine image format (portrait/square/landscape) from platform name.

    Configurable: PROMOAGENT_IMAGE_FORMAT=portrait overrides per-platform logic.
    """
    env = env or os.environ
    override = env.get("PROMOAGENT_IMAGE_FORMAT", "").lower().strip()
    if override in _FORMAT_DIMS:
        return override

    p = platform.lower()
    if any(k in p for k in ("xhs", "xiaohongshu", "red", "vertical")):
        return "portrait"
    if any(k in p for k in ("wechat", "moments", "weixin", "square")):
        return "square"
    return "landscape"   # default for Twitter, LinkedIn, zhihu, etc.


def _platform_dims(platform: str, env: dict[str, str] | None = None) -> tuple[int, int]:
    fmt = _platform_format(platform, env)
    return _FORMAT_DIMS.get(fmt, (1024, 1024))


def _platform_openai_size(platform: str, env: dict[str, str] | None = None) -> str:
    fmt = _platform_format(platform, env)
    return _FORMAT_OPENAI_SIZES.get(fmt, "1024x1024")

def _safe_platform_slug(platform: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", platform.lower()).strip("-")
    return slug or "platform"


def _smart_default_platforms(result: dict[str, Any]) -> list[str]:
    """Choose default platforms based on project type and language."""
    project = result.get("project", {})
    topics = project.get("topics") or []
    desc = project.get("description", "")
    name = project.get("name", "")
    combined = " ".join([name, desc, *topics]).lower()

    # Check if project is Chinese-oriented
    chinese_indicators = ["中文", "简体", "繁体", "国内", "中国", "微信", "小程序", "抖音"]
    is_chinese = any(ind in combined for ind in chinese_indicators)

    # Check project type
    if any(k in combined for k in ["food", "restaurant", "coffee", "美食", "餐厅", "咖啡"]):
        return ["xhs", "wechat"] if is_chinese else ["twitter", "linkedin"]
    elif any(k in combined for k in ["app", "tool", "cli", "软件", "工具", "开源"]):
        return ["xhs", "zhihu"] if is_chinese else ["twitter", "linkedin", "producthunt"]
    elif any(k in combined for k in ["research", "paper", "论文", "研究", "学术"]):
        return ["zhihu", "wechat"] if is_chinese else ["linkedin", "twitter"]
    elif any(k in combined for k in ["event", "活动", "大会", "会议"]):
        return ["xhs", "wechat"] if is_chinese else ["twitter", "linkedin"]

    # Default based on language
    return ["xhs", "wechat"] if is_chinese else ["twitter", "linkedin"]


def _image_platforms(options: dict[str, Any], env: dict[str, str], result: dict[str, Any] | None = None) -> list[str]:
    raw = options.get("platforms") or env.get("PROMOAGENT_IMAGE_PLATFORMS")

    # If no explicit platforms, use smart defaults based on project
    if not raw and result:
        return _smart_default_platforms(result)

    if not raw:
        raw = "xhs,wechat"

    if isinstance(raw, str):
        values = re.split(r"[,;\s]+", raw)
    else:
        values = [str(v) for v in raw]

    platforms: list[str] = []
    seen: set[str] = set()
    for value in values:
        platform = value.strip().lower()
        if platform and platform not in seen:
            platforms.append(platform)
            seen.add(platform)
    return platforms or ["xhs", "wechat"]


DEFAULT_OPENAI_BASE  = "https://api.openai.com/v1"
DEFAULT_MODELSCOPE_BASE = "https://api-inference.modelscope.cn/v1"
DEFAULT_IMAGE_MODEL  = "Qwen/Qwen-Image"
FETCH_TIMEOUT = 15
# Cap upstream API error bodies surfaced in exceptions. Provider responses can
# echo request metadata or prompt fragments; keep enough to debug, never the
# full body. Also strips newlines so multi-line responses stay on one log line.
_ERROR_BODY_LIMIT = 200


def _sanitize_error_body(body: str) -> str:
    """Trim and flatten an upstream API error response for safe logging."""
    text = " ".join(str(body or "").split())
    return text[:_ERROR_BODY_LIMIT] + ("…" if len(text) > _ERROR_BODY_LIMIT else "")


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------

def _is_openai_model(model: str) -> bool:
    """Return True if the model should use the OpenAI synchronous Images API."""
    return bool(re.search(r"gpt-image|dall-e|gpt-4o", model, re.I))


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def image_config(options: dict[str, Any] | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Read image generation configuration from options and environment."""
    options = options or {}
    env = os.environ if env is None else env

    model = (
        options.get("model")
        or env.get("PROMOAGENT_IMAGE_MODEL")
        or DEFAULT_IMAGE_MODEL
    )

    # API key: OpenAI models prefer OPENAI_API_KEY; ModelScope prefers MODELSCOPE key
    if _is_openai_model(model):
        api_key = (
            options.get("api_key")
            or env.get("PROMOAGENT_IMAGE_API_KEY")
            or env.get("OPENAI_API_KEY")
            or env.get("PROMOAGENT_API_KEY")
        )
        default_base = DEFAULT_OPENAI_BASE
    else:
        api_key = (
            options.get("api_key")
            or env.get("PROMOAGENT_IMAGE_API_KEY")
            or env.get("PROMOAGENT_MODELSCOPE_API_KEY")
            or env.get("PROMOAGENT_API_KEY")
            or env.get("MODELSCOPE_API_KEY")
        )
        default_base = DEFAULT_MODELSCOPE_BASE

    base_url = (
        options.get("base_url")
        or env.get("PROMOAGENT_IMAGE_BASE_URL")
        or env.get("PROMOAGENT_BASE_URL")
        or default_base
    ).rstrip("/")

    return {
        "apiKey": api_key,
        "baseUrl": base_url,
        "model": model,
        "quality": options.get("quality") or env.get("PROMOAGENT_IMAGE_QUALITY") or "medium",
        "size": options.get("size") or env.get("PROMOAGENT_IMAGE_SIZE"),
        "pollIntervalMs": int(options.get("poll_interval_ms") or env.get("PROMOAGENT_IMAGE_POLL_MS") or 4000),
        "timeoutMs": int(options.get("timeout_ms") or env.get("PROMOAGENT_IMAGE_TIMEOUT_MS") or 180_000),
    }


def has_image_key(env: dict[str, str] | None = None) -> bool:
    env = os.environ if env is None else env
    return bool(
        env.get("PROMOAGENT_IMAGE_API_KEY")
        or env.get("OPENAI_API_KEY")
        or env.get("PROMOAGENT_MODELSCOPE_API_KEY")
        or env.get("PROMOAGENT_API_KEY")
        or env.get("MODELSCOPE_API_KEY")
    )


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _combined_promo_text(result: dict[str, Any]) -> str:
    project = result.get("project", {})
    evidence = result.get("evidence", {})
    parts = [
        str(project.get("name", "")),
        str(project.get("description", "")),
        str(evidence.get("opening") or evidence.get("readmeOpening") or ""),
        " ".join(project.get("topics") or []),
        str(result.get("target", "")),
    ]
    return " ".join(part for part in parts if part).strip()


def _recommendation_kind(result: dict[str, Any]) -> str:
    """Classify what is being recommended without calling an LLM."""
    source = result.get("source", "")
    input_type = result.get("inputType", "")
    text = _combined_promo_text(result)

    if source in ("github", "local"):
        return "software"
    if source == "file" and input_type in ("pdf", "document"):
        return "research"

    if re.search(r"(餐厅|火锅|咖啡|奶茶|烧烤|烤肉|小吃|美食|人均|地址|探店|restaurant|cafe|coffee|brunch|hotpot|bar\b)", text, re.I):
        return "local_food"
    if re.search(r"(活动|展览|大会|会议|讲座|沙龙|门票|报名|周末|workshop|webinar|meetup|conference|event)", text, re.I):
        return "event"
    if re.search(r"(论文|研究|实验|数据集|基准|paper|study|research|dataset|benchmark|method)", text, re.I):
        return "research"
    if re.search(r"(github|repo|cli|sdk|api|developer|代码|开源|工具|模型|工作流|自动化|ai\b|app\b|software|agent)", text, re.I):
        return "software"
    if re.search(r"(课程|训练营|咨询|顾问|服务|方案|course|coaching|consulting|service|agency)", text, re.I):
        return "service"
    if re.search(r"(新品|电商|护肤|耳机|键盘|服装|价格|折扣|优惠|元|\$|product|shop|ecommerce|sale)", text, re.I):
        return "product"
    return "general"


def _recommendation_profile(kind: str) -> dict[str, str]:
    profiles = {
        "software": {
            "category": "software/tool recommendation",
            "angle": "developer productivity, evidence-to-output workflow, automation, and launch readiness.",
            "subject": "one hero device or product interface showing an abstract evidence-to-promotion workflow, with a few source cards flowing into finished content cards.",
            "scene": "premium maker desk or clean launch-control workspace; tangible documents, subtle interface panels, and abstract channel tiles without real logos.",
            "style": "premium SaaS launch photography mixed with restrained 3D product UI, cinematic but believable.",
            "avoid": "fake metrics, unreadable code dumps, generic stock-office scenes, robot mascots, toy-like dashboards, crowded app-card grids.",
        },
        "local_food": {
            "category": "restaurant/local lifestyle recommendation",
            "angle": "sensory appeal, discovery value, location-life context, and trustworthy recommendation energy.",
            "subject": "one appetite-first hero dish or table moment, supported by two or three real venue details that imply neighborhood discovery.",
            "scene": "warm real restaurant table, shallow depth of field, steam, authentic ingredients, evening city or storefront atmosphere.",
            "style": "premium lifestyle food photography, editorial composition, appetizing natural texture.",
            "avoid": "plastic-looking food, fake menu text, exaggerated crowds, misleading price tags, over-staged banquet layouts.",
        },
        "product": {
            "category": "consumer product recommendation",
            "angle": "clear product desirability, use scenario, value cues, and tactile quality.",
            "subject": "one clear hero product in a real use scenario, with material detail and a controlled set of supporting props.",
            "scene": "premium studio-meets-lifestyle setup, believable surface, reflections controlled, product function visible without explanatory text.",
            "style": "high-end product photography, crisp commercial lighting, tactile details.",
            "avoid": "fake brand logos, fake discounts, cluttered marketplace layouts, impossible product shapes, excessive glow.",
        },
        "event": {
            "category": "event/activity recommendation",
            "angle": "why attend, who it is for, time-sensitive energy, and social proof without fabricated numbers.",
            "subject": "one immersive venue moment with a clear stage or screen focal point and a small engaged audience seen from behind.",
            "scene": "credible event space, warm practical lighting, networking atmosphere, abstract agenda shapes with no readable text.",
            "style": "premium event key visual, cinematic lighting, clear focal point.",
            "avoid": "fake speaker names, fake dates, fake sponsor logos, overcrowded scenes, identifiable faces.",
        },
        "service": {
            "category": "service/course recommendation",
            "angle": "problem-solution fit, trust, transformation, and professional clarity.",
            "subject": "one clear client workflow or transformation metaphor, with before-and-after structure shown through abstract panels.",
            "scene": "calm consulting or learning workspace, realistic materials, organized notes, professional but human.",
            "style": "professional editorial visual, clean service design language, trustworthy lighting.",
            "avoid": "guaranteed outcomes, fake certificates, unrealistic transformations, handshake stock-photo clichés.",
        },
        "research": {
            "category": "research/document recommendation",
            "angle": "method clarity, evidence, insight, and credible takeaway.",
            "subject": "one research paper or document as the hero, with simplified evidence diagrams and analysis artifacts around it.",
            "scene": "clean research desk or editorial analysis spread, paper texture, precise diagram geometry, subtle data fragments.",
            "style": "analytical editorial cover, academic but accessible, precise visual hierarchy.",
            "avoid": "fake charts with numbers, fake institution logos, dense unreadable text, sci-fi lab clichés.",
        },
    }
    return profiles.get(kind, {
        "category": "general recommendation",
        "angle": "clear value, authentic context, and a platform-native reason to care.",
        "subject": "one concrete hero subject shown through a real use scenario and a clean support context.",
        "scene": "believable editorial promotional scene with real-world texture and clear visual hierarchy.",
        "style": "premium editorial promotional visual, polished and attractive.",
        "avoid": "fake claims, fake logos, clutter, watermarks, generic AI-generated decoration.",
    })


def _visual_text(value: Any, limit: int = 180) -> str:
    text = str(value or "")
    text = re.sub(r"[`*_#>\[\]()]|https?://\S+", " ", text)
    text = re.sub(r"[^\w\s\u4e00-\u9fff,.:;!?/+-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].strip()


def _copy_safe_geometry(platform: str) -> str:
    fmt = _platform_format(platform)
    if fmt == "portrait":
        return "Reserve a clean top 25-30% copy-safe zone as a hard subject-exclusion area: no hero objects, faces, logos, UI focus, or strong detail."
    if fmt == "landscape":
        return "Reserve one side as a clean 40-45% copy-safe zone as a hard subject-exclusion area; keep the hero subject on the opposite side."
    return "Reserve a clean compact upper-left 42-48% wide copy-safe zone as a hard subject-exclusion area; keep the hero subject entirely center-right or lower-right, outside that text area."


def _layout_quality_contract(platform: str) -> str:
    fmt = _platform_format(platform)
    if fmt == "portrait":
        return (
            "Poster layout contract: top zone is quiet background for local title; lower two-thirds carries one oversized hero subject. "
            "Subject bounding box must not enter the title zone, even partially."
        )
    if fmt == "landscape":
        return (
            "Poster layout contract: one-side copy lane stays quiet and low-contrast; opposite side carries the hero subject with clear silhouette. "
            "Avoid centered subjects that would collide with local headline text."
        )
    return (
        "Poster layout contract: compact upper-left copy panel stays quiet and low-detail; hero subject lives center-right or lower-right. "
        "Avoid placing the subject, face, product label, or key UI inside the upper-left panel."
    )


def _bool_env(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


def _split_badges(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        raw = re.split(r"[,，;/|]+", str(value or ""))
    return [_visual_text(item, 18) for item in raw if _visual_text(item, 18)][:4]


def image_brief(
    result: dict[str, Any],
    *,
    options: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Resolve image ad brief from CLI options, environment, and source evidence."""
    options = options or {}
    env = env or os.environ
    project = result.get("project", {})
    title = (
        options.get("title")
        or env.get("PROMOAGENT_IMAGE_TITLE")
        or project.get("name")
        or "推荐"
    )
    subtitle = (
        options.get("subtitle")
        or env.get("PROMOAGENT_IMAGE_SUBTITLE")
        or project.get("description")
        or ""
    )
    cta = (
        options.get("cta")
        or env.get("PROMOAGENT_IMAGE_CTA")
        or project.get("cta")
        or project.get("installCommand")
        or ""
    )
    badges = options.get("badges") or env.get("PROMOAGENT_IMAGE_BADGES") or ""
    note = options.get("note") or env.get("PROMOAGENT_IMAGE_BRIEF") or ""
    overlay = _bool_env(
        options.get("text_overlay", env.get("PROMOAGENT_IMAGE_TEXT_OVERLAY")),
        default=True,
    )
    return {
        "title": _visual_text(title, 40),
        "subtitle": _visual_text(subtitle, 90),
        "cta": _visual_text(cta, 36),
        "badges": _split_badges(badges),
        "note": _visual_text(note, 220),
        "textOverlay": overlay,
    }


def ask_image_brief_interactively(result: dict[str, Any], options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Collect ad-image direction in a terminal session."""
    options = dict(options or {})
    if not sys.stdin.isatty():
        return options

    current = image_brief(result, options=options)
    skill_default = options.get("skill") or os.environ.get("PROMOAGENT_IMAGE_SKILL") or "auto"
    skill_choices = ", ".join(["auto", *list_image_skills()])
    print("\n✦ 交互式广告生图 brief（直接回车使用默认值）", file=sys.stderr)
    prompts = [
        ("skill", f"创意 skill（{skill_choices}）", skill_default),
        ("title", "广告标题", current.get("title", "")),
        ("subtitle", "副标题/核心卖点", current.get("subtitle", "")),
        ("cta", "CTA 按钮文案", current.get("cta", "")),
        ("badges", "角标/卖点标签（逗号分隔）", "，".join(current.get("badges", []))),
        ("note", "视觉方向（例如：更像小红书真实探店封面/高端产品广告/强转化电商风）", current.get("note", "")),
    ]
    for key, label, default in prompts:
        suffix = f" [{default}]" if default else ""
        try:
            value = input(f"  {label}{suffix}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n（跳过剩余图片 brief，继续生成）", file=sys.stderr)
            break
        if value:
            options[key] = value
    options["text_overlay"] = True
    return options


def _is_chinese_model(model: str) -> bool:
    """Detect if the model is a Chinese model that prefers Chinese prompts."""
    chinese_patterns = [r"qwen", r"通义", r"文心", r"智谱", r"glm", r"baichuan", r"chatglm", r"modelscope"]
    model_lower = model.lower()
    return any(re.search(p, model_lower) for p in chinese_patterns)


def _build_chinese_prompt(
    result: dict[str, Any],
    platform: str,
    style: str,
    skill: dict[str, Any],
    brief: dict[str, Any],
    variant: int,
) -> str:
    """Build a Chinese prompt optimized for Chinese image models like Qwen."""
    project = result.get("project", {})
    name = project.get("name", "项目")
    desc = project.get("description", "")
    kind = _recommendation_kind(result)

    platform_cn = {
        "xhs": "小红书封面",
        "xiaohongshu": "小红书封面",
        "wechat": "微信公众号封面",
        "zhihu": "知乎头图",
        "twitter": "Twitter卡片",
        "x": "X卡片",
        "linkedin": "LinkedIn横幅",
        "producthunt": "Product Hunt发布图",
    }.get(platform.lower(), "推广图片")

    # Simplified skill mapping for Chinese prompts
    skill_desc = {
        "ad-cover": "专业广告封面，一个醒目的主视觉主体，干净的背景留出文字空间",
        "xhs-lifestyle": "小红书风格生活分享图，真实自然的场景，温暖的色调，顶部留白给标题",
        "food-local": "美食探店图，诱人的食物特写，真实的餐厅环境，温暖的灯光",
        "product-hero": "产品展示图，精致的产品特写，简洁的背景，突出产品质感",
        "event-poster": "活动海报，有氛围感的场景，清晰的空间感，专业灯光",
        "b2b-saas": "B2B软件产品图，现代办公场景，抽象界面元素，专业商务风格",
        "research-editorial": "学术编辑风格，简洁的几何图形，论文或文档元素，知性配色",
        "service-trust": "服务信任图，整洁的工作场景，前后对比或进度展示，温暖专业",
    }.get(skill.get("name", ""), "专业推广图片，一个清晰的主视觉，干净的背景")

    variant_desc = ""
    if variant > 1:
        variants = [
            "直接展示产品/体验，突出核心卖点",
            "问题到解决方案的视觉隐喻，强调对比",
            "生活方式角度，更强的情感共鸣",
            "高端品牌视觉，大胆的留白和记忆点",
        ]
        variant_desc = f"\n变体风格：{variants[(variant - 1) % len(variants)]}"

    # User creative direction
    ad_note = brief.get("note", "")
    note_part = f"\n用户特别要求：{ad_note}" if ad_note else ""

    # Platform-specific Chinese instructions
    platform_notes = {
        "xhs": "\n小红书风格要点：竖版3:4比例，顶部30%区域保持简洁明亮（留给标题文字），主体占据下方2/3，真实质感，浅景深，生活化场景。",
        "xiaohongshu": "\n小红书风格要点：竖版3:4比例，顶部30%区域保持简洁明亮（留给标题文字），主体占据下方2/3，真实质感，浅景深，生活化场景。",
        "wechat": "\n微信封面要点：方形1:1比例，居中构图，简洁大气，可信赖感，细节清晰。",
        "zhihu": "\n知乎头图要点：横版16:9比例，分析性、可信感，方法或证据导向，简洁编辑风格。",
        "twitter": "\nTwitter卡片要点：横版比例，高对比度，简洁有力，在信息流中一眼可辨。",
        "x": "\nX卡片要点：横版比例，高对比度，简洁有力，在信息流中一眼可辨。",
        "linkedin": "\nLinkedIn横幅要点：专业商务风格，B2B导向，精致结构化，办公场景。",
    }.get(platform.lower(), "")

    prompt = f"""为"{name}"创建一张{platform_cn}。

核心要求：
- {skill_desc}
- 项目描述：{desc[:100] if desc else "一个值得推荐的优质项目"}
- 风格：精致、现代、专业级广告质感
{platform_notes}

构图要求：
- 一个明确的主视觉主体，不要多个分散的元素
- 清晰的前景-中景-背景层次感
- 预留文字叠加区域，该区域不要有重要视觉元素
- 不要使用 collage 拼贴风格

视觉规范：
- 光线：精致的工作室灯光或自然光，清晰的边缘，可信的阴影
- 配色：以中性色为基底，搭配1-2个点缀色，避免彩虹色或霓虹色
- 材质：真实的材质质感，控制反射，有深度的画面
- 情绪：积极、精致、乐观、电影感但真实可信

禁止事项：
- 不要生成可读的文字、字母、二维码、价格标签
- 不要出现真实的品牌logo、应用图标、社交媒体logo
- 不要拥挤的图标堆砌、虚假的仪表盘、机器人吉祥物
- 不要像AI生成的装饰性图案
{variant_desc}{note_part}

目标：看起来像资深艺术总监制作的 campaign 背景图，准备好让设计师添加文字，而不是图片模型自己尝试绘制文字的海报。"""

    return prompt


def build_image_prompt(
    result: dict[str, Any],
    *,
    platform: str = "xhs",
    style: str = "clean",
    skill: str | None = None,
    brief: dict[str, Any] | None = None,
    variant: int = 1,
    variant_count: int = 1,
    model: str = "",
) -> str:
    """Build an image generation prompt from project evidence."""
    project = result.get("project", {})
    evidence = result.get("evidence", {})
    name = project.get("name", "Project")
    desc = project.get("description", "")
    topics = project.get("topics") or []
    cta = project.get("cta") or project.get("installCommand", "")
    kind = _recommendation_kind(result)
    profile = _recommendation_profile(kind)

    platform_key = platform.lower().strip()

    # Check if we should use Chinese prompt
    effective_model = model or os.environ.get("PROMOAGENT_IMAGE_MODEL", "")
    if _is_chinese_model(effective_model):
        creative_skill = resolve_image_skill(requested=skill, recommendation_kind=kind, platform=platform_key)
        brief = brief or {}
        return _build_chinese_prompt(result, platform, style, creative_skill, brief, variant)

    # Original English prompt logic for non-Chinese models
    platform_guides = {
        "xhs": {
            "format": "vertical 3:4 poster",
            "fit": "Xiaohongshu-style mobile cover: scroll-stopping, tactile, creator-friendly, strong first-screen impact.",
            "composition": "portrait layout, one large foreground hero subject in the lower two-thirds, rich real texture, bright clean top 25% reserved for title overlay.",
            "camera": "close editorial camera angle, shallow depth of field, strong foreground/background separation.",
            "density": "highly curated: one hero subject plus at most three support elements; no collage wall.",
        },
        "xiaohongshu": {
            "format": "vertical 3:4 poster",
            "fit": "Xiaohongshu-style mobile cover: scroll-stopping, tactile, creator-friendly, strong first-screen impact.",
            "composition": "portrait layout, one large foreground hero subject in the lower two-thirds, rich real texture, bright clean top 25% reserved for title overlay.",
            "camera": "close editorial camera angle, shallow depth of field, strong foreground/background separation.",
            "density": "highly curated: one hero subject plus at most three support elements; no collage wall.",
        },
        "wechat": {
            "format": "square 1:1 card",
            "fit": "WeChat article cover: polished, trustworthy, easy to scan in a feed.",
            "composition": "balanced square layout, centered hero subject, calm negative space, refined editorial cover structure.",
            "camera": "stable product/editorial camera angle, soft premium lighting, clean edges.",
            "density": "medium-low density; avoid small details that disappear in feed previews.",
        },
        "zhihu": {
            "format": "wide 16:9 header image",
            "fit": "Zhihu answer/article header: analytical, credible, method-oriented.",
            "composition": "wide header with one clear reasoning/evidence metaphor, restrained and informative, generous left or right copy-safe area.",
            "camera": "clean editorial angle, precise lines, no flashy entertainment styling.",
            "density": "medium density; structured but not diagram-heavy.",
        },
        "twitter": {
            "format": "wide Twitter/X card",
            "fit": "Twitter/X launch card: high contrast, concise, energetic, instantly legible.",
            "composition": "landscape card with one bold product scene, strong diagonal energy, large readable shapes, copy-safe area on one side.",
            "camera": "dynamic wide angle, dramatic contrast, clear silhouette.",
            "density": "low-medium density; one visual hook that reads at thumbnail size.",
        },
        "x": {
            "format": "wide Twitter/X card",
            "fit": "Twitter/X launch card: high contrast, concise, energetic, instantly legible.",
            "composition": "landscape card with one bold product scene, strong diagonal energy, large readable shapes, copy-safe area on one side.",
            "camera": "dynamic wide angle, dramatic contrast, clear silhouette.",
            "density": "low-medium density; one visual hook that reads at thumbnail size.",
        },
        "linkedin": {
            "format": "wide LinkedIn banner",
            "fit": "LinkedIn B2B banner: professional, evidence-led, polished for founders and teams.",
            "composition": "landscape banner with professional hero workflow, source evidence, outcome preview, and clean enterprise polish.",
            "camera": "premium B2B editorial angle, calm depth, tasteful contrast.",
            "density": "medium density; sophisticated and structured, not playful.",
        },
        "producthunt": {
            "format": "wide launch banner",
            "fit": "Product Hunt launch visual: crisp product-first hero, maker-friendly, immediately understandable.",
            "composition": "wide hero with a focused product centerpiece, simple launch-day energy, and clean copy-safe area.",
            "camera": "crisp product hero angle with bright launch lighting.",
            "density": "low-medium density; product-first, not decorative.",
        },
    }
    guide = platform_guides.get(platform_key, {
        "format": "square card",
        "fit": "platform-native promotional image.",
        "composition": "clean promotional composition with a clear subject and room for optional overlay text.",
        "camera": "editorial camera angle with polished lighting.",
        "density": "one hero subject plus limited supporting detail.",
    })
    creative_skill = resolve_image_skill(requested=skill, recommendation_kind=kind, platform=platform_key)
    skill_lines = image_skill_prompt_lines(creative_skill, platform=platform_key)

    topic_str = ", ".join(topics[:4]) if topics else profile["category"]
    display_name = _visual_text(name, 80) or "Project"
    desc_short = _visual_text(desc, 140) or "provided source evidence"
    cta_hint = f"Call to action cue: {_visual_text(cta, 100)}. " if cta else ""
    headings = evidence.get("headings") or []
    feature_hints = [_visual_text(h.get("text"), 70) for h in headings if isinstance(h, dict) and h.get("level") == 2]
    feature_hints = [h for h in feature_hints if h][:3]
    feature_str = ", ".join(feature_hints) if feature_hints else profile["subject"]
    brief = brief or {}
    ad_note = brief.get("note") or ""
    overlay_title = brief.get("title") or display_name
    overlay_subtitle = brief.get("subtitle") or desc_short
    overlay_cta = brief.get("cta") or _visual_text(cta, 36)
    variant_line = ""
    if variant_count > 1:
        concepts = [
            "Concept A: direct product/experience hero with strong desire and clean proof cues.",
            "Concept B: problem-to-solution visual metaphor with more contrast and urgency.",
            "Concept C: platform-native lifestyle/editorial angle with stronger emotional pull.",
            "Concept D: premium brand key visual with bold negative space and one memorable object.",
        ]
        variant_line = concepts[(variant - 1) % len(concepts)]

    lines = [
        "Use case: ads-marketing",
        f"Recommendation category: {profile['category']}",
        f"Asset type: {guide['format']} for {platform_key}",
        f"Primary request: Create an ad-ready campaign visual for '{display_name}', not a generic illustration.",
        *skill_lines,
        f"Source context: {desc_short}",
        f"{cta_hint}Topics: {topic_str}. Recommendation angle: {profile['angle']}",
        f"Subject cues: {feature_str}.",
        f"Scene/backdrop: {profile['scene']}",
        f"Ad copy to reserve space for local overlay: headline '{overlay_title}', subhead '{overlay_subtitle}', CTA '{overlay_cta}'. Do not draw this text yourself.",
        f"Copy-safe geometry: {_copy_safe_geometry(platform_key)}",
        _layout_quality_contract(platform_key),
        f"Platform fit: {guide['fit']}",
        f"Style/medium: {style}, {profile['style']}",
        f"Composition/framing: {guide['composition']}",
        f"Camera/framing: {guide['camera']}",
        f"Visual density: {guide['density']}",
        "Quality bar: looks like a real campaign key visual made by a senior art director, not a generic AI demo image.",
        "Lighting/mood: attractive, refined, optimistic, cinematic but believable, crisp contrast, no clutter.",
        "Color palette: sophisticated multi-color accents with one dominant neutral base; avoid neon rainbow overload.",
        "Materials/textures: tactile real-world surfaces, controlled reflections, crisp edges, believable depth.",
        "Text: do not render readable words, pseudo-letters, QR codes, subtitles, captions, price tags, watermarks, or UI copy; leave clean space for separate local typography overlay.",
        "Brand safety: do not show real app logos, social media logos, company logos, trademarked icons, or recognizable brand marks; use abstract unlabeled rounded tiles instead.",
        "Composition rules: one unmistakable hero subject, clear foreground-midground-background separation, no tiny icon soup, no busy collage, no focal object under the reserved copy area.",
        "Ad creative objective: make it look like a finished campaign background plate ready for crisp designer-set typography, not a poster where the image model attempted the lettering.",
        f"Constraints: visually distinctive, premium, platform-appropriate. Avoid: {profile['avoid']}",
    ]
    if ad_note:
        lines.append(f"User creative direction: {ad_note}")
    if variant_line:
        lines.append(f"Variant direction: {variant_line}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ModelScope image generation
# ---------------------------------------------------------------------------

def generate_modelscope_image(
    prompt: str,
    *,
    output_path: str | Path,
    config: dict[str, Any],
    platform: str = "default",
) -> dict[str, Any]:
    """Submit an image generation task to ModelScope, poll, download the result."""
    api_key = config["apiKey"]
    base_url = config["baseUrl"]
    model = config["model"]
    poll_sec = config["pollIntervalMs"] / 1000
    timeout_sec = config["timeoutMs"] / 1000

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "PromoAgent/0.4",
    }

    # Derive dimensions from output filename (platform hint)
    out_stem = Path(output_path).stem.lower()
    width, height = _platform_dims(out_stem)

    # Prepare parameters optimized for Chinese models like Qwen
    # Use enhanced parameters for better quality
    request_body: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "width": width,
        "height": height,
    }

    # Add quality and style parameters for supported models
    if "qwen" in model.lower():
        # Qwen-specific optimizations for promotional images
        request_body["response_format"] = "url"
        # Optional: add seed for reproducibility if needed
        # request_body["seed"] = 42

    body = json.dumps(request_body).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/images/generations",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            task_data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = _sanitize_error_body(exc.read().decode("utf-8", errors="replace"))
        raise RuntimeError(f"Image API error {exc.code}: {detail}") from exc

    task_id = task_data.get("task_id") or task_data.get("id")
    if not task_id:
        raise RuntimeError(f"No task_id in response: {task_data}")

    # Poll for result
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        time.sleep(poll_sec)
        req = urllib.request.Request(
            f"{base_url}/tasks/{task_id}",
            headers={"Authorization": f"Bearer {api_key}", "User-Agent": "PromoAgent/0.4"},
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            status_data = json.loads(resp.read())

        status = status_data.get("task_status", "")
        if status == "SUCCEED":
            image_urls = status_data.get("output_images") or []
            if not image_urls:
                raise RuntimeError("Task succeeded but returned no output_images")
            image_url = image_urls[0]
            break
        if status in ("FAILED", "ERROR", "CANCELLED"):
            raise RuntimeError(f"Image generation failed: status={status}")
    else:
        raise RuntimeError(f"Image generation timed out after {config['timeoutMs']}ms")

    # Download
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(image_url, out)

    return {
        "provider": "modelscope",
        "model": model,
        "taskId": task_id,
        "outputPath": str(out),
        "width": width,
        "height": height,
        "platform": platform,
    }


# ---------------------------------------------------------------------------
# OpenAI image generation (gpt-image-2, dall-e-3 — synchronous)
# ---------------------------------------------------------------------------

def generate_openai_image(
    prompt: str,
    *,
    output_path: str | Path,
    config: dict[str, Any],
    platform: str = "default",
) -> dict[str, Any]:
    """Generate an image via OpenAI Images API (gpt-image-2, dall-e-3).

    Synchronous — response contains base64 JSON or a URL directly.
    """
    api_key = config["apiKey"]
    base_url = config["baseUrl"]
    model = config["model"]
    quality = config.get("quality", "medium")
    size = config.get("size") or _platform_openai_size(platform)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "PromoAgent/0.3",
    }

    # gpt-image-2 returns b64_json by default; url is also supported
    body_dict: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "n": 1,
    }
    # gpt-image-2 supports quality; dall-e-3 uses "hd"/"standard"
    if re.search(r"gpt-image", model, re.I):
        body_dict["quality"] = quality         # low / medium / high / auto
        body_dict["output_format"] = "png"
    else:
        body_dict["quality"] = "hd" if quality in ("high", "hd") else "standard"
        body_dict["response_format"] = "b64_json"

    attempts = [body_dict]
    if re.search(r"gpt-image", model, re.I):
        # Some OpenAI-compatible image gateways expose a narrower parameter set.
        attempts.append({k: v for k, v in body_dict.items() if k != "output_format"})
        attempts.append({k: v for k, v in body_dict.items() if k not in {"output_format", "quality"}})

    last_error = ""
    data: dict[str, Any] | None = None
    for attempt in attempts:
        body = json.dumps(attempt).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/images/generations",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=config["timeoutMs"] / 1000) as resp:
                data = json.loads(resp.read())
            break
        except urllib.error.HTTPError as exc:
            last_error = _sanitize_error_body(exc.read().decode("utf-8", errors="replace"))
            if exc.code not in (400, 422, 500, 502, 503, 504):
                raise RuntimeError(f"OpenAI Image API error {exc.code}: {last_error}") from exc

    if data is None:
        raise RuntimeError(f"OpenAI Image API error: {last_error}")

    items = data.get("data") or []
    if not items:
        raise RuntimeError("No image data in API response")

    item = items[0]
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if item.get("b64_json"):
        out.write_bytes(base64.b64decode(item["b64_json"]))
    elif item.get("url"):
        urllib.request.urlretrieve(item["url"], out)
    else:
        raise RuntimeError("Response item has neither b64_json nor url")

    return {
        "provider": "openai",
        "model": model,
        "outputPath": str(out),
        "size": size,
        "quality": quality,
        "platform": platform,
    }


# ---------------------------------------------------------------------------
# Local ad text overlay
# ---------------------------------------------------------------------------

def _load_font(size: int, weight: str = "regular") -> Any:
    try:
        from PIL import ImageFont
    except ImportError:  # pragma: no cover - guarded by caller
        return None

    if weight == "bold":
        candidates: list[tuple[str, int]] = [
            ("/System/Library/Fonts/Hiragino Sans GB.ttc", 2),
            ("/System/Library/Fonts/PingFang.ttc", 8),
            ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
        ]
    elif weight == "medium":
        candidates = [
            ("/System/Library/Fonts/Hiragino Sans GB.ttc", 2),
            ("/System/Library/Fonts/PingFang.ttc", 6),
            ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0),
        ]
    else:
        candidates = [
            ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
            ("/System/Library/Fonts/PingFang.ttc", 3),
            ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
            ("/Library/Fonts/Arial Unicode.ttf", 0),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0),
        ]
    for path, index in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size, index=index)
            except (OSError, TypeError):
                continue
    return ImageFont.load_default()


def _text_width(draw: Any, text: str, font: Any) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return int(box[2] - box[0])


def _wrap_visual_text_lines(draw: Any, text: str, font: Any, max_width: int) -> list[str]:
    text = _visual_text(text, 120)
    if not text or max_width <= 0:
        return []

    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if current and _text_width(draw, candidate, font) > max_width:
            lines.append(current.rstrip())
            current = char.lstrip()
        else:
            current = candidate
    if current:
        lines.append(current.rstrip())
    return lines


def _wrap_visual_text(draw: Any, text: str, font: Any, max_width: int, max_lines: int) -> list[str]:
    return _wrap_visual_text_lines(draw, text, font, max_width)[:max_lines]


def _fit_wrapped_font(
    draw: Any,
    text: str,
    start_size: int,
    min_size: int,
    max_width: int,
    max_lines: int,
    *,
    weight: str = "regular",
) -> tuple[Any, list[str]]:
    size = start_size
    best_font = _load_font(size, weight=weight)
    best_lines = _wrap_visual_text(draw, text, best_font, max_width, max_lines)
    while size > min_size:
        font = _load_font(size, weight=weight)
        all_lines = _wrap_visual_text_lines(draw, text, font, max_width)
        lines = all_lines[:max_lines]
        too_many = len(all_lines) > max_lines
        awkward_tail = len(lines) > 1 and len(lines[-1]) <= 2
        if not too_many and not awkward_tail:
            return font, lines
        best_font, best_lines = font, lines
        size -= 3
    return best_font, best_lines


def _region_is_bright(image: Any, box: tuple[int, int, int, int]) -> bool:
    crop = image.crop(box).convert("L")
    hist = crop.histogram()
    total = sum(hist) or 1
    mean = sum(idx * count for idx, count in enumerate(hist)) / total
    return mean > 145


def _draw_pill(
    draw: Any,
    xy: tuple[int, int],
    text: str,
    font: Any,
    fill: tuple[int, int, int, int],
    ink: tuple[int, int, int, int],
    *,
    outline: tuple[int, int, int, int] | None = None,
    outline_width: int = 1,
) -> int:
    x, y = xy
    font_size = int(getattr(font, "size", 18))
    pad_x = max(10, int(font_size * 0.55))
    pad_y = max(5, int(font_size * 0.28))
    pill_width = _text_width(draw, text, font) + pad_x * 2
    height = int(font_size * 1.45)
    draw.rounded_rectangle((x, y, x + pill_width, y + height), radius=height // 2, fill=fill, outline=outline, width=outline_width)
    draw.text((x + pad_x, y + pad_y - 1), text, font=font, fill=ink)
    return pill_width


def _sample_accent_color(image: Any) -> tuple[int, int, int]:
    """Pick a restrained accent from the generated image for local typography."""
    try:
        sample = image.convert("RGB").resize((28, 28))
    except Exception:  # noqa: BLE001
        return (37, 99, 235)

    buckets: dict[tuple[int, int, int], float] = {}
    # Pillow 14 removes Image.getdata(); prefer get_flattened_data when present.
    pixels = sample.get_flattened_data() if hasattr(sample, "get_flattened_data") else sample.getdata()
    for r, g, b in pixels:
        h, lightness, saturation = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        if saturation < 0.20 or lightness < 0.24 or lightness > 0.78:
            continue
        key = (min(255, (r // 32) * 32), min(255, (g // 32) * 32), min(255, (b // 32) * 32))
        hue_balance = 0.8 + 0.2 * (1 - abs(h - 0.58))
        buckets[key] = buckets.get(key, 0.0) + saturation * (1 - abs(lightness - 0.56)) * hue_balance

    if not buckets:
        return (37, 99, 235)
    return max(buckets, key=buckets.get)


def _detect_content_region_brightness(image: Any, platform: str, fmt: str) -> tuple[bool, tuple[int, int, int, int]]:
    """Detect the brightness of the content region where text will be placed.

    Returns (is_bright, region_box).
    """
    width, height = image.size

    if fmt == "portrait":
        # For portrait (Xiaohongshu), text at top
        margin = int(width * 0.07)
        block = (margin, int(height * 0.055), width - margin, int(height * 0.36))
    elif fmt == "landscape":
        # For landscape, text on left side
        margin = int(width * 0.06)
        block = (margin, int(height * 0.13), int(width * 0.48), int(height * 0.78))
    else:
        # Square (WeChat)
        margin = int(width * 0.075)
        block = (margin, int(height * 0.075), int(width * 0.46), int(height * 0.44))

    return _region_is_bright(image, block), block


def apply_text_overlay(image_path: str | Path, *, platform: str, brief: dict[str, Any]) -> bool:
    """Render crisp local ad copy over a generated visual."""
    if not brief.get("textOverlay", True):
        return False

    # Normalize platform
    platform_key = platform.lower().strip()

    fmt = _platform_format(platform_key)

    # Adjust limits based on platform for better native feel
    platform_limits = {
        "xhs": {"title": 20, "subtitle": 60},
        "xiaohongshu": {"title": 20, "subtitle": 60},
        "wechat": {"title": 24, "subtitle": 50},
        "zhihu": {"title": 35, "subtitle": 80},
        "twitter": {"title": 35, "subtitle": 70},
        "x": {"title": 35, "subtitle": 70},
        "linkedin": {"title": 35, "subtitle": 80},
    }.get(platform_key, {"title": 28 if fmt == "square" else 40, "subtitle": 54 if fmt == "square" else 90})

    title_limit = platform_limits["title"]
    subtitle_limit = platform_limits["subtitle"]

    title = _visual_text(brief.get("title"), title_limit)
    subtitle = _visual_text(brief.get("subtitle"), subtitle_limit)
    cta = _visual_text(brief.get("cta"), 28 if fmt == "square" else 36)
    badges = [b for b in (brief.get("badges") or []) if b]
    if not any([title, subtitle, cta, badges]):
        return False

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("promoagent: Pillow not installed — skipping local text overlay", file=sys.stderr)
        return False

    path = Path(image_path)
    img = Image.open(path).convert("RGBA")
    width, height = img.size
    if width < 200 or height < 200:
        return False

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    editorial_square = fmt == "square"

    # Platform-specific layout adjustments
    if fmt == "portrait":
        # Xiaohongshu style: top area for text, bottom 2/3 for image
        margin = int(width * 0.07)
        block = (margin, int(height * 0.055), width - margin, int(height * 0.36))
        title_size = max(40, min(88, int(width * 0.082)))
        subtitle_size = max(22, min(42, int(width * 0.038)))
        cta_size = max(22, min(36, int(width * 0.034)))
    elif fmt == "landscape":
        # LinkedIn/Twitter style: left side for text
        margin = int(width * 0.06)
        block = (margin, int(height * 0.13), int(width * 0.48), int(height * 0.78))
        title_size = max(36, min(76, int(width * 0.048)))
        subtitle_size = max(20, min(36, int(width * 0.023)))
        cta_size = max(18, min(30, int(width * 0.02)))
    else:
        # WeChat style: compact left-top area
        margin = int(width * 0.075)
        block = (margin, int(height * 0.075), int(width * 0.46), int(height * 0.44))
        title_size = max(30, min(50, int(width * 0.048)))
        subtitle_size = max(18, min(28, int(width * 0.026)))
        cta_size = max(17, min(26, int(width * 0.024)))

    # Detect background brightness for contrast
    bright = _region_is_bright(img, block)
    accent_rgb = _sample_accent_color(img)

    # Enhanced color scheme with platform nuances
    if editorial_square:
        # WeChat: warmer, more elegant
        panel_fill = (252, 252, 248, 178)
        panel_outline = (255, 255, 255, 110)
        title_ink = (21, 24, 31, 255)
        body_ink = (67, 72, 82, 238)
        accent_ink = (*accent_rgb, 235)
    else:
        if platform_key in ("xhs", "xiaohongshu"):
            # Xiaohongshu: brighter, more vibrant
            panel_fill = (255, 255, 255, 160) if not bright else (255, 255, 255, 90)
            panel_outline = (255, 255, 255, 140) if not bright else None
            title_ink = (18, 22, 30, 255) if bright else (255, 255, 255, 255)
            body_ink = (48, 55, 68, 240) if bright else (255, 255, 255, 245)
            accent_ink = (*accent_rgb, 255)
        elif platform_key in ("linkedin", "zhihu"):
            # LinkedIn/Zhihu: more professional, subdued
            panel_fill = (248, 249, 250, 170) if not bright else (255, 255, 255, 100)
            panel_outline = None
            title_ink = (28, 32, 38, 255) if bright else (250, 251, 252, 255)
            body_ink = (72, 78, 88, 240) if bright else (235, 237, 240, 245)
            accent_ink = (255, 255, 255, 0)
        else:
            # Default: Twitter/X, etc.
            panel_fill = (255, 255, 255, 178) if not bright else (255, 255, 255, 118)
            panel_outline = None
            title_ink = (18, 22, 30, 255) if bright else (255, 255, 255, 255)
            body_ink = (48, 55, 68, 235) if bright else (245, 247, 252, 232)
            accent_ink = (255, 255, 255, 0)

        if not bright:
            panel_fill = (10, 14, 22, 96)

    x1, y1, x2, _y2 = block
    max_text_width = x2 - x1

    # Platform-specific line limits
    title_lines_max = 2
    subtitle_lines_max = 1 if editorial_square else 2

    title_font, title_lines = _fit_wrapped_font(
        draw,
        title,
        title_size,
        max(28, int(title_size * 0.72)),
        max_text_width,
        title_lines_max,
        weight="bold",
    )
    subtitle_font, subtitle_lines = _fit_wrapped_font(
        draw,
        subtitle,
        subtitle_size,
        max(16, int(subtitle_size * 0.78)),
        max_text_width,
        subtitle_lines_max,
        weight="regular",
    )
    cta_font = _load_font(cta_size, weight="bold")
    badge_font = _load_font(max(16, int(cta_size * 0.8)), weight="medium")

    # Calculate panel height
    y = y1
    title_size_actual = int(getattr(title_font, "size", title_size))
    subtitle_size_actual = int(getattr(subtitle_font, "size", subtitle_size))
    panel_bottom = y + len(title_lines) * int(title_size_actual * 1.12)

    # Add accent line space for editorial square
    if editorial_square:
        panel_bottom += int(title_size_actual * 0.42)

    # Add subtitle space
    if subtitle_lines:
        panel_bottom += int(title_size_actual * 0.35)
        panel_bottom += len(subtitle_lines) * int(subtitle_size_actual * 1.35)

    # Add spacing before badges/CTA
    panel_bottom += int(height * 0.035)

    # Add badges space
    if badges:
        panel_bottom += int(getattr(badge_font, "size", 18) * 1.9)

    # Add CTA space
    if cta:
        panel_bottom += int(cta_size * 1.9)

    # Draw panel background
    panel_pad = int(width * 0.025)
    draw.rounded_rectangle(
        (x1 - panel_pad, y1 - panel_pad, x2 + panel_pad, min(height - panel_pad, panel_bottom + panel_pad)),
        radius=max(18, int(width * 0.025)),
        fill=panel_fill,
        outline=panel_outline,
        width=max(1, int(width * 0.0015)),
    )

    # Accent line for editorial square (WeChat style)
    if editorial_square:
        accent_h = max(4, int(height * 0.006))
        accent_w = max(40, int(width * 0.055))
        draw.rounded_rectangle((x1, y, x1 + accent_w, y + accent_h), radius=accent_h // 2, fill=accent_ink)
        y += int(title_size_actual * 0.42)

    # Draw title
    for line in title_lines:
        draw.text((x1, y), line, font=title_font, fill=title_ink)
        y += int(title_size_actual * 1.12)

    # Draw subtitle
    if subtitle_lines:
        y += int(subtitle_size_actual * 0.35)
        for line in subtitle_lines:
            draw.text((x1, y), line, font=subtitle_font, fill=body_ink)
            y += int(subtitle_size_actual * 1.35)

    # Draw badges
    if badges:
        badge_size = int(getattr(badge_font, "size", 18))
        y += int(badge_size * 0.55)
        badge_x = x1
        for badge in badges:
            if editorial_square:
                fill = (255, 255, 255, 70)
                ink = (42, 47, 58, 245)
                outline = (*accent_rgb, 126)
            else:
                fill = (20, 24, 32, 34) if bright else (255, 255, 255, 205)
                ink = (42, 48, 60, 245) if bright else (26, 30, 40, 255)
                outline = None
            used = _draw_pill(draw, (badge_x, y), badge, badge_font, fill, ink, outline=outline)
            badge_x += used + int(badge_size * 0.45)
            if badge_x > x2 - int(width * 0.12):
                break
        y += int(badge_size * 1.8)

    # Draw CTA button
    if cta:
        y += int(cta_size * 0.3)
        if editorial_square:
            cta_fill = (23, 27, 35, 238)
            cta_ink = (255, 255, 252, 255)
        else:
            cta_fill = (24, 29, 39, 235) if bright else (255, 255, 255, 235)
            cta_ink = (255, 255, 255, 255) if bright else (22, 27, 38, 255)
        _draw_pill(draw, (x1, y), cta, cta_font, cta_fill, cta_ink)

    # Composite and save
    out = Image.alpha_composite(img, overlay).convert("RGB")
    out.save(path, quality=95, optimize=True)
    return True


# ---------------------------------------------------------------------------
# README image extraction
# ---------------------------------------------------------------------------

def _is_suitable_promo_image(url: str) -> bool:
    """Check if a URL points to an image suitable for promotion (not badge/icon)."""
    url_lower = url.lower()
    # Skip common non-promo images
    skip_patterns = [
        "badge", "shield", "icon", "logo-small", "favicon",
        "github.com/actions", "github/workflows", "img.shields.io",
        "codecov", "coveralls", "travis", "circleci", "dependabot",
        "pre-commit", "semantic-release", "allcontributors",
        "pypi.org", "npmjs.com", "crates.io", "maven", "gradle",
        "license-", "version-", "downloads-", "stars-",
    ]
    for pattern in skip_patterns:
        if pattern in url_lower:
            return False
    # Prefer screenshots, demos, covers
    promo_patterns = ["screenshot", "demo", "preview", "cover", "banner", "hero", "example"]
    return any(p in url_lower for p in promo_patterns)


def fetch_readme_images(result: dict[str, Any], output_dir: Path) -> list[dict[str, Any]]:
    """Download images from the project's README visual URLs."""
    urls = (result.get("evidence") or {}).get("visualUrls") or []
    saved: list[dict[str, Any]] = []
    if not urls:
        return saved

    # Prioritize suitable promo images
    prioritized = sorted(urls, key=lambda u: (not _is_suitable_promo_image(u), urls.index(u)))

    output_dir.mkdir(parents=True, exist_ok=True)
    for i, url in enumerate(prioritized[:4]):
        try:
            ext = "jpg"
            for candidate in (".png", ".gif", ".webp", ".svg"):
                if candidate in url.lower():
                    ext = candidate.lstrip(".")
                    break
            out_path = output_dir / f"readme-{i + 1}.{ext}"
            req = urllib.request.Request(url, headers={"User-Agent": "promoagent/0.3"})
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
                out_path.write_bytes(resp.read())
            saved.append({"url": url, "path": str(out_path), "source": "readme"})
            print(f"promoagent: downloaded readme image → {out_path.name}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"promoagent: could not download {url}: {exc}", file=sys.stderr)

    return saved


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def generate_platform_images(
    result: dict[str, Any],
    output_dir: Path,
    options: dict[str, Any] | None = None,
    *,
    env: dict[str, str] | None = None,
    produce_data: dict[str, Any] | None = None,
    image_style: str = "auto",
) -> list[dict[str, Any]]:
    """Generate images from both README sources and AI (ModelScope).

    Returns a list of generated image metadata dicts.
    Image generation failures are logged but do not raise.

    ``produce_data`` (the produce stage's platform→content mapping) enables
    HTML card rendering via ``render_xhs`` when ``image_style`` is "card" or
    "auto" (auto uses cards for Xiaohongshu, AI for others).
    """
    options = options or {}
    generated: list[dict[str, Any]] = []

    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # Source 0: HTML card rendering (deterministic, styleable) for platforms
    # whose produce output is available. Routes by PlatformRenderSpec so any
    # platform with a spec (xhs/wechat/linkedin/twitter) renders cards; others
    # fall through to AI image generation below.
    if produce_data and image_style in ("card", "auto"):
        try:
            from .render import render_platform_cards, get_spec
        except ImportError:
            render_platform_cards = None  # type: ignore[assignment]
            get_spec = None  # type: ignore[assignment]
        if render_platform_cards is not None and get_spec is not None:
            for plat_key, content in produce_data.items():
                if not isinstance(content, dict) or not content.get("markdown"):
                    continue
                spec = get_spec(plat_key)
                if spec is None or spec.cards == "none":
                    continue  # pass-through platform or unknown
                try:
                    cards = render_platform_cards(plat_key, content, images_dir)
                    generated.extend(cards)
                except Exception as exc:  # noqa: BLE001
                    print(f"promoagent: {plat_key} card render failed: {exc}", file=sys.stderr)

    # Source 1: README images
    readme_imgs = fetch_readme_images(result, images_dir)
    generated.extend(readme_imgs)

    # Source 2: AI-generated cover images (requires API key)
    # Merge env key into options so image_config and has_image_key both see it
    effective_env = {**(env or os.environ)}
    if options.get("api_key"):
        effective_env["PROMOAGENT_IMAGE_API_KEY"] = options["api_key"]
    if not has_image_key(effective_env):
        print(
            "promoagent: no image API key found — skipping AI image generation. "
            "Set PROMOAGENT_IMAGE_API_KEY or PROMOAGENT_MODELSCOPE_API_KEY to enable.",
            file=sys.stderr,
        )
        return generated

    cfg = image_config(options, effective_env)
    use_openai = _is_openai_model(cfg["model"])
    provider_label = "openai" if use_openai else "modelscope"
    print(f"promoagent: image provider → {provider_label} ({cfg['model']})", file=sys.stderr)

    style = options.get("style") or effective_env.get("PROMOAGENT_IMAGE_STYLE") or "clean"
    skill = options.get("skill") or effective_env.get("PROMOAGENT_IMAGE_SKILL") or "auto"
    brief = image_brief(result, options=options, env=effective_env)
    try:
        variants = max(1, min(6, int(options.get("variants") or effective_env.get("PROMOAGENT_IMAGE_VARIANTS") or 1)))
    except (TypeError, ValueError):
        variants = 1
    platforms_to_generate = [(platform, _safe_platform_slug(platform)) for platform in _image_platforms(options, effective_env, result)]
    for platform, filename_hint in platforms_to_generate:
        for variant in range(1, variants + 1):
            try:
                prompt = build_image_prompt(
                    result,
                    platform=platform,
                    style=style,
                    skill=skill,
                    brief=brief,
                    variant=variant,
                    variant_count=variants,
                    model=cfg["model"],
                )
                creative_skill = resolve_image_skill(
                    requested=skill,
                    recommendation_kind=_recommendation_kind(result),
                    platform=platform,
                )
                ext = "png" if use_openai else "jpg"
                variant_suffix = f"-v{variant}" if variants > 1 else ""
                out_path = images_dir / f"cover-{filename_hint}{variant_suffix}.{ext}"
                label = f"{platform} v{variant}" if variants > 1 else platform
                print(f"promoagent: generating image for {label}…", file=sys.stderr)

                if use_openai:
                    meta = generate_openai_image(prompt, output_path=out_path, config=cfg, platform=platform)
                else:
                    meta = generate_modelscope_image(prompt, output_path=out_path, config=cfg, platform=platform)

                if apply_text_overlay(out_path, platform=platform, brief=brief):
                    meta["textOverlay"] = True
                meta["skill"] = creative_skill["name"]
                meta["prompt"] = prompt
                meta["variant"] = variant
                generated.append(meta)
                print(f"promoagent: image saved → {out_path.name}", file=sys.stderr)
            except Exception as exc:  # noqa: BLE001
                print(f"promoagent: image generation failed for {platform}: {exc}", file=sys.stderr)

    return generated

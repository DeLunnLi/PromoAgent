"""Platform configuration and specifications.

Centralized platform definitions to avoid duplication across modules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PlatformSpec:
    """Platform specification."""
    key: str
    name: str
    name_cn: str
    format: str
    style: str
    length: str
    emoji: bool
    tone: str
    icon: str
    api_support: bool
    best_for: str
    aspect_ratio: str = "1:1"  # Default for image generation
    # Per-axis critic weights — higher = that axis matters more for this platform.
    # Used by pipeline._critic_platform for weighted total calculation.
    critic_weights: dict[str, float] = field(default_factory=lambda: {
        "fidelity": 1.0, "engagement": 1.0, "alignment": 1.0,
    })


# Unified platform specifications
PLATFORMS: dict[str, PlatformSpec] = {
    "xiaohongshu": PlatformSpec(
        key="xiaohongshu",
        name="Xiaohongshu",
        name_cn="小红书",
        format="图文笔记",
        style="真实分享、种草",
        length="300-600字",
        emoji=True,
        tone="亲切、口语化",
        icon="📱",
        api_support=False,
        best_for="Visual storytelling, lifestyle",
        aspect_ratio="3:4",
        critic_weights={"fidelity": 0.8, "engagement": 1.4, "alignment": 0.8},
    ),
    "xhs": PlatformSpec(
        key="xiaohongshu",
        name="Xiaohongshu",
        name_cn="小红书",
        format="图文笔记",
        style="真实分享、种草",
        length="300-600字",
        emoji=True,
        tone="亲切、口语化",
        icon="📱",
        api_support=False,
        best_for="Visual storytelling, lifestyle",
        aspect_ratio="3:4",
        critic_weights={"fidelity": 0.8, "engagement": 1.4, "alignment": 0.8},
    ),
    "zhihu": PlatformSpec(
        key="zhihu",
        name="Zhihu",
        name_cn="知乎",
        format="回答/文章",
        style="专业深度、结构化",
        length="800-1500字",
        emoji=False,
        tone="理性、可信",
        icon="📝",
        api_support=False,
        best_for="Technical deep-dives",
        aspect_ratio="16:9",
        critic_weights={"fidelity": 1.4, "engagement": 0.8, "alignment": 0.8},
    ),
    "wechat": PlatformSpec(
        key="wechat",
        name="WeChat",
        name_cn="微信",
        format="公众号文章",
        style="正式、完整",
        length="1000-2000字",
        emoji=False,
        tone="专业、权威",
        icon="💬",
        api_support=False,
        best_for="Long-form articles",
        aspect_ratio="1:1",
        critic_weights={"fidelity": 1.2, "engagement": 1.0, "alignment": 0.8},
    ),
    "twitter": PlatformSpec(
        key="twitter",
        name="Twitter",
        name_cn="Twitter/X",
        format="推文串",
        style="简洁有力",
        length="280字/条，3-5条串",
        emoji=True,
        tone="直接、有冲击力",
        icon="🐦",
        api_support=True,
        best_for="Quick announcements",
        aspect_ratio="16:9",
        critic_weights={"fidelity": 0.8, "engagement": 1.3, "alignment": 0.9},
    ),
    "x": PlatformSpec(
        key="twitter",
        name="Twitter",
        name_cn="Twitter/X",
        format="推文串",
        style="简洁有力",
        length="280字/条，3-5条串",
        emoji=True,
        tone="直接、有冲击力",
        icon="🐦",
        api_support=True,
        best_for="Quick announcements",
        aspect_ratio="16:9",
        critic_weights={"fidelity": 0.8, "engagement": 1.3, "alignment": 0.9},
    ),
    "linkedin": PlatformSpec(
        key="linkedin",
        name="LinkedIn",
        name_cn="LinkedIn",
        format="专业帖子",
        style="B2B、职业",
        length="300-800字",
        emoji=False,
        tone="专业、务实",
        icon="💼",
        api_support=True,
        best_for="B2B professional",
        aspect_ratio="16:9",
        critic_weights={"fidelity": 1.0, "engagement": 0.8, "alignment": 1.2},
    ),
    "reddit": PlatformSpec(
        key="reddit",
        name="Reddit",
        name_cn="Reddit",
        format="帖子",
        style="社区驱动、真实",
        length="200-800字",
        emoji=False,
        tone="真实、友好",
        icon="🤖",
        api_support=True,
        best_for="Community engagement",
        aspect_ratio="16:9",
    ),
    "producthunt": PlatformSpec(
        key="producthunt",
        name="Product Hunt",
        name_cn="Product Hunt",
        format="产品发布",
        style="maker故事、简洁",
        length="短描述",
        emoji=True,
        tone="兴奋、简洁",
        icon="🎯",
        api_support=False,
        best_for="Product launches",
        aspect_ratio="16:9",
    ),
    "showhn": PlatformSpec(
        key="showhn",
        name="Show HN",
        name_cn="Show HN",
        format="极简发布",
        style="技术导向、直接",
        length="简洁",
        emoji=False,
        tone="技术、直接",
        icon="🖥️",
        api_support=False,
        best_for="Tech launches",
        aspect_ratio="16:9",
    ),
    "weibo": PlatformSpec(
        key="weibo",
        name="Weibo",
        name_cn="微博",
        format="短内容",
        style="社交、热点",
        length="140字",
        emoji=True,
        tone="轻松、社交",
        icon="📢",
        api_support=True,
        best_for="Chinese social",
        aspect_ratio="1:1",
    ),
    "telegram": PlatformSpec(
        key="telegram",
        name="Telegram",
        name_cn="Telegram",
        format="频道消息",
        style="简洁、即时",
        length="可变",
        emoji=True,
        tone="直接、信息性",
        icon="✈️",
        api_support=True,
        best_for="Channel broadcasts",
        aspect_ratio="1:1",
    ),
    "bluesky": PlatformSpec(
        key="bluesky",
        name="Bluesky",
        name_cn="Bluesky",
        format="帖子",
        style="去中心化、开放",
        length="300字",
        emoji=True,
        tone="友好、开放",
        icon="🦋",
        api_support=True,
        best_for="Decentralized social",
        aspect_ratio="1:1",
    ),
}


def get_platform(key: str) -> PlatformSpec | None:
    """Get platform specification by key."""
    return PLATFORMS.get(key.lower())


def list_platforms() -> list[PlatformSpec]:
    """Get list of unique platform specifications."""
    seen = set()
    platforms = []
    for spec in PLATFORMS.values():
        if spec.key not in seen:
            seen.add(spec.key)
            platforms.append(spec)
    return platforms


def get_primary_platforms() -> list[str]:
    """Get primary platform keys (no aliases)."""
    return ["xiaohongshu", "zhihu", "wechat", "twitter", "linkedin", "reddit", "producthunt", "showhn", "weibo", "telegram", "bluesky"]


def to_prompt_dict(spec: PlatformSpec) -> dict[str, Any]:
    """Convert platform spec to prompt-compatible dict."""
    return {
        "format": spec.format,
        "style": spec.style,
        "length": spec.length,
        "emoji": spec.emoji,
        "tone": spec.tone,
    }


# ---------------------------------------------------------------------------
# Platform playbooks — deeper, prompt-injected knowledge per platform.
#
# Kept separate from PlatformSpec on purpose: asdict(spec) is serialized for the
# MCP s2l_list_platforms tool, and embedding long playbook text there would
# bloat every platform-list response. Playbooks are pulled on demand only by
# the produce stage.
# ---------------------------------------------------------------------------

PLATFORM_PLAYBOOKS: dict[str, dict[str, str]] = {
    "xiaohongshu": {
        "structure_template": "痛点引入（前3行）→ 个人体验故事 → 具体好处（带数字/场景）→ 互动CTA",
        "opening_rule": "前3行决定推荐流量。第一句要有具体场景或冲突，禁止以「推荐」「介绍」开头",
        "good_vs_bad": "好帖：像朋友分享体验；广告感帖：罗列功能参数、通篇「我们」「这款」",
        "mechanics": "话题标签3-5个放文末，含1个大词+2个长尾词；标题SEO关键词前置；正文口语化、分段短",
    },
    "twitter": {
        "structure_template": "钩子推文（冲击力）→ 价值点1 → 价值点2 → 证据/数据 → CTA推文",
        "opening_rule": "首推文决定整条串是否被展开。用反常识、具体数字或提问开头，禁止「我很兴奋地宣布」",
        "good_vs_bad": "好推：一句一个信息点；广告感推：堆砌形容词、链接放首推",
        "mechanics": "链接放最后一推；每推独立可读；hashtag最多2个；首推留字符余量给预览卡片",
    },
    "zhihu": {
        "structure_template": "问题切入 → 个人观点（带立场）→ 论证（数据/案例/对比）→ 实操建议 → 总结",
        "opening_rule": "首段要给明确结论或反常识观点，知乎读者吃这一套；禁止「关于这个问题我认为」",
        "good_vs_bad": "好答：有信息密度和结构；水答：堆砌大段空话、无数据支撑",
        "mechanics": "用加粗/小标题分段；关键数据加引用；文末可加相关推荐但不硬广",
    },
    "wechat": {
        "structure_template": "场景代入 → 痛点共鸣 → 解决方案展开 → 案例/数据佐证 → 价值收尾",
        "opening_rule": "首段要有一个具体的人/场景，公众号读者要被代入才往下读",
        "good_vs_bad": "好文：叙事感强、有信息增量；水文：通篇口号、无具体案例",
        "mechanics": "小标题分明；每段不超过4行；配图位置预留；文末引导关注但不强推",
    },
    "linkedin": {
        "structure_template": "职业洞察开场 → 反共识/数据点 → 3-5条结构化要点 → 个人经验佐证 → 行动呼吁",
        "opening_rule": "首行给一个能引发同行讨论的判断，LinkedIn 算法重讨论",
        "good_vs_bad": "好帖：专业且有立场；广告帖：纯产品宣传、无个人视角",
        "mechanics": "每行间空行提升可读性；3-5个要点用emoji编号；文末抛问题促评论",
    },
}


def get_playbook(key: str) -> dict[str, str] | None:
    """Return the playbook for a platform key, resolving aliases (xhs→xiaohongshu)."""
    spec = PLATFORMS.get(key.lower().strip())
    if spec is None:
        return None
    return PLATFORM_PLAYBOOKS.get(spec.key)


def format_playbook_for_prompt(key: str) -> str:
    """Format a platform playbook into a prompt block; empty string if none."""
    pb = get_playbook(key)
    if not pb:
        return ""
    lines = [f"【{key} 平台法则】"]
    for label, field in [
        ("结构模板", "structure_template"),
        ("开头法则", "opening_rule"),
        ("好/反例", "good_vs_bad"),
        ("机制要点", "mechanics"),
    ]:
        if pb.get(field):
            lines.append(f"{label}：{pb[field]}")
    return "\n".join(lines)


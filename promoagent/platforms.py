"""Platform configuration and specifications.

Centralized platform definitions to avoid duplication across modules.
"""
from __future__ import annotations

from dataclasses import dataclass
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


def get_platform_keys() -> list[str]:
    """Get all valid platform keys (including aliases)."""
    return list(PLATFORMS.keys())


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

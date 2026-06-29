from __future__ import annotations

from typing import Any

PLATFORM_LABELS = {
    "twitter": "X / Twitter",
    "linkedin": "LinkedIn",
    "producthunt": "Product Hunt",
    "hackernews": "Hacker News / Show HN",
    "zhihu": "Zhihu",
    "xhs": "Xiaohongshu",
    "wechat-official": "WeChat Official Account",
    "wechat-moments": "WeChat Moments",
}

PLATFORM_DELIVERY = {
    "twitter": {"apiCapable": True, "adapter": "x-api", "officialApi": "POST /2/tweets", "reviewNote": "Verify text, link, media, and account before posting through the X API."},
    "linkedin": {"apiCapable": True, "adapter": "linkedin-posts-api", "officialApi": "LinkedIn Posts API", "reviewNote": "Verify organization/person author, media assets, and link preview before publishing."},
    "producthunt": {"apiCapable": False, "adapter": "manual-launch-review", "officialApi": "Product Hunt API access is limited for launch workflows.", "reviewNote": "Use this payload as launch-page copy and maker-comment draft; keep final submission manual."},
    "hackernews": {"apiCapable": False, "adapter": "manual-show-hn", "officialApi": "No official posting API for Show HN.", "reviewNote": "Use this as a Show HN draft; submit manually from the logged-in account after checking guidelines."},
    "zhihu": {"apiCapable": False, "adapter": "assist-fill", "officialApi": "No general public posting API for normal user answers.", "reviewNote": "Use browser-assisted filling only after user review; publish manually."},
    "xhs": {"apiCapable": False, "adapter": "assist-fill", "officialApi": "No general public posting API for normal user notes.", "reviewNote": "Use browser-assisted filling only after user review; publish manually."},
    "wechat-official": {"apiCapable": True, "adapter": "wechat-official-api", "officialApi": "Draft and free-publish APIs", "reviewNote": "Verify title, cover, media IDs, article body, and account permissions before publishing."},
    "wechat-moments": {"apiCapable": False, "adapter": "manual-moments", "officialApi": "No public WeChat Moments publishing API.", "reviewNote": "Use this as a manual Moments draft."},
}

BROWSER_ASSIST_TARGETS = {
    "twitter": {"openUrl": "https://x.com/compose/post", "surface": "Post composer"},
    "linkedin": {"openUrl": "https://www.linkedin.com/feed/", "surface": "LinkedIn post composer"},
    "producthunt": {"openUrl": "https://www.producthunt.com/launch", "surface": "Product Hunt launch flow"},
    "hackernews": {"openUrl": "https://news.ycombinator.com/submit", "surface": "Hacker News submit page"},
    "zhihu": {"openUrl": "https://www.zhihu.com/", "surface": "Zhihu answer/article composer"},
    "xhs": {"openUrl": "https://creator.xiaohongshu.com/publish/publish", "surface": "Xiaohongshu creator publish page"},
    "wechat-official": {"openUrl": "https://mp.weixin.qq.com/", "surface": "WeChat Official Account draft editor"},
    "wechat-moments": {"openUrl": "weixin://", "surface": "WeChat Moments composer"},
}

ALL_PLATFORMS = ["twitter", "linkedin", "producthunt", "hackernews", "zhihu", "xhs", "wechat-official", "wechat-moments"]


def build_publish_plan(input_data: dict[str, Any], options: dict[str, Any] | None = None) -> dict[str, Any]:
    options = options or {}
    content = normalize_promotion_content(input_data)
    platforms = normalize_publish_platforms(options.get("platform") or options.get("promo") or "all")
    approved = bool(options.get("approved") or options.get("yes"))
    publish_mode = normalize_publish_mode(options.get("publishMode"))
    media = normalize_list(options.get("media"))
    items = [
        item for platform in platforms
        if (item := build_publish_item(content, platform, {"approved": approved, "media": media, "publishMode": publish_mode}))
    ]
    return {
        "version": "0.1",
        "status": "approved" if approved else "review_required",
        "publishMode": publish_mode,
        "approved": approved,
        "reviewRequired": not approved,
        "execution": "not_executed",
        "note": "Payloads are marked approved, but no platform API call has been executed by this preview plan." if approved else "Review the payloads below. Add --yes only after a human has approved the content.",
        "items": items,
    }


def format_publish_plan(plan: dict[str, Any]) -> str:
    lines = [
        f"Publish plan ({plan['status']})",
        f"Mode: {plan['publishMode']}",
        f"Approved: {'yes' if plan['approved'] else 'no'}",
        f"Execution: {plan['execution']}",
    ]
    if plan.get("note"):
        lines.append(f"Note: {plan['note']}")
    for item in plan.get("items", []):
        lines.extend(["", f"{item['label']} [{item['status']}]", f"Adapter: {item['delivery']['adapter']}", f"Official API: {item['delivery']['officialApi']}", f"API capable: {'yes' if item['delivery']['apiCapable'] else 'no'}"])
        if item["delivery"].get("reviewNote"):
            lines.append(f"Review note: {item['delivery']['reviewNote']}")
        append_payload(lines, item["payload"])
        if item.get("browserAssist"):
            append_assist(lines, item["browserAssist"])
        append_checklist(lines, item["reviewChecklist"])
    return "\n".join(lines)


def build_publish_item(content: dict[str, Any], platform: str, options: dict[str, Any]) -> dict[str, Any] | None:
    payload = platform_payload(content, platform, options)
    if not payload:
        return None
    delivery = PLATFORM_DELIVERY.get(platform, {"apiCapable": False, "adapter": "manual", "officialApi": "Unknown", "reviewNote": "Review manually before publishing."})
    status = publish_item_status(delivery, options)
    item = {
        "platform": platform,
        "label": PLATFORM_LABELS.get(platform, platform),
        "status": status,
        "payload": payload,
        "delivery": delivery,
        "reviewChecklist": review_checklist_for(platform, payload),
    }
    if options["publishMode"] == "assist":
        item["browserAssist"] = browser_assist_plan(platform, payload)
    return item


def platform_payload(content: dict[str, Any], platform: str, options: dict[str, Any]) -> dict[str, Any] | None:
    promotions = content.get("promotions", {})
    media = options.get("media", [])
    if platform == "xhs":
        item = promotions.get("xiaohongshu") or promotions.get("xhs") or {}
        return {"title": first(item.get("titles")) or item.get("title") or "", "text": item.get("markdown") or item.get("body") or "", "tags": item.get("tags") or [], "media": media}
    if platform == "zhihu":
        item = promotions.get("zhihu") or {}
        return {"title": item.get("title") or first(item.get("suggestedQuestions")) or "", "text": item.get("markdown") or item.get("body") or "", "questions": item.get("suggestedQuestions") or [], "media": media}
    if platform == "wechat-moments":
        item = promotions.get("wechatMoments") or promotions.get("wechat") or {}
        return {"text": item.get("markdown") or item.get("body") or "", "media": media}
    if platform == "hackernews":
        item = promotions.get("showHn") or {}
        return {"title": item.get("title") or "", "text": item.get("markdown") or item.get("body") or "", "url": content.get("project", {}).get("repositoryUrl")}
    if platform == "producthunt":
        item = promotions.get("productHunt") or {}
        return {"name": content.get("project", {}).get("name"), "tagline": item.get("tagline") or "", "text": item.get("markdown") or item.get("firstComment") or "", "media": media}
    if platform == "twitter":
        item = promotions.get("twitter") or {}
        return {"text": item.get("markdown") or "", "thread": markdown_to_thread(item.get("markdown") or ""), "media": media}
    return {"text": ""}


def publish_item_status(delivery: dict[str, Any], options: dict[str, Any]) -> str:
    if not options["approved"]:
        return "review_required"
    if options["publishMode"] == "api" and not delivery["apiCapable"]:
        return "manual_review_required"
    if options["publishMode"] == "assist":
        return "assist_ready"
    return "approved"


def browser_assist_plan(platform: str, payload: dict[str, Any]) -> dict[str, Any]:
    target = BROWSER_ASSIST_TARGETS.get(platform, {"openUrl": "", "surface": "Unknown"})
    return {"openUrl": target["openUrl"], "surface": target["surface"], "fields": payload, "finalAction": "user_clicks_publish"}


def review_checklist_for(platform: str, payload: dict[str, Any]) -> list[str]:
    checks = ["Human has reviewed facts and tone.", "Links and media are correct.", "No unsupported metrics or claims remain."]
    if platform in {"xhs", "zhihu", "wechat-moments"}:
        checks.append("Chinese copy matches the account voice and platform rhythm.")
    if payload.get("media"):
        checks.append("Attached media is source-grounded and publish-safe.")
    return checks


def normalize_promotion_content(input_data: dict[str, Any]) -> dict[str, Any]:
    if input_data.get("ai", {}).get("content"):
        return input_data["ai"]["content"]
    if input_data.get("content"):
        return input_data["content"]
    return input_data


def normalize_publish_platforms(value: str | list[str]) -> list[str]:
    raw = value if isinstance(value, list) else str(value).split(",")
    names = [normalize_platform_name(item) for item in raw if str(item).strip()]
    if not names or "all" in names:
        return ALL_PLATFORMS
    return names


def normalize_platform_name(value: str) -> str:
    value = value.strip().lower()
    aliases = {"hn": "hackernews", "showhn": "hackernews", "show-hn": "hackernews", "product-hunt": "producthunt", "wechat": "wechat-moments", "weixin": "wechat-moments", "x": "twitter"}
    return aliases.get(value, value)


def normalize_publish_mode(value: str | None) -> str:
    value = (value or "review").strip().lower()
    return value if value in {"review", "dry-run", "api", "assist"} else "review"


def markdown_to_thread(markdown: str) -> list[str]:
    return [part.strip() for part in markdown.split("\n\n") if part.strip()][:8]


def append_payload(lines: list[str], payload: dict[str, Any]) -> None:
    lines.append("Payload:")
    for key, value in payload.items():
        if value not in (None, "", []):
            lines.append(f"- {key}: {value}")


def append_assist(lines: list[str], assist: dict[str, Any]) -> None:
    lines.append("Browser assist:")
    lines.append(f"- openUrl: {assist['openUrl']}")
    lines.append(f"- finalAction: {assist['finalAction']}")


def append_checklist(lines: list[str], checklist: list[str]) -> None:
    lines.append("Review checklist:")
    for item in checklist:
        lines.append(f"- [ ] {item}")


def normalize_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def first(value: Any) -> Any:
    return value[0] if isinstance(value, list) and value else None

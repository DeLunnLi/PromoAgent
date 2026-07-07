"""Platform publishing adapters for Source2Launch.

Each publisher reads credentials from environment variables and posts
promotional content to the corresponding social media platform.

All network calls use urllib (zero new dependencies).

Supported platforms:
  telegram   - Telegram Bot API (easiest, no developer approval needed)
  bluesky    - Bluesky AT Protocol (open, no approval needed)
  twitter    - Twitter/X API v2 (requires OAuth 2.0 user token)
  linkedin   - LinkedIn API v2 (requires OAuth access token)
  reddit     - Reddit API OAuth2 (requires registered app)
  weibo      - Weibo Open API (requires registered app)

Chinese platforms (小红书, 知乎) have no public posting API.
Content is generated but must be posted manually.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

FETCH_TIMEOUT = 30

# ---------------------------------------------------------------------------
# Base publisher
# ---------------------------------------------------------------------------

class PublishResult:
    def __init__(self, ok: bool, platform: str, url: str = "", error: str = ""):
        self.ok = ok
        self.platform = platform
        self.url = url
        self.error = error

    def __repr__(self) -> str:
        if self.ok:
            return f"✅ {self.platform}: {self.url or 'published'}"
        return f"❌ {self.platform}: {self.error}"


class BasePlatformPublisher:
    platform_name: str = "unknown"
    required_env: list[str] = []

    def __init__(self, env: dict[str, str] | None = None):
        self.env = env or os.environ

    def is_configured(self) -> bool:
        return all(self.env.get(k) for k in self.required_env)

    def publish(self, content: str, **kwargs: Any) -> PublishResult:
        raise NotImplementedError

    def _post(self, url: str, body: dict, headers: dict | None = None) -> dict:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        try:
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc

    def _post_form(self, url: str, params: dict, headers: dict | None = None) -> dict:
        data = urllib.parse.urlencode(params).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded", **(headers or {})},
        )
        try:
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
# Setup: Create a bot via @BotFather, get the token.
# Env:   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

class TelegramPublisher(BasePlatformPublisher):
    platform_name = "telegram"
    required_env = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]

    def publish(self, content: str, **kwargs: Any) -> PublishResult:
        token = self.env["TELEGRAM_BOT_TOKEN"]
        chat_id = kwargs.get("chat_id") or self.env["TELEGRAM_CHAT_ID"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        # Telegram has a 4096-char limit; truncate if needed
        text = content[:4096]
        try:
            resp = self._post(url, {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
            if resp.get("ok"):
                msg_id = resp.get("result", {}).get("message_id", "")
                return PublishResult(True, "telegram", f"https://t.me/{chat_id}/{msg_id}")
            return PublishResult(False, "telegram", error=str(resp.get("description")))
        except Exception as exc:  # noqa: BLE001
            return PublishResult(False, "telegram", error=str(exc))


# ---------------------------------------------------------------------------
# Bluesky (AT Protocol)
# ---------------------------------------------------------------------------
# Setup: Use your Bluesky handle and an App Password (Settings → App Passwords).
# Env:   BLUESKY_HANDLE (e.g. yourname.bsky.social), BLUESKY_APP_PASSWORD

class BlueskyPublisher(BasePlatformPublisher):
    platform_name = "bluesky"
    required_env = ["BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD"]
    _BASE = "https://bsky.social/xrpc"

    def _login(self) -> tuple[str, str]:
        """Returns (did, accessJwt)."""
        resp = self._post(
            f"{self._BASE}/com.atproto.server.createSession",
            {"identifier": self.env["BLUESKY_HANDLE"], "password": self.env["BLUESKY_APP_PASSWORD"]},
        )
        return resp["did"], resp["accessJwt"]

    def publish(self, content: str, **kwargs: Any) -> PublishResult:
        try:
            did, token = self._login()
            # Bluesky post limit: 300 graphemes
            text = content[:300]
            import datetime
            record = {
                "$type": "app.bsky.feed.post",
                "text": text,
                "createdAt": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            }
            resp = self._post(
                f"{self._BASE}/com.atproto.repo.createRecord",
                {"repo": did, "collection": "app.bsky.feed.post", "record": record},
                headers={"Authorization": f"Bearer {token}"},
            )
            uri = resp.get("uri", "")
            rkey = uri.split("/")[-1] if uri else ""
            handle = self.env["BLUESKY_HANDLE"]
            post_url = f"https://bsky.app/profile/{handle}/post/{rkey}" if rkey else ""
            return PublishResult(True, "bluesky", post_url)
        except Exception as exc:  # noqa: BLE001
            return PublishResult(False, "bluesky", error=str(exc))


# ---------------------------------------------------------------------------
# Twitter / X  (API v2)
# ---------------------------------------------------------------------------
# Setup: Apply for Twitter Developer access, create an app, generate User Access Token.
# Env:   TWITTER_BEARER_TOKEN  (for app-only) or
#        TWITTER_ACCESS_TOKEN + TWITTER_ACCESS_TOKEN_SECRET (for user-context posting)
# Note:  Posting requires user-context (OAuth 1.0a or OAuth 2.0 PKCE).

class TwitterPublisher(BasePlatformPublisher):
    platform_name = "twitter"
    required_env = ["TWITTER_ACCESS_TOKEN"]

    def publish(self, content: str, **kwargs: Any) -> PublishResult:
        token = self.env["TWITTER_ACCESS_TOKEN"]
        text = content[:280]
        try:
            resp = self._post(
                "https://api.twitter.com/2/tweets",
                {"text": text},
                headers={"Authorization": f"Bearer {token}"},
            )
            tweet_id = (resp.get("data") or {}).get("id", "")
            url = f"https://x.com/i/web/status/{tweet_id}" if tweet_id else ""
            return PublishResult(True, "twitter", url)
        except Exception as exc:  # noqa: BLE001
            return PublishResult(False, "twitter", error=str(exc))


# ---------------------------------------------------------------------------
# LinkedIn
# ---------------------------------------------------------------------------
# Setup: Create a LinkedIn App, get OAuth 2.0 access token with w_member_social scope.
# Env:   LINKEDIN_ACCESS_TOKEN, LINKEDIN_AUTHOR_URN (urn:li:person:YOUR_ID)

class LinkedInPublisher(BasePlatformPublisher):
    platform_name = "linkedin"
    required_env = ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_AUTHOR_URN"]

    def publish(self, content: str, **kwargs: Any) -> PublishResult:
        token = self.env["LINKEDIN_ACCESS_TOKEN"]
        author = self.env["LINKEDIN_AUTHOR_URN"]
        body = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": content[:3000]},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        try:
            resp = self._post(
                "https://api.linkedin.com/v2/ugcPosts",
                body,
                headers={"Authorization": f"Bearer {token}", "X-Restli-Protocol-Version": "2.0.0"},
            )
            post_id = resp.get("id", "")
            return PublishResult(True, "linkedin", f"https://www.linkedin.com/feed/update/{post_id}")
        except Exception as exc:  # noqa: BLE001
            return PublishResult(False, "linkedin", error=str(exc))


# ---------------------------------------------------------------------------
# Reddit
# ---------------------------------------------------------------------------
# Setup: Create an app at https://www.reddit.com/prefs/apps (script type).
# Env:   REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD
#        REDDIT_SUBREDDIT (e.g. programming)

class RedditPublisher(BasePlatformPublisher):
    platform_name = "reddit"
    required_env = ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME", "REDDIT_PASSWORD", "REDDIT_SUBREDDIT"]

    def _get_token(self) -> str:
        creds = urllib.parse.urlencode({
            "grant_type": "password",
            "username": self.env["REDDIT_USERNAME"],
            "password": self.env["REDDIT_PASSWORD"],
        }).encode()
        import base64
        b64 = base64.b64encode(f"{self.env['REDDIT_CLIENT_ID']}:{self.env['REDDIT_CLIENT_SECRET']}".encode()).decode()
        req = urllib.request.Request(
            "https://www.reddit.com/api/v1/access_token",
            data=creds, method="POST",
            headers={"Authorization": f"Basic {b64}", "User-Agent": "promoagent/0.2", "Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            return json.loads(resp.read())["access_token"]

    def publish(self, content: str, title: str = "", **kwargs: Any) -> PublishResult:
        try:
            token = self._get_token()
            subreddit = self.env["REDDIT_SUBREDDIT"]
            post_title = title or content[:100]
            resp = self._post_form(
                "https://oauth.reddit.com/api/submit",
                {"sr": subreddit, "kind": "self", "title": post_title, "text": content, "resubmit": "true"},
                headers={"Authorization": f"Bearer {token}", "User-Agent": "promoagent/0.2"},
            )
            errors = resp.get("json", {}).get("errors") or []
            if errors:
                return PublishResult(False, "reddit", error=str(errors))
            post_url = (resp.get("json", {}).get("data") or {}).get("url", "")
            return PublishResult(True, "reddit", post_url)
        except Exception as exc:  # noqa: BLE001
            return PublishResult(False, "reddit", error=str(exc))


# ---------------------------------------------------------------------------
# Weibo
# ---------------------------------------------------------------------------
# Setup: Register at open.weibo.com, get OAuth2 access token.
# Env:   WEIBO_ACCESS_TOKEN

class WeiboPublisher(BasePlatformPublisher):
    platform_name = "weibo"
    required_env = ["WEIBO_ACCESS_TOKEN"]

    def publish(self, content: str, **kwargs: Any) -> PublishResult:
        token = self.env["WEIBO_ACCESS_TOKEN"]
        text = content[:140]  # Weibo 140-char limit
        try:
            resp = self._post_form(
                "https://api.weibo.com/2/statuses/share.json",
                {"access_token": token, "status": text},
            )
            post_id = resp.get("id", "")
            return PublishResult(True, "weibo", f"https://weibo.com/{post_id}" if post_id else "")
        except Exception as exc:  # noqa: BLE001
            return PublishResult(False, "weibo", error=str(exc))


# ---------------------------------------------------------------------------
# Registry & dispatcher
# ---------------------------------------------------------------------------

_PUBLISHERS: dict[str, type[BasePlatformPublisher]] = {
    "telegram":  TelegramPublisher,
    "bluesky":   BlueskyPublisher,
    "twitter":   TwitterPublisher,
    "linkedin":  LinkedInPublisher,
    "reddit":    RedditPublisher,
    "weibo":     WeiboPublisher,
}

# Platforms with no public API — content is generated, posting is manual
NO_API_PLATFORMS = {
    "xiaohongshu": "小红书（无公开发布 API，请手动发布）",
    "zhihu":       "知乎（无公开发布 API，请手动发布）",
    "wechat":      "微信（需企业认证公众号，请手动发布）",
}


def available_publishers(env: dict[str, str] | None = None) -> dict[str, BasePlatformPublisher]:
    """Return a dict of configured publishers based on available env vars."""
    env = env or os.environ
    result: dict[str, BasePlatformPublisher] = {}
    for name, cls in _PUBLISHERS.items():
        pub = cls(env)
        if pub.is_configured():
            result[name] = pub
    return result


def publish_content(
    platform: str,
    content: str,
    *,
    env: dict[str, str] | None = None,
    **kwargs: Any,
) -> PublishResult:
    """Publish content to a single platform by name."""
    env = env or os.environ

    if platform in NO_API_PLATFORMS:
        return PublishResult(False, platform, error=NO_API_PLATFORMS[platform])

    cls = _PUBLISHERS.get(platform.lower())
    if not cls:
        return PublishResult(False, platform, error=f"Unknown platform: {platform}. Supported: {', '.join(_PUBLISHERS)}")

    pub = cls(env)
    if not pub.is_configured():
        missing = [k for k in pub.required_env if not env.get(k)]
        return PublishResult(False, platform, error=f"Missing env vars: {', '.join(missing)}")

    return pub.publish(content, **kwargs)


def load_content_from_assets(output_dir: str | Path, platform: str) -> str:
    """Read generated markdown content for a platform from launch-assets/."""
    from .platforms import get_platform

    out = Path(output_dir)
    # Resolve aliases (xhs → xiaohongshu, x → twitter) so the glob matches the
    # canonical filename written by optimize._platform_filename().
    spec = get_platform(platform)
    canonical = spec.key if spec else platform
    # Try exact/canonical match first, then fuzzy on the raw input, then any promo file.
    candidates = list(out.glob(f"*{canonical}*.md"))
    if not candidates:
        candidates = list(out.glob(f"*{platform}*.md"))
    if not candidates:
        candidates = list(out.glob("promo-*.md"))
    if not candidates:
        raise FileNotFoundError(f"No promo file found in {output_dir} for platform '{platform}'")
    return candidates[0].read_text(encoding="utf-8")

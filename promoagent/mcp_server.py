"""MCP Server for Source2Launch.

Exposes 8 tools to AI clients (Claude Desktop, Cursor, Continue, etc.):
  s2l_analyze          — analyze any source, return structured evidence
  s2l_evidence_brief   — extract evidence brief (no AI, fast)
  s2l_check_risks      — list launch risk flags
  s2l_promote          — generate AI promotional content
  s2l_optimize         — generate a complete launch-assets folder
  s2l_refine           — refine content with feedback (stateless)
  s2l_list_platforms   — list all supported promotional platforms
  s2l_list_publishers  — list configured social media publishers

Install:  pip install "promoagent[mcp]"
Run:      promoagent-mcp

Claude Desktop config
  macOS:   ~/Library/Application Support/Claude/claude_desktop_config.json
  Windows: %APPDATA%\\Claude\\claude_desktop_config.json

  {
    "mcpServers": {
      "promoagent": { "command": "promoagent-mcp" }
    }
  }

Then in Claude, just say:
  "用 promoagent 分析 https://github.com/owner/repo 并生成小红书文案"
"""

from __future__ import annotations

import json
import os
from typing import Any

# FastMCP is imported lazily so the module can be imported even without the mcp
# extra; the ImportError only surfaces when main() is actually called.
try:
    from mcp.server.fastmcp import FastMCP
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False  # type: ignore[assignment]

from .analyzer import analyze_target
from .ai import generate_ai_content, ai_config, dispatch_chat
from .optimize import run_optimize
from .promo_prompts import build_evidence_brief, build_refine_messages
from .publish import available_publishers, NO_API_PLATFORMS, _PUBLISHERS
from .examples import find_examples


# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

if _MCP_AVAILABLE:
    mcp = FastMCP(
        "promoagent",
        instructions=(
            "Source2Launch: 把 GitHub 仓库、PDF 论文、本地项目转成多平台推广文案。\n"
            "主要工具：s2l_analyze（提取证据）、s2l_promote（AI 生成文案）、"
            "s2l_optimize（生成 launch-assets 文件夹）。\n"
            "AI 参数从环境变量 / .env 文件自动读取，也可在工具调用时通过 model 参数覆盖。"
        ),
    )
else:
    mcp = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ai_opts(model: str, base_url: str, api_key: str) -> dict[str, Any]:
    """Build an options dict from the optional override params."""
    opts: dict[str, Any] = {}
    if model:
        opts["model"] = model
    if base_url:
        opts["base_url"] = base_url
    if api_key:
        opts["api_key"] = api_key
    return opts


def _fmt_risks(risks: list) -> str:
    if not risks:
        return "✅ 未发现明显风险"
    return "\n".join(
        f"- ⚠️ {r.get('message', r) if isinstance(r, dict) else r}"
        for r in risks
    )


def _fmt_evidence(result: dict[str, Any]) -> str:
    """Format an analyze_target result into a readable Markdown summary."""
    proj = result.get("project") or {}
    ev = result.get("evidence") or {}
    repo = result.get("repository") or {}

    lines: list[str] = [
        f"## 📦 {proj.get('name') or '（未识别项目名）'}",
        "",
        proj.get("description") or "（无描述）",
        "",
    ]
    if proj.get("repositoryUrl"):
        lines += [f"🔗 仓库：{proj['repositoryUrl']}", ""]
    if proj.get("homepage"):
        lines += [f"🌐 主页：{proj['homepage']}", ""]

    install = proj.get("installCommand") or (
        (ev.get("keyActions") or [None])[0]
    )
    if install:
        lines += ["**安装 / 使用**", f"```\n{install}\n```", ""]

    if ev.get("headings"):
        lines.append("**关键章节**")
        lines += [f"- {h}" for h in ev["headings"][:8]]
        lines.append("")

    if ev.get("proofPoints"):
        lines.append("**证明点**")
        lines += [f"- {p}" for p in ev["proofPoints"][:5]]
        lines.append("")

    if repo:
        meta: list[str] = []
        if repo.get("language"):
            meta.append(f"语言：{repo['language']}")
        if repo.get("filesScanned"):
            meta.append(f"扫描文件：{repo['filesScanned']}")
        if meta:
            lines += ["**仓库信息**", "  ".join(meta), ""]

    risks = ev.get("launchRisks") or []
    lines += ["**发布风险**", _fmt_risks(risks)]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

if _MCP_AVAILABLE:

    @mcp.tool()
    def s2l_analyze(target: str = ".") -> str:
        """Analyze any source and return structured evidence — no AI required.

        Accepts:
          - Local directory path (scans README, package.json, pyproject.toml, …)
          - GitHub URL        (fetches README + repo metadata via GitHub API)
          - Local PDF path    (extracts text from academic paper or document)
          - Free-text string  (restaurant, product, event description, etc.)

        Returns a human-readable Markdown summary: project name, description,
        install command, key sections, proof points, and launch-readiness risks.
        Fast — no AI call, completes in seconds.
        """
        try:
            result = analyze_target(target)
            return _fmt_evidence(result)
        except Exception as exc:  # noqa: BLE001
            return f"❌ 分析失败：{exc}"

    @mcp.tool()
    def s2l_evidence_brief(target: str = ".") -> str:
        """Extract a compact evidence brief from any source — no AI, instant.

        Returns the concise Markdown brief that Source2Launch uses as factual
        grounding when generating promotional content. Lighter than s2l_analyze;
        useful for quickly checking what facts the tool will work from.

        Accepts the same inputs as s2l_analyze (path / URL / PDF / text).
        """
        try:
            result = analyze_target(target)
            return build_evidence_brief(result)
        except Exception as exc:  # noqa: BLE001
            return f"❌ 提取失败：{exc}"

    @mcp.tool()
    def s2l_check_risks(target: str = ".") -> str:
        """Check launch readiness and flag potential issues — no AI required.

        Inspects the source for: missing README, no install command, TODO/FIXME
        markers, absent screenshots / visuals, missing license, and more.
        Returns a numbered list of risk items to address before launching.
        """
        try:
            result = analyze_target(target)
            proj = result.get("project") or {}
            ev = result.get("evidence") or {}
            risks = ev.get("launchRisks") or []

            name = proj.get("name") or target
            lines = [f"## 🚦 发布准备检查 — {name}", ""]
            if not risks:
                lines.append("✅ **一切就绪，未发现明显风险！**")
            else:
                lines.append(f"发现 **{len(risks)}** 项需要注意：\n")
                for i, r in enumerate(risks, 1):
                    msg = r.get("message") if isinstance(r, dict) else str(r)
                    lines.append(f"{i}. ⚠️ {msg}")
            return "\n".join(lines)
        except Exception as exc:  # noqa: BLE001
            return f"❌ 检查失败：{exc}"

    @mcp.tool()
    def s2l_promote(
        target: str,
        platforms: str = "all",
        prompt_note: str = "",
        no_examples: bool = False,
        model: str = "",
        base_url: str = "",
        api_key: str = "",
    ) -> str:
        """Generate AI-powered promotional content from any source.

        Runs a three-stage pipeline:
          1. Extract evidence from the source (no AI)
          2. Find reference examples from similar content (optional, skippable)
          3. Generate platform-specific copy grounded in the evidence

        Args:
            target:       GitHub URL, local path, PDF path, or free-text description.
            platforms:    Comma-separated list or "all". Options:
                          xhs, zhihu, wechat, twitter, linkedin, reddit,
                          showhn, producthunt, telegram, bluesky, weibo, all.
            prompt_note:  Extra writing instructions, e.g. "不要营销腔，像维护者复盘".
            no_examples:  Skip Stage 1 example search for faster generation.
            model:        Override AI model (default: from .env / PROMOAGENT_MODEL).
            base_url:     Override API base URL (default: from .env).
            api_key:      Override API key (default: from .env).

        Returns generated promotional content in Markdown, ready to copy-paste.
        """
        try:
            result = analyze_target(target)
            opts = _ai_opts(model, base_url, api_key)

            brief = build_evidence_brief(result)
            if prompt_note:
                brief += f"\n\n**写作指令**：{prompt_note}"

            examples: list[str] = []
            if not no_examples:
                try:
                    examples = find_examples(
                        result, platform=platforms, ai_options=opts, verbose=False
                    )
                except Exception:  # noqa: BLE001
                    pass  # examples are best-effort; generation continues without them

            content = generate_ai_content(
                result,
                platform=platforms,
                brief_section=brief,
                examples=examples,
                options=opts,
            )

            # generate_ai_content always returns {"content": <parsed>, "messages": [...], ...}
            inner: dict = content.get("content") or {}
            promotions: dict = inner.get("promotions") or {}
            if not promotions:
                raw = json.dumps(inner, ensure_ascii=False, indent=2)[:2000]
                return f"⚠️ AI 未生成推广内容。原始返回：\n```json\n{raw}\n```"

            proj_name = (result.get("project") or {}).get("name") or target
            lines: list[str] = []

            positioning = inner.get("positioning") or ""
            if positioning:
                lines += [f"**定位**：{positioning}", ""]

            lines += [f"## 🚀 推广文案 — {proj_name}", ""]

            for plat, item in promotions.items():
                if isinstance(item, str):
                    md, notes = item, ""
                else:
                    md = item.get("markdown") or ""
                    notes = item.get("publishNotes") or ""
                lines += [f"### {plat}", "", md.strip(), ""]
                if notes:
                    lines += [f"> 💡 {notes}", ""]

            return "\n".join(lines)
        except Exception as exc:  # noqa: BLE001
            return f"❌ 生成失败：{exc}"

    @mcp.tool()
    def s2l_optimize(
        target: str = ".",
        output_dir: str = "launch-assets",
        model: str = "",
        base_url: str = "",
        api_key: str = "",
    ) -> str:
        """Generate a complete launch-assets folder with all platform files.

        Writes the following files to output_dir:
          INDEX.md              — navigation and pre-launch checklist
          evidence-summary.md   — extracted project facts
          promo-xhs.md          — 小红书 content
          promo-zhihu.md        — 知乎 content
          promo-twitter.md      — Twitter/X content
          promo-show-hn.md      — Show HN post
          promo-product-hunt.md — Product Hunt tagline + description
          … (AI picks the best 2-5 platforms for the content)

        Args:
            target:     GitHub URL, local path, PDF, or free-text (default: current dir).
            output_dir: Destination folder (default: launch-assets).
            model / base_url / api_key: Override AI config (default: from .env).
        """
        try:
            result = analyze_target(target)
            opts = _ai_opts(model, base_url, api_key)

            brief = build_evidence_brief(result)
            examples: list[str] = []
            try:
                examples = find_examples(
                    result, platform="all", ai_options=opts, verbose=False
                )
            except Exception:  # noqa: BLE001
                pass

            ai_result = generate_ai_content(
                result,
                platform="all",
                brief_section=brief,
                examples=examples,
                options=opts,
            )
            # run_optimize expects the inner content dict (with "promotions"),
            # not the generate_ai_content wrapper (which also has "messages", "model", etc.)
            summary = run_optimize(
                result,
                output_dir=output_dir,
                ai_content=ai_result.get("content"),
            )

            generated = summary.get("generated") or []
            out_path = summary.get("outputDir") or output_dir
            proj_name = (result.get("project") or {}).get("name") or target

            lines = [
                f"## ✅ launch-assets 已生成 — {proj_name}",
                f"📁 输出目录：`{out_path}`",
                "",
                f"生成了 **{len(generated)}** 个文件：",
            ]
            for fname in generated:
                lines.append(f"  - `{fname}`")
            lines += [
                "",
                "**下一步建议**",
                "- 运行 `s2l_list_publishers` 查看已配置的发布渠道",
                "- 打开 `INDEX.md` 按发布检查清单逐项核对后再发布",
            ]
            return "\n".join(lines)
        except Exception as exc:  # noqa: BLE001
            return f"❌ 生成失败：{exc}"

    @mcp.tool()
    def s2l_refine(
        content: str,
        feedback: str,
        platform: str = "",
        model: str = "",
        base_url: str = "",
        api_key: str = "",
    ) -> str:
        """Refine promotional content based on feedback — stateless, no session needed.

        Paste in any promotional text and describe what to change; the tool returns
        an improved version. Works independently of s2l_promote / s2l_optimize.

        Args:
            content:  The promotional copy to improve (plain text or Markdown).
            feedback: What to change, e.g. "太广告腔了，改得更像真实探店体验".
            platform: Optional platform hint for tone adjustment (xhs, twitter, etc.).
            model / base_url / api_key: Override AI config (default: from .env).
        """
        try:
            opts = _ai_opts(model, base_url, api_key)
            cfg = ai_config(opts)
            messages = build_refine_messages(content, feedback, platform)
            refined = dispatch_chat(messages, cfg)
            return f"## ✏️ 改进后文案\n\n{refined}"
        except Exception as exc:  # noqa: BLE001
            return f"❌ 改进失败：{exc}"

    @mcp.tool()
    def s2l_list_platforms() -> str:
        """List all supported promotional platforms with style notes and API status.

        Returns a reference table to help choose which platforms to target
        and which support automated publishing vs. manual copy-paste.
        """
        rows = [
            ("xhs",          "小红书",       "图文种草，口语化，1500字以内，多标签",    "❌ 手动"),
            ("zhihu",        "知乎",         "专业深度，结构化，技术/学术内容",          "❌ 手动"),
            ("wechat",       "微信公众号",    "正式，适合长内容，企业号可 API",          "❌ 手动"),
            ("twitter",      "Twitter / X",  "简洁有力，280字，英文为主",              "✅ API"),
            ("linkedin",     "LinkedIn",     "专业人脉，3000字，B2B 调性",             "✅ API"),
            ("reddit",       "Reddit",       "社区驱动，真实，技术友好",               "✅ API"),
            ("showhn",       "Show HN",      "Hacker News，极简，技术原创，需 karma",   "❌ 手动"),
            ("producthunt",  "Product Hunt", "发布日，tagline + 描述 + first comment", "❌ 手动"),
            ("telegram",     "Telegram",     "频道/群组，Markdown 支持，无字数限制",    "✅ API"),
            ("bluesky",      "Bluesky",      "去中心化，300字，类 Twitter",            "✅ API"),
            ("weibo",        "微博",         "大众社交，140字，话题标签",              "✅ API"),
        ]
        lines = [
            "## 📋 支持的推广平台",
            "",
            "| 参数值 | 平台 | 内容风格 | 自动发布 |",
            "|--------|------|---------|---------|",
        ]
        for key, name, style, pub in rows:
            lines.append(f"| `{key}` | {name} | {style} | {pub} |")
        lines += [
            "",
            "**用法提示**",
            "- `s2l_promote` 的 `platforms` 参数填写上表左列的参数值，多个用逗号分隔",
            "- `platforms=\"all\"` 让 AI 自动选择最适合的 2–5 个平台",
            "- `s2l_list_publishers` 查看哪些 API 平台已配置好凭证",
        ]
        return "\n".join(lines)

    @mcp.tool()
    def s2l_list_publishers() -> str:
        """List all social media publishers and their current configuration status.

        Shows which platforms are ready to publish (credentials configured in
        environment variables or .env file) and which require manual posting.
        Includes quick setup hints for unconfigured platforms.
        """
        try:
            configured = available_publishers()

            lines = ["## 📡 社交媒体发布渠道", ""]

            if configured:
                lines.append("### ✅ 已配置（可直接通过 API 发布）")
                for name in configured:
                    lines.append(f"- **{name}**")
                lines.append("")

            env_hints = {
                "telegram": "TELEGRAM_BOT_TOKEN  +  TELEGRAM_CHAT_ID",
                "bluesky":  "BLUESKY_HANDLE  +  BLUESKY_APP_PASSWORD",
                "twitter":  "TWITTER_ACCESS_TOKEN",
                "linkedin": "LINKEDIN_ACCESS_TOKEN  +  LINKEDIN_AUTHOR_URN",
                "reddit":   "REDDIT_CLIENT_ID  +  REDDIT_CLIENT_SECRET  +  REDDIT_USERNAME  +  REDDIT_PASSWORD",
                "weibo":    "WEIBO_ACCESS_TOKEN",
            }
            unconfigured = [k for k in _PUBLISHERS if k not in configured]
            if unconfigured:
                lines.append("### ⚙️ 未配置（在 .env 中添加以下环境变量即可启用）")
                for k in unconfigured:
                    lines.append(f"- **{k}** — `{env_hints.get(k, '')}`")
                lines.append("")

            lines.append("### 📝 手动发布（平台无公开发布 API）")
            for name, reason in NO_API_PLATFORMS.items():
                lines.append(f"- **{name}** — {reason}")

            if not configured:
                lines += [
                    "",
                    "💡 **快速上手**：配置 Telegram Bot 最简单（无需申请开发者资质）",
                    "   1. 向 @BotFather 发送 `/newbot` 获取 Token",
                    "   2. 在 .env 中填写 `TELEGRAM_BOT_TOKEN=xxx` 和 `TELEGRAM_CHAT_ID=xxx`",
                ]

            return "\n".join(lines)
        except Exception as exc:  # noqa: BLE001
            return f"❌ 查询失败：{exc}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the MCP server using stdio transport."""
    if not _MCP_AVAILABLE:
        import sys
        print(
            "promoagent-mcp: 缺少 mcp 依赖，请先安装：\n"
            "  pip install \"promoagent[mcp]\"\n",
            file=sys.stderr,
        )
        sys.exit(1)
    mcp.run()


if __name__ == "__main__":
    main()

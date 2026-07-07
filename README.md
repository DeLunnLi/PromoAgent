<div align="center">

# 🚀 PromoAgent

**AI Promotion Agent for Launches, Ads, and Multi-Platform Copy**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-0.3.0-orange.svg)](https://github.com/DeLunnLi/PromoAgent/releases)

*Turn projects, products, and ideas into ready-to-publish marketing content*

[Quick Start](#quick-start) • [Features](#features) • [Installation](#installation) • [Documentation](#documentation)

</div>

---

## ✨ What is PromoAgent?

PromoAgent is an **AI-powered promotion agent** that reads your source evidence (GitHub repos, PDFs, product descriptions, release notes) and turns it into campaign-ready copy, launch assets, and ad-image briefs.

**Unlike other AI copywriters:**
- ✅ **Evidence-first**: Analyzes your actual content before generating
- ✅ **Multi-platform**: One input → tailored content for XHS, Twitter, LinkedIn, etc.
- ✅ **Campaign planning**: Audience segments, channel fit, launch sequence, and creative variants
- ✅ **Release-ready**: Translate README/CHANGELOG/release notes into user-facing announcements
- ✅ **Ad creative briefs**: Generate platform-aware image prompts and overlay copy from the same evidence
- ✅ **No hallucination**: All claims are traceable to source evidence
- ✅ **Agent architecture**: MCP server, browser automation, API publishing

```bash
# Example: Promote a GitHub repo across all platforms
promoagent draft https://github.com/user/awesome-project

# Example: Generate ad copy from a product description
promoagent draft "AI writing tool, $19/mo, boosts productivity 10x" --platforms twitter,linkedin

# Example: Interactive editing - pause at blueprint stage
promoagent draft ./CHANGELOG.md --interactive

# Example: Generate with images and save to folder
promoagent draft . --image --output-dir launch-assets
```

> **Note**: `promote`/`optimize`/`refine` are deprecated. Use `draft` for better results.

---

## 🎬 Demo

```bash
$ promoagent analyze .

╔═══════════════════════════════════════════════════════════╗
║  PromoAgent — Your AI Agent for Every Promotion          ║
╚═══════════════════════════════════════════════════════════╝

📊 Project Analysis
┌───────────────┬──────────────────────────────────────────┐
│ Name          │ PromoAgent                               │
│ Description   │ AI Promotion Agent for Launches...       │
│ Install       │ pip install -e .                         │
│ Topics        │ ai, promotion, marketing, launch         │
│ Files Scanned │ 44                                       │
└───────────────┴──────────────────────────────────────────┘

✓ No significant risks detected
```

---

## 🚀 Quick Start

### 1. Install

```bash
git clone https://github.com/DeLunnLi/PromoAgent.git
cd PromoAgent
pip install -e .
```

### 2. Setup

```bash
# Interactive setup wizard
promoagent setup
```

Or manually create `.env`:
```bash
# Using ModelScope (recommended for China users)
PROMOAGENT_MODELSCOPE_API_KEY=ms-your-token
PROMOAGENT_BASE_URL=https://api-inference.modelscope.cn/v1
PROMOAGENT_MODEL=Qwen/Qwen3.5-397B-A17B

# Or using OpenAI
PROMOAGENT_API_KEY=sk-your-key
PROMOAGENT_MODEL=gpt-4o-mini
```

### 3. Verify

```bash
promoagent doctor
```

### 4. Generate Content

```bash
# Analyze a project
promoagent analyze .

# Generate promotional content (new unified command)
promoagent draft .

# Interactive editing - pause to edit blueprint
promoagent draft . --interactive

# Create complete launch package with images
promoagent draft . --image --output-dir launch-assets/

# Continue from saved blueprint
promoagent draft --resume --stage produce
```

---

## 🎯 Features

### Multi-Source Input

| Source | Command Example |
|--------|-----------------|
| **GitHub Repo** | `promoagent draft https://github.com/user/repo` |
| **Local Project** | `promoagent draft .` |
| **PDF Paper** | `promoagent draft paper.pdf` |
| **Product Description** | `promoagent draft "AI tool, $19/mo"` |
| **Website URL** | `promoagent draft https://example.com` |

### Supported Platforms

| Platform | Key | API Support | Best For |
|----------|-----|-------------|----------|
| 小红书 | `xhs` | ❌ Manual | Visual storytelling, lifestyle |
| 知乎 | `zhihu` | ❌ Manual | Technical deep-dives |
| 微信 | `wechat` | ❌ Manual | Long-form articles |
| Twitter/X | `twitter` | ✅ Auto | Quick announcements |
| LinkedIn | `linkedin` | ✅ Auto | B2B professional |
| Reddit | `reddit` | ✅ Auto | Community engagement |
| Show HN | `showhn` | ❌ Manual | Tech launches |
| Product Hunt | `producthunt` | ❌ Manual | Product launches |
| Telegram | `telegram` | ✅ Auto | Channel broadcasts |
| Bluesky | `bluesky` | ✅ Auto | Decentralized social |
| 微博 | `weibo` | ✅ Auto | Chinese social |

### Three-Stage Generation Pipeline

```bash
# 1. RESEARCH - Extract facts and strategy
promoagent draft <target> --stage research

# 2. BLUEPRINT - Structured editable content
promoagent draft <target> --stage blueprint --interactive

# 3. PRODUCE - Platform-native content
promoagent draft --resume --stage produce
```

### Legacy Commands (Deprecated)

```bash
# Old commands - still work but show deprecation warning
promoagent promote <target> --platform all --ai  # Use 'draft' instead
promoagent optimize <target> --ai --output <dir>  # Use 'draft' instead
promoagent refine "feedback"                       # Use 'draft --resume --edit' instead
```

---

## 🛠️ Installation Options

### Basic Install
```bash
pip install -e .
```

### With Optional Features
```bash
# Web UI
pip install -e ".[web]"

# Browser auto-fill
pip install -e ".[fill]"

# MCP Server (Claude Desktop integration)
pip install -e ".[mcp]"

# PDF OCR support
pip install -e ".[ocr]"

# Everything
pip install -e ".[web,fill,mcp,ocr]"
```

---

## 🤖 MCP Server Integration

Use PromoAgent directly inside AI tools (Claude Desktop, Cursor, etc.) via the
Model Context Protocol. Install the MCP extra, then point your tool at the
`promoagent-mcp` command:

```bash
pip install "promoagent[mcp]"
```

Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "promoagent": {
      "command": "promoagent-mcp"
    }
  }
}
```

Then ask naturally:
> "Analyze https://github.com/owner/repo and draft Xiaohongshu + Twitter content.
> Show me the blueprint first so I can edit it before producing."

### Available Tools

| Tool | Description |
|------|-------------|
| `s2l_analyze(target)` | Analyze a source (GitHub URL / local path / file / free text); returns evidence + a `source_id` handle. |
| `s2l_list_platforms()` | List supported platforms with format, style, and API-support flags. |
| `s2l_research(target, search=True)` | Run the research stage: extract facts, strategy, and information gaps. Returns `source_id`. |
| `s2l_blueprint(source_id)` | Generate the editable blueprint (content elements + variants) from research. |
| `s2l_edit_blueprint(source_id, edits)` | Apply edits (content updates, variant selection, reorder, add/remove element, set structure). Returns a markdown preview. |
| `s2l_produce(source_id, platforms?)` | Generate platform-native content from the blueprint. |
| `s2l_draft(target, platforms?, search=True)` | One-shot full pipeline (research → blueprint → produce). |
| `s2l_image_brief(source_id, ...)` | Resolve the ad-copy brief (title/subtitle/cta/badges) for image text overlay. |
| `s2l_build_image_prompt(source_id, platform, skill, model, ...)` | Build a text image-generation prompt for any external image model (DALL·E / Qwen-Image). Pass `model` to pick the prompt language. |

### Two Ways to Use It

**One-shot** — when you just want the content:

```
s2l_draft("https://github.com/owner/repo", platforms=["xiaohongshu", "twitter"])
```

**Staged** — when you want to inspect and edit the blueprint first (the AI
tool's UI is great for this):

```
1. s2l_research("https://github.com/owner/repo")        → source_id + gaps
2. s2l_blueprint(source_id)                              → elements + variants
3. s2l_edit_blueprint(source_id, {"hook-main": "新钩子"}) → preview
4. s2l_produce(source_id, platforms=["xiaohongshu"])     → final content
```

State persists across calls via `source_id`, so you can step through and edit
without re-running earlier stages.

---

## 📚 Documentation

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PROMOAGENT_API_KEY` | OpenAI-compatible API key | - |
| `PROMOAGENT_MODEL` | Model name | `gpt-4o-mini` |
| `PROMOAGENT_BASE_URL` | API base URL | `https://api.openai.com/v1` |
| `PROMOAGENT_MAX_TOKENS` | Max generation tokens | `4096` |
| `PROMOAGENT_TEMPERATURE` | Generation temperature | `0.7` |
| `TAVILY_API_KEY` | Tavily search API | - |
| `EXA_API_KEY` | Exa semantic search | - |
| `FIRECRAWL_API_KEY` | Web scraping | - |

### Publishing Credentials

| Platform | Variables |
|----------|-----------|
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| Twitter | `TWITTER_ACCESS_TOKEN` |
| LinkedIn | `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AUTHOR_URN` |
| Reddit | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, ... |
| Bluesky | `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` |
| Weibo | `WEIBO_ACCESS_TOKEN` |

---

## 🎨 Advanced Usage

### Custom Writing Style

```bash
promoagent promote . \
  --prompt-preset launch \
  --prompt-note "Like a founder post-mortem, not marketing speak" \
  --context ./notes.md \
  --ai
```

### Interactive Ad Images

```bash
promoagent optimize . \
  --image \
  --image-platforms xhs,wechat \
  --image-skill auto \
  --image-interactive \
  --image-variants 2
```

`--image-skill auto` will choose a creative skill by recommendation type:
`b2b-saas` for software/tools, `food-local` for restaurant and local lifestyle,
`product-hero` for products, `event-poster` for events, `research-editorial` for papers,
and `service-trust` for services/courses. Use `xhs-lifestyle` when the image should feel
like a Xiaohongshu creator cover instead of a corporate banner.
These built-in image skills use a structured prompt-spec approach inspired by the
[GPT-Image2-Skill](https://github.com/wuyoscar/GPT-Image2-Skill) gallery/craft workflow:
canvas and layout first, then concrete scene systems, material, lighting, palette, and checks.
The generator treats the AI image as a clean campaign background plate and renders final
headline/CTA typography locally, so the subject stays out of the copy-safe zone and Chinese
text remains crisp.

For non-interactive runs, pass the ad copy directly:

```bash
promoagent optimize . \
  --image \
  --image-platforms xhs \
  --image-skill b2b-saas \
  --image-title "一键把项目变成推广素材" \
  --image-subtitle "自动读证据，生成多平台文案和广告封面" \
  --image-cta "立即生成" \
  --image-badges "小红书封面,多平台推广,证据驱动"
```

### Browser Auto-Fill

```bash
# Fill content to Xiaohongshu (requires login)
promoagent fill xhs --assets-dir ./launch-assets

# Fill to Twitter
promoagent fill twitter --content "Your tweet here"
```

### Batch Publishing

```bash
# Dry run
promoagent publish telegram --dry-run

# Actually publish
promoagent publish telegram
```

---

## 🏗️ Architecture

```
Input → Evidence Extraction → AI Generation → Multi-Platform Output
  │          │                    │                │
  │          │                    │                ├── Twitter
  │          │                    │                ├── LinkedIn
  │          │                    │                ├── 小红书
  │          │                    │                └── ...
  │          │                    │
  │          │                    └── Stage 1: Example Search
  │          │                        Stage 2: Content Generation
  │          │                        Stage 3: Auto-Improvement
  │          │
  │          └── README, package.json, GitHub API, PDF, etc.
  │
  └── GitHub URL / Local Path / PDF / Description / Website
```

---

## 🧪 Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
python -m unittest discover -s tests_py -v

# Run specific test
python -m unittest tests_py.test_python_core.PythonCoreTest.test_analyzes_healthy_repo -v
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with [Rich](https://github.com/Textualize/rich) for beautiful CLI output
- Multi-provider AI support via OpenAI-compatible APIs
- Inspired by the need for evidence-based content generation

---

<div align="center">

**[⬆ Back to Top](#promoagent)**

Made with ❤️ by [DeLunnLi](https://github.com/DeLunnLi)

</div>

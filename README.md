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

PromoAgent is an **AI-powered promotion agent** that reads your source evidence (GitHub repos, PDFs, product descriptions) and generates platform-native marketing copy.

**Unlike other AI copywriters:**
- ✅ **Evidence-first**: Analyzes your actual content before generating
- ✅ **Multi-platform**: One input → tailored content for XHS, Twitter, LinkedIn, etc.
- ✅ **No hallucination**: All claims are traceable to source evidence
- ✅ **Agent architecture**: MCP server, browser automation, API publishing

```bash
# Example: Promote a GitHub repo across all platforms
promoagent promote https://github.com/user/awesome-project --platform all --ai

# Example: Generate ad copy from a product description
promoagent promote "AI writing tool, $19/mo, boosts productivity 10x" --platform twitter,linkedin --ai
```

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

# Generate promotional content
promoagent promote . --platform all --ai

# Create complete launch package
promoagent optimize . --ai --output launch-assets/
```

---

## 🎯 Features

### Multi-Source Input

| Source | Command Example |
|--------|-----------------|
| **GitHub Repo** | `promoagent promote https://github.com/user/repo --ai` |
| **Local Project** | `promoagent promote . --ai` |
| **PDF Paper** | `promoagent promote paper.pdf --ai` |
| **Product Description** | `promoagent promote "AI tool, $19/mo" --ai` |
| **Website URL** | `promoagent promote https://example.com --ai` |

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

### Three Core Commands

```bash
# 1. ANALYZE - Extract evidence
promoagent analyze <target>

# 2. PROMOTE - Generate copy
promoagent promote <target> --platform <platform> --ai

# 3. OPTIMIZE - Create launch package
promoagent optimize <target> --ai --output <dir>
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

Use PromoAgent directly in Claude Desktop:

```json
{
  "mcpServers": {
    "promoagent": {
      "command": "promoagent-mcp"
    }
  }
}
```

Then simply ask:
> "Analyze https://github.com/owner/repo and generate Xiaohongshu and Twitter content"

**Available Tools:**
- `pa_analyze` - Analyze any source
- `pa_promote` - Generate promotional copy
- `pa_optimize` - Create launch-assets folder
- `pa_refine` - Iterate on content
- `pa_check_risks` - Validate launch readiness

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

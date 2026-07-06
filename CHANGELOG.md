# Changelog

All notable changes to PromoAgent will be documented in this file.

## [0.3.0] - 2024-07-06

### 🎉 Major Release - Rebrand to PromoAgent

PromoAgent is the evolution of Source2Launch, now supporting not just code projects but also products, services, ads, and any content that needs promotion.

### ✨ New Features

- **Rich CLI Interface**: Beautiful terminal output with progress bars, tables, and panels
- **Interactive Setup Wizard**: `promoagent setup` for first-time configuration
- **Doctor Command**: `promoagent doctor` to check configuration and dependencies
- **Product Ad Support**: Generate ads from product descriptions, not just code
- **Enhanced Platforms Command**: Visual table of all supported platforms

### 🔧 Improvements

- **Multi-Provider AI**: Support for OpenAI, Anthropic, Gemini, Ollama, and ModelScope
- **Parallel Search**: Tavily and Exa searches run in parallel for faster example finding
- **Smart Caching**: Cache GitHub API and Firecrawl responses
- **Structured Logging**: Better observability with structured logs

### 🏗️ Architecture

- **Modular Design**: Optional extras for web UI, browser fill, MCP server, OCR
- **MCP Server**: Full integration with Claude Desktop and other MCP clients
- **Browser Automation**: Playwright-based auto-fill for platforms without API

### 📦 Package Changes

- Renamed package from `source2launch` to `promoagent`
- Updated all CLI commands: `promoagent <command>`
- Updated environment variables: `PROMOAGENT_*`

---

## [0.2.0] - 2024-07-04 (Source2Launch Legacy)

### Source2Launch Release

- Initial stable release as Source2Launch
- Three core commands: `analyze`, `promote`, `optimize`
- Multi-platform support (XHS, Twitter, LinkedIn, etc.)
- MCP Server with 8 tools
- Browser auto-fill for manual platforms

---

## Legend

- ✨ New Features
- 🔧 Improvements
- 🐛 Bug Fixes
- 🏗️ Architecture
- 📦 Package
- 📝 Documentation

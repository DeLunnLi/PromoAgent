# Changelog

本项目的所有 notable 变更记录在此。

## [Unreleased]

## [0.2.0] — 2026-06-29

### 新定位

- 项目定位收敛为 **Source2Launch：开源项目和论文的发布内容生成 CLI**
- 核心使命：从真实来源证据生成可人工审核的多平台推广文案、Markdown 发布资料、配图素材和发布计划

### 新增

- `promote`：从仓库、PDF、Markdown 或 URL 生成平台文案
- `optimize`：生成完整 `launch-assets/` 发布资料包
- `markdown`：生成项目介绍、README 草稿、Launch Kit 或推广笔记
- `publish`：生成发布审核计划，默认不自动发布
- `--skill paper/code/paper-code/social/visual/markdown`：按任务选择默认受众、语气、提示词和审核重点
- ModelScope / Gradio 图片生成与图片编辑入口

### 调整

- README 首屏改为 `source2launch promote` / `source2launch optimize` 主路径
- 包名和公开命令统一为 `source2launch`
- 环境变量文档统一为 `SOURCE2LAUNCH_*`，旧 `STAR_UP_*` 仅作为兼容 fallback
- 移除历史命令别名、独立诊断入口和 HTML 报告公开入口
- AI 审核输出不再展示规则参考分或等级，改为证据缺口与人工审核问题

## [0.1.2] — 2026-06-22

### 定位调整

- **大模型驱动**：项目理解、介绍、审计、推广文案以 LLM 为主；本地规则仅收集 evidence / CI

### 新增

- `--read-project` / `--brief` 默认调用大模型生成 `project-summary.md`
- `src/project-brief.js`：`buildProjectIntakeWithAi`、`formatAiProjectBriefMarkdown`
- `--local` / `--no-ai`：强制本地证据摘要

### 改进

- `--optimize` 始终生成 AI 项目理解（有 Key 时）
- README 与工作流文档重写为大模型优先叙事

## [0.1.1] — 2026-06-22

### 改进

- README 首屏、安装路径（`npx github:`）、小红书终稿、npm 发布清单

## [0.1.0] — 2026-06-22

### 定位

- 确立产品定位：**开源项目的 AI Star 增长顾问**

### 新增

- 支持本地目录与 GitHub 仓库 URL 扫描
- 8 维 star 转化评分（README、视觉、安装、Demo、Topics、Examples、首屏、发布信息）
- 本地推广文案生成：小红书、微信
- `--launch-pack` 多渠道发布包（Show HN、Reddit/V2EX、X、Product Hunt）
- `--readme-suggestions` README 首屏改写建议
- `--boost` AI 一键流程：star 诊断、改进计划、README 改写、7 渠道推广文案
- `--template` Markdown 模板渲染与 `--output` 文件输出
- 可选 AI 模式（OpenAI 兼容 Chat Completions API）
- 发布前风险检查（TODO 占位符、缺失 License 等）

### 工具链

- CI 矩阵测试 Node 18 / 20 / 22
- `--json` 与 `--fail-under` 供 CI 集成

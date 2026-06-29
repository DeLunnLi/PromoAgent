# Source2Launch

> 项目/论文发布内容生成 CLI。本文档是仓库级介绍，主使用入口见 README。

## 一句话介绍

Source2Launch 读取开源项目、论文 PDF、README、Markdown 笔记和网页来源证据，生成可人工审核的多平台推广文案、Markdown 发布资料和配图素材。

## 解决的问题

很多开源项目和论文并不是“没有内容可讲”，而是缺少从真实证据到平台表达的转换层：

- README 或论文摘要太技术化，普通读者不知道为什么要点开。
- 小红书、知乎、微信、Show HN、Product Hunt 的写法差异很大，不能复用同一段文案。
- 直接让模型写文案容易编造效果、用户数、benchmark 或推广话术。
- 发布前需要人工审核，但缺少一份清晰的发布计划。

Source2Launch 的目标是把这条链路收敛成一个 CLI 工作流。

## 核心工作流

```sh
source2launch promote . --platform xhs
source2launch promote paper.pdf --skill paper --platform zhihu
source2launch optimize . --output launch-assets/
source2launch publish promotion.json --platform xhs --publish-mode review
```

## 核心能力

- `promote`：从项目或论文生成单平台/全平台推广文案。
- `optimize`：生成完整 `launch-assets/`，包括项目理解、平台文案、英文发布包和配图。
- `markdown`：生成项目介绍、README 草稿、Launch Kit 或推广笔记。
- `publish`：生成发布审核计划，保留人工最后确认。
- `--skill`：按 paper、code、paper-code、social、visual、markdown 等任务选择默认策略。
- `--prompt-preset` / `--prompt-note`：追加写作风格和审核约束。

## 设计原则

- 先证据，后文案：所有结论应来自 README、论文、代码、截图、表格或用户提供资料。
- 先策略，后平台：先生成 `promotionStrategy`，再写各平台 Markdown。
- 先审核，后发布：CLI 默认只生成草稿和发布计划，不自动提交平台内容。
- 兼容旧配置：旧环境变量仍可读取，但公开文档和示例统一使用 `SOURCE2LAUNCH_*`。

## 项目结构

```text
bin/                 CLI 入口
src/cli.js           命令解析和主流程
src/ai.js            OpenAI-compatible / ModelScope 文本模型调用
src/promo-prompts.js 多平台推广 prompt 和 JSON schema
src/skills.js        任务技能定义
src/prompts.js       prompt preset 定义
src/optimize.js      launch-assets 生成
src/publish.js       人工审核发布计划
src/modelscope.js    图片生成/编辑入口
docs/                使用指南和方法论文档
templates/           兼容模板
test/                Node test 测试
```

## 下一步适合优化的方向

- 为 `--context` 增加远程 URL 内容抓取和来源引用。
- 为 paper promotion 增加论文图表裁剪、关键页截图和视觉素材清单。
- 为 `publish assist` 增加平台字段映射导出，但继续禁止自动点击发布。
- 增加远程 URL 内容抓取和来源引用，让 OpenReview、arXiv、GitHub 页面可以直接进入证据层。

---

*本文档由维护者整理，反映当前 Source2Launch 主路径。*

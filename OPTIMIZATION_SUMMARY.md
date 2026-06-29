# Source2Launch 优化总结

## 当前产品定义

Source2Launch 是一个面向开源项目和论文的发布内容生成 CLI：

```sh
source2launch promote <repo-or-paper-url>
source2launch optimize <repo-or-paper-url> --output launch-assets/
source2launch markdown <repo-or-paper-url> --markdown-type launch
source2launch publish promotion.json --publish-mode review
```

主目标不是继续做 Star 诊断，而是把真实来源材料转换为可审核、可发布的推广内容。

## 已完成的收敛

### 1. 主入口收敛

- `promote`：快速生成平台文案。
- `optimize`：生成完整发布资料包。
- `markdown`：生成本地 Markdown 文档。
- `publish`：生成审核计划，默认不执行发布。

历史命令别名、独立诊断入口和 HTML 报告入口已从公开 CLI 表面移除；审核材料改由 `content-review.md`、`campaign.json` 和平台 Markdown 承载。

### 2. AutoPR-style 任务层

新增并接通：

- `--skill paper`
- `--skill code`
- `--skill paper-code`
- `--skill social`
- `--skill visual`
- `--skill markdown`

这些 skill 会设置默认平台、受众、语气、prompt presets 和 review focus。AI prompt 中会显式要求先生成 `promotionStrategy`，再生成各平台 Markdown。

### 3. Prompt Presets

默认启用：

- `grounded`
- `author`
- `realworld`
- `autopr`
- `scholardag`
- `human`

用户可追加：

```sh
source2launch promote paper.pdf \
  --platform zhihu \
  --prompt-preset paper,visual \
  --prompt-note "像研究者读论文，不要营销腔"
```

### 4. 文件目标支持

`paper.pdf`、`notes.md`、`intro.txt` 可以直接作为 target：

```sh
source2launch promote paper.pdf --platform zhihu
source2launch markdown notes.md --markdown-type promo
```

CLI 会自动把 PDF/文本文件作为证据，并以文件所在目录作为分析上下文。

### 5. 人工审核闸门

`publish` 已兼容当前 `promotions.*.markdown` 输出结构：

```sh
source2launch promote . --platform all --json --output promotion.json
source2launch publish promotion.json --platform xhs --publish-mode review
source2launch publish promotion.json --platform producthunt --publish-mode assist --yes
```

`assist` 只生成浏览器辅助填草稿所需字段，不登录、不绕过风控、不点击最终发布。

## 当前推荐用法

### 开源项目

```sh
source2launch promote . --skill code --platform launch
source2launch optimize . --output launch-assets/
```

### 论文

```sh
source2launch promote paper.pdf --skill paper --platform zhihu
source2launch optimize paper.pdf --output launch-assets/
```

### 论文 + 代码

```sh
source2launch promote paper.pdf \
  --skill paper-code \
  --context ./repo-notes.md \
  --platform all \
  --json \
  --output promotion.json
```

## 后续优化建议

1. 远程 `--context` 抓取：支持 arXiv/OpenReview/GitHub URL 的内容读取和引用。
2. 论文视觉证据：自动提取摘要页、方法图、结果表格，生成小红书/知乎配图计划。
3. 真实案例集：维护 `examples/source-pairs.json`，对比真实推广文案和生成文案。
4. 发布适配器：继续以 review/assist 为主，官方 API 可用的平台才做真正发布。
5. 平台发布辅助：为官方 API 稳定的平台增加 adapter；没有稳定 API 的平台继续只生成人工审核与草稿填充计划。

## 验证

```sh
npm test
npm pack --dry-run
```

# Generated Result

这不是手写模板，而是当前仓库实际运行 Source2Launch 后得到的结果节选。

本次运行环境没有配置 `SOURCE2LAUNCH_API_KEY` / `SOURCE2LAUNCH_MODELSCOPE_API_KEY`，所以结果来自本地证据模式。配置模型后，同一流程会继续生成 AI 推广文案和配图。

## Input

使用仓库内 fixture 项目作为输入：

```sh
./bin/source2launch optimize test/fixtures/healthy-repo --output /tmp/source2launch-demo-opt
```

输入项目的 README 证据：

````markdown
# Repo Pulse

Repo Pulse reads GitHub repositories and turns source evidence into concise technical social posts.

![Repo Pulse demo](./docs/demo.gif)

## Quickstart

```sh
npx repo-pulse .
```
````

## Generated Files

命令生成了这些文件：

```text
/tmp/source2launch-demo-opt/
  INDEX.md
  campaign.json
  project-summary.md
  content-review.md
  heuristic-audit.md
  readme-suggestions.md
  launch-pack.md
  improvement-report.md
  promo-xhs.md
  promo-wechat.md
  promo-zhihu.md
  promo-en.md
  promo-copy.md
  platform/
    xhs.md
    zhihu.md
    wechat.md
    show-hn.md
    producthunt-kit.md
```

## Generated Result: INDEX.md

```markdown
# repo-pulse · Launch Assets

> 由 `source2launch optimize` 自动生成

资料检查：**已生成本地检查报告**（见 `heuristic-audit.md`）
项目理解：**本地证据摘要**（配置 API Key 后由大模型生成）
AI 平台文案：**未生成（需配置 API Key）**

## 文件清单

- [heuristic-audit.md](./heuristic-audit.md) — 本地资料检查（CI）
- [readme-suggestions.md](./readme-suggestions.md)
- [launch-pack.md](./launch-pack.md)
- [improvement-report.md](./improvement-report.md)
- [project-summary.md](./project-summary.md) — 大模型项目理解（推荐先读）
- [promo-xhs.md](./promo-xhs.md) — 小红书
- [promo-wechat.md](./promo-wechat.md) — 微信
- [promo-zhihu.md](./promo-zhihu.md) — 知乎
- [promo-en.md](./promo-en.md) — 英文平台
- [promo-copy.md](./promo-copy.md) — 推广索引
- [platform/xhs.md](./platform/xhs.md) — 平台草稿
- [platform/wechat.md](./platform/wechat.md) — 平台草稿
- [platform/zhihu.md](./platform/zhihu.md) — 平台草稿
- [platform/show-hn.md](./platform/show-hn.md) — 平台草稿
- [platform/producthunt-kit.md](./platform/producthunt-kit.md) — 平台草稿
- [content-review.md](./content-review.md) — 人工审核清单
- [campaign.json](./campaign.json) — 活动状态（机器可读）

## 推荐使用顺序

1. 阅读 `project-summary.md`（大模型项目理解，推荐起点）
2. 阅读 `content-review.md`，确认事实、图片、链接和平台语气
3. 到 `platform/` 选择要发布的平台草稿
4. 英文渠道优先看 `platform/show-hn.md` 和 `platform/producthunt-kit.md`
5. 配图使用 `images/` 中的封面，必要时再用 `--promo-brief` 重新生成
6. 需要自动化对接时读取 `campaign.json`；需要改 README 时再看 `readme-suggestions.md`

## 项目信息

- 项目：repo-pulse
- 仓库：https://github.com/example/repo-pulse
- 安装：`npx repo-pulse .`
```

## Generated Result: project-summary.md

````markdown
> 未配置 API Key，以下为本地证据摘要。配置 `SOURCE2LAUNCH_MODELSCOPE_API_KEY` 后重新运行，将由大模型阅读并介绍项目。

# 项目阅读摘要

> 项目：repo-pulse · 本地证据摘要

## 一句话
Generate technical social posts from repository evidence.

## 安装命令
```sh
npx repo-pulse .
```

## README 首屏片段
Repo Pulse reads GitHub repositories and turns source evidence into concise technical social posts.

## 优先改进
- Use language like "Scan X to find Y" or "Helps Z do W without V".

## 写作提示
- 推广文案必须原样使用安装命令：npx repo-pulse .
````

## Generated Result: launch-pack.md

```markdown
# repo-pulse · 多渠道发布包

> 由 Source2Launch 生成 · 开源项目发布资料参考

资料检查：见 `heuristic-audit.md`（仅供 CI / 资料完整度参考）

## 发布阻碍

未发现明显阻碍，可以开始推广。

## GitHub About

**Description：** Generate technical social posts from repository evidence
**Topics：** github, readme, open-source, tweet, social

## Show HN

**Title：** Show HN: repo-pulse - Generate technical social posts from repository evidence

I built repo-pulse, an open source project for open source maintainers and indie developers.

Generate technical social posts from repository evidence

What it does:
- Explains the project value early
- Shows visual proof instead of only text
- Offers a short copy-paste install path
- Has a visible demo or usage path

Try it: npx repo-pulse .
Repo: https://github.com/example/repo-pulse

I would appreciate feedback on whether the README makes the value clear in the first 10 seconds.

## Product Hunt

**Tagline：** Generate technical social posts from repository evidence

Hi Product Hunt - I built repo-pulse.

Generate technical social posts from repository evidence

The project is open source: https://github.com/example/repo-pulse
You can try it with: npx repo-pulse .

I would love feedback on the positioning and README clarity.
```

## What This Demonstrates

- Source2Launch 会从 README 和 package metadata 中抽取项目名、描述、安装命令、视觉证据和仓库链接。
- 在没有 API key 时，它仍能生成本地 Markdown 发布资料和 Launch Kit。
- `content-review.md` 和 `campaign.json` 会把人工审核、平台草稿和发布状态组织成一个完整 campaign。
- 配置模型后，同一 `optimize` 流程会把 `promo-xhs.md`、`promo-zhihu.md`、`promo-wechat.md`、`promo-en.md` 替换成 AI 生成的完整平台文案，并尝试生成配图。

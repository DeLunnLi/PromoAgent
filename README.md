# Source2Launch

把开源项目、论文 PDF、README 和技术笔记转成可人工审核的多平台发布内容。

Source2Launch 不从空白 prompt 开始写宣传稿。它先读取来源证据，再生成推广策略、平台文案、Markdown 发布资料、配图提示和发布审核计划。

```sh
source2launch promote . --platform xhs
source2launch promote paper.pdf --platform zhihu
source2launch optimize . --output launch-assets/
```

[查看生成示例](docs/generated-examples.md) · [Task Skills](docs/skills.md) · [Prompt Presets](docs/prompt-presets.md) · [Image Guide](docs/image-optimization-guide.md)

## 产品定义

Source2Launch 是一个给开源作者、论文作者和技术内容维护者使用的 CLI：

- 输入：GitHub 仓库、本地项目、PDF、Markdown 笔记、README、补充资料。
- 处理：抽取证据，形成自己的 `promotionStrategy`，再按平台改写。
- 输出：小红书、知乎、微信、Show HN、X/Twitter、Product Hunt 等平台的草稿和配图素材。
- 发布：默认只生成审核计划，不自动点击发布。

## 安装

发布到 npm 前，推荐用 GitHub 包临时运行，并显式指定 `source2launch` 这个 bin：

```sh
npm exec --package github:DeLunnLi/Source2Launch -- source2launch promote . --platform xhs
```

本地开发：

```sh
git clone https://github.com/DeLunnLi/Source2Launch.git
cd Source2Launch
npm install
npm link
source2launch promote . --platform all
```

`source2launch` 是主命令。

## 生成文案

```sh
source2launch promote . --platform xhs
source2launch promote . --platform zhihu
source2launch promote paper.pdf --platform all
source2launch promote https://github.com/user/repo --platform launch
```

常用平台：

| 平台 | 参数 |
| --- | --- |
| 小红书 | `--platform xhs` |
| 知乎 | `--platform zhihu` |
| 微信 | `--platform wechat` |
| 英文发布包 | `--platform launch` |
| 全平台 | `--platform all` |

任务技能会选择默认受众、语气、提示词预设和审核重点：

```sh
source2launch promote paper.pdf --skill paper --platform zhihu
source2launch promote . --skill code --platform launch
source2launch promote paper.pdf --skill paper-code --context ./repo-notes.md --platform all
source2launch promote . --skill social --prompt-note "像维护者复盘，不要营销腔"
```

## 生成发布资料包

```sh
source2launch optimize . --output launch-assets/
source2launch optimize paper.pdf --output launch-assets/
source2launch optimize . --pdf docs/paper.pdf --output launch-assets/
```

输出结构：

```text
launch-assets/
  INDEX.md
  campaign.json
  project-summary.md
  content-review.md
  promo-xhs.md
  promo-zhihu.md
  promo-wechat.md
  promo-en.md
  promo-copy.md
  platform/
    xhs.md
    zhihu.md
    wechat.md
    show-hn.md
    producthunt-kit.md
  images/
```

`INDEX.md` 会把材料按阅读顺序排好：项目理解、人工审核清单、平台草稿、英文发布包、配图和机器可读的 `campaign.json`。

## 生成 Markdown 文档

如果只需要本地文档，不需要完整推广包：

```sh
source2launch markdown . --markdown-type project --output PROJECT.md
source2launch markdown . --markdown-type readme --output README.draft.md
source2launch markdown . --markdown-type launch --output LAUNCH.md
source2launch markdown paper.pdf --markdown-type promo --output PROMO.md
```

支持类型：`project`、`readme`、`launch`、`promo`、`all`。

## 人工审核与发布计划

Source2Launch 默认不会发布内容。你可以先导出 JSON，再生成审核计划：

```sh
source2launch promote . --platform all --json --output promotion.json
source2launch publish promotion.json --platform xhs --publish-mode review
source2launch publish promotion.json --platform producthunt --publish-mode assist --yes
```

`assist` 只描述登录态浏览器辅助填草稿所需字段。最终发布/提交按钮仍由用户手动点击。

## 配置模型

复制 `.env.example` 并填入自己的密钥：

```sh
cp .env.example .env
```

ModelScope 推荐配置：

```sh
SOURCE2LAUNCH_MODELSCOPE_API_KEY=ms-your-token
SOURCE2LAUNCH_BASE_URL=https://api-inference.modelscope.cn/v1
SOURCE2LAUNCH_MODEL=Qwen/Qwen3.5-397B-A17B
```

图片生成可使用 Gradio 或 ModelScope。先 dry-run 查看项目证据生成的配图提示词，再决定是否调用模型：

```sh
source2launch image . --platform xhs --dry-run
source2launch image . --platform xhs --provider modelscope --output cover.jpg
source2launch image paper.pdf --platform wechat --provider gradio --base-url http://127.0.0.1:7860 --output cover.png
source2launch image . --provider modelscope --model FireRedTeam/FireRed-Image-Edit-1.1 --image-url https://example.com/reference.png --prompt "改成更适合小红书首图的技术推广封面"
```

图片命令只从环境变量读取密钥，例如 `SOURCE2LAUNCH_MODELSCOPE_API_KEY`；不要把真实 key 写进命令、README 或提交记录。

如果需要给其他本地工具提供图片生成/编辑 API，可以启动本地服务：

```sh
source2launch-api --host 127.0.0.1 --port 4317 --token your-local-token
curl http://127.0.0.1:4317/health
```

`source2launch-api` 现在由 Python 实现，接口不会接收客户端传入的模型密钥；请只在服务端环境变量中配置 key。

## 审核清单

生成内容后建议检查：

- 文案中的事实是否来自 README、论文、截图、表格、命令或代码证据。
- 论文结论、benchmark、用户数、star 数、媒体报道是否被模型编造。
- 平台语气是否自然，是否需要删减广告腔。
- 配图是否展示真实来源证据，而不是虚构结果。
- 发布账号、链接、图片和标签是否正确。

## CI / 本地检查

保留少量 CI / 本地检查入口：

```sh
source2launch . --fail-under 70
source2launch . --json > report.json
source2launch . --intro -o PROJECT_INTRO.md
```

这些命令主要用于本地资料检查、项目介绍文档生成和兼容已有工作流。历史命令别名、独立检查入口和 HTML 报告入口已移除。

## Python 迁移

项目正在逐步从 JavaScript 迁移到 Python。当前 npm 发布包的主命令 `source2launch` 和 `source2launch-api` 已是 Python shebang 脚本，发布清单不再包含 `src/`。仓库里的 `src/` 仅作为历史迁移参考和旧测试基线保留。Python 版已覆盖本地仓库/Markdown/TXT/PDF/URL 输入分析、Markdown 生成、`optimize` 本地资料包、`publish` 审核计划、promotion prompt payload、OpenAI-compatible / ModelScope 文本模型调用、ModelScope / Gradio 图片生成入口，以及图片 API 服务。

```sh
python3 -m source2launch analyze . --json
python3 -m source2launch analyze paper.md --json
python3 -m source2launch markdown . --markdown-type launch --output LAUNCH.md
python3 -m source2launch promote . --platform xhs --json
python3 -m source2launch promote . --platform all --ai --json --output promotion.json
python3 -m source2launch image . --platform xhs --dry-run
python3 -m source2launch image . --platform xhs --provider modelscope --output cover.jpg
python3 -m source2launch optimize . --output launch-assets/
python3 -m source2launch optimize . --ai --output launch-assets/
python3 -m source2launch publish promotion.json --platform xhs --publish-mode review
```

Python 测试：

```sh
npm run test:python
```

## 开发

```sh
npm install
npm test
npm run test:python
npm run test:js   # optional legacy baseline
npm pack --dry-run
```

## License

[MIT](LICENSE)

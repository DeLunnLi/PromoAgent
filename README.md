# Source2Launch

把开源项目、论文 PDF 和 GitHub 仓库转成多平台推广文案。

Source2Launch 先读取来源证据，再调 AI 生成推广内容——不从空白 prompt 开始写，不编造数据。

```sh
source2launch promote https://github.com/user/repo --platform all --ai
source2launch promote paper.pdf --platform zhihu --ai
source2launch optimize . --ai --output launch-assets/
```

## 安装

```sh
git clone https://github.com/DeLunnLi/Source2Launch.git
cd Source2Launch
pip install -e .
```

复制配置模板：

```sh
cp .env.example .env
# 填入你的 API Key
```

## 配置模型

`.env` 文件会在启动时自动加载，无需手动 `source`。

**ModelScope（推荐）：**

```sh
SOURCE2LAUNCH_MODELSCOPE_API_KEY=ms-your-token
SOURCE2LAUNCH_BASE_URL=https://api-inference.modelscope.cn/v1
SOURCE2LAUNCH_MODEL=Qwen/Qwen3.5-397B-A17B
```

**OpenAI 兼容服务：**

```sh
SOURCE2LAUNCH_API_KEY=sk-your-key
SOURCE2LAUNCH_MODEL=gpt-4o-mini
```

## 三个命令

### `analyze` — 查看证据

```sh
source2launch analyze .
source2launch analyze https://github.com/openai/whisper
source2launch analyze paper.pdf --json
```

输出项目名称、描述、安装命令、文件数量和发布风险提示。

### `promote` — 生成推广文案

```sh
# 本地项目
source2launch promote . --platform xhs --ai
source2launch promote . --platform all --ai

# GitHub 仓库（直接拉取，无需 clone）
source2launch promote https://github.com/user/repo --platform all --ai

# 论文 PDF
source2launch promote paper.pdf --platform zhihu --ai

# 导出 JSON
source2launch promote . --platform all --ai --json -o promo.json
```

常用平台参数：

| 参数 | 平台 |
|---|---|
| `--platform xhs` | 小红书 |
| `--platform zhihu` | 知乎 |
| `--platform wechat` | 微信 |
| `--platform launch` | Show HN + Product Hunt |
| `--platform all` | 全部平台 |

### `optimize` — 保存到文件夹

```sh
source2launch optimize . --ai --output launch-assets/
source2launch optimize https://github.com/user/repo --ai
source2launch optimize paper.pdf --ai --output launch-assets/
```

输出结构：

```
launch-assets/
  INDEX.md              ← 文件导航和发布前提醒
  evidence-summary.md   ← 项目证据摘要
  promo-xhs.md          ← 小红书文案
  promo-zhihu.md
  promo-wechat.md
  promo-show-hn.md
  promo-product-hunt.md
  promo-twitter.md
  promo-linkedin.md
  promo-reddit.md
```

## Prompt 控制

```sh
# 指定写作风格
source2launch promote . --prompt-preset autopr --ai
source2launch promote paper.pdf --prompt-preset paper,scholardag --ai

# 添加写作指令
source2launch promote . --prompt-note "像维护者复盘，不要营销腔" --ai

# 附加上下文文件
source2launch promote . --context ./notes.md --ai
```

内置 Preset（共 17 个）：`autopr` `scholardag` `grounded` `author` `paper` `launch` `launchkit` `tweet` `zhihu` `xhs` `wechat` 等。

## 审核清单

生成内容后建议确认：

- 文案中的事实是否来自 README、论文、截图、命令或代码证据
- benchmark、用户数、star 数、媒体报道是否被模型编造
- 平台语气是否自然，是否需要删减广告腔
- 发布账号、链接和标签是否正确

## 开发

```sh
pip install -e .
python3 -m unittest discover -s tests_py -v
```

## License

[MIT](LICENSE)

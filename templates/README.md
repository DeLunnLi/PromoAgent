# 模板说明

`templates/` 存放 Source2Launch 的 Markdown 模板，主要用于无 API 场景下生成基础推广文案和发布资料草稿。

渲染方式：

```sh
source2launch promote . --platform xhs
source2launch promote . --platform wechat
source2launch markdown . --markdown-type launch --output LAUNCH.md
source2launch optimize . --output launch-assets/
```

## 占位符

| 占位符 | 含义 |
|--------|------|
| `{{project_name}}` | 项目或包名 |
| `{{project_description}}` | 一句话描述 |
| `{{repo_url}}` | GitHub 仓库地址 |
| `{{homepage_url}}` | 项目主页或 Demo 地址 |
| `{{install_command}}` | 最短安装 / 快速开始命令 |
| `{{stars}}` | GitHub star 数（如有） |
| `{{topics}}` | Topics 或 keywords |
| `{{strengths}}` | 可用于发布的已验证亮点 |
| `{{top_fixes}}` | 发布前需要补充的资料 |
| `{{target_users}}` | 目标用户群 |
| `{{tags}}` | 平台标签 / 话题 |

## 文件一览

| 路径 | 用途 |
|------|------|
| `promo/xiaohongshu.md` | 小红书：标题备选 + 正文 + 配图建议 |
| `promo/wechat-moments.md` | 微信朋友圈短帖 |
| `promo/wechat-official-account.md` | 微信公众号长文 |
| `audit/improvement-report.md` | 兼容旧模板的资料补充清单 |

本地模板无需 API；需要 AI 个性化文案时使用 `source2launch promote . --platform all` 或 `source2launch optimize . --output launch-assets/`。

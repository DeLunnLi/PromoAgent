# 小红书发布稿（终版 v2）

> 发布前确认：`source2launch promote . --platform xhs` 在本机可跑
> 封面：`launch-assets/images/xhs-cover.png`（result 风格 · 资料检查与发布素材界面）
> 正文源文件：`launch-assets/promo-xhs.md`

## 标题（三选一）

- 开源项目不会写发布文案？我让 AI 先读证据
- 论文/代码怎么发小红书？先生成可审核草稿
- 别空写宣传稿了，先把 README 和论文读完

## 正文（可直接复制）

做了开源项目或论文，最难的不是“写一句宣传语”，而是别把内容写假。😭

以前我经常直接丢给模型一句“帮我写推广文案”，结果不是太营销，就是把论文结论/项目能力写过头。

现在把这件事收敛成了 **Source2Launch**：先读 README、PDF、命令、截图这些证据，再生成小红书/知乎/微信/Show HN 等平台的草稿。

```sh
source2launch promote . --platform xhs
source2launch optimize . --output launch-assets/
```

它会先给出 `promotionStrategy`：主角度、证据链、配图思路和人工审核问题。然后再写平台文案，不是直接套模板。

我现在更常用这两个入口：

- `promote`：快速生成单个平台草稿
- `optimize`：生成完整 `launch-assets/`，包含项目理解、文案和配图

不保证发了就火，但至少能少踩“模型编故事”和“平台风格全一样”的坑。

你们发论文/开源项目时，会先写知乎还是小红书？🤔

GitHub：https://github.com/DeLunnLi/Source2Launch

## 标签

#开源 #GitHub #程序员 #独立开发 #论文阅读 #AI工具 #Source2Launch

## 配图清单

| 顺序 | 内容 |
|------|------|
| 1 | 封面 `launch-assets/images/xhs-cover.png` |
| 2 | 终端 `source2launch optimize . --output launch-assets/` 截图 |
| 3 | `launch-assets/promo-copy.md` 或 `promotionStrategy` 截图 |
| 4 | （可选）README / 论文图表来源证据 |

## 发布时间

工作日 20:00–22:00 或周末上午。

## 评论区预备

- **装不上？** → `npm exec --package github:DeLunnLi/Source2Launch -- source2launch promote . --platform xhs`
- **要 API？** → 复制 `.env.example`，填 ModelScope Token
- **会自动发布吗？** → 不会，默认只生成草稿和审核计划

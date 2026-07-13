# 迁移指南：从旧流程到新流程

## 概述

`promoagent` 已从旧的 `promote`/`optimize`/`refine` 流程迁移到新的三阶段 `draft` 流程。

## 命令映射

| 旧命令 | 新命令 | 说明 |
|--------|--------|------|
| `promoagent promote . --ai` | `promoagent draft .` | 生成推广内容 |
| `promoagent optimize . --ai` | `promoagent draft . --output-dir launch-assets` | 生成并保存文件 |
| `promoagent refine "修改"` | `promoagent draft --resume --edit edits.json` | 编辑并重新生成 |
| `promoagent promote . --ai --platform xiaohongshu` | `promoagent draft . --platforms xiaohongshu` | 指定平台 |
| `promoagent optimize . --ai --image` | `promoagent draft . --image --output-dir launch-assets` | 生成图片 |

## 新功能：Blueprint 编辑

新流程引入了 **Blueprint** 中间格式，可以在生成最终内容前编辑：

```bash
# 1. 生成到 blueprint 阶段并暂停
promoagent draft "项目描述" --interactive

# 2. 编辑 .blueprint.json 文件

# 3. 继续生成最终内容
promoagent draft --resume --stage produce
```

### Blueprint 结构

```json
{
  "version": "2.0",
  "positioning": {
    "one_liner": "一句话定位",
    "core_promise": "核心承诺"
  },
  "elements": [
    {
      "id": "hook-main",
      "type": "hook",
      "label": "开场钩子",
      "content": "当前文案",
      "variants": ["变体A", "变体B", "变体C"],
      "editable": true
    }
  ]
}
```

### 编辑方式

**方式 1：直接编辑 JSON**
```bash
# 修改 .blueprint.json 中的 content 字段
promoagent draft --resume --stage produce
```

**方式 2：使用 edits 文件**
```bash
# 创建 edits.json
{
  "hook-main": "新的钩子文案",
  "_selectVariant": {"cta-main": 1}
}

# 应用编辑
promoagent draft --resume --edit edits.json
```

**方式 3：选择变体**
```bash
# 在 edits.json 中选择变体
{
  "_selectVariant": {
    "hook-main": 0,
    "cta-main": 2
  }
}
```

**方式 4：调整结构**
```bash
# 在 edits.json 中调整元素顺序
{
  "_reorder": ["hook-main", "story-1", "solution-1", "cta-main"]
}
```

## 阶段控制

新流程分为三个阶段：

```bash
# 只运行研究阶段
promoagent draft . --stage research

# 运行到 blueprint（可编辑）
promoagent draft . --stage blueprint

# 从 blueprint 生成最终内容
promoagent draft --resume --stage produce

# 完整流程
promoagent draft . --stage all
```

## 向后兼容

旧命令（`promote` / `optimize` / `refine`）**已在 v0.4 移除**，不再可用。直接使用 `draft`：

```bash
# 旧（已失效）
promoagent promote . --ai
promoagent optimize . --ai
promoagent refine "改一下"

# 新
promoagent draft .
promoagent draft . --output-dir launch-assets
promoagent draft --resume --edit edits.json
```

## v0.4 后续增强（0.4.x）

- **主动搜索参考广告**：`draft` 在 research 阶段自动搜同品类真实帖子/广告塞进 prompt（`--no-search` 可关）。复用 `examples.find_examples`（Tavily + Exa + AI 三路）。
- **research 缺口追问**：`--interactive` 模式下，research 跑完读取 `facts.gaps` 逐条向用户追问，答案合并进 blueprint 的 prompt。
- **MCP server**：`promoagent serve` 或 `promoagent-mcp` 启动 stdio MCP server，暴露 9 个工具（analyze / research / blueprint / edit_blueprint / produce / draft / image_brief / build_image_prompt / list_platforms），供 Claude Desktop / Cursor 调用。`serve` 不再是 Web UI。
- **CLI 清理**：移除 `web.py`（Gradio）、`interactive.py`、`promo_prompts.py`。旧版 `mcp_server.py` 已被新版替换（基于 v0.4 draft pipeline，9 个工具）。`web` extra（gradio）已从 pyproject 删除。

## 主要改进

1. **更清晰的结构**：研究 → Blueprint → 产出
2. **可编辑的中间格式**：Blueprint 允许在生成前调整内容
3. **并行生成**：多平台内容同时生成
4. **阶段缓存**：失败后可从任意阶段恢复
5. **更好的错误处理**：每个阶段独立重试

## 常见问题

### Q: 旧命令会被删除吗？
A: 已经删除。`promote` / `optimize` / `refine` 在 v0.4 移除，请用 `draft`。

### Q: 如何获取之前的功能？
A: 所有旧功能都已迁移到 `draft`，见上方命令映射表。

### Q: Blueprint 文件在哪里？
A: 运行 `promoagent draft . --interactive` 后会生成 `.blueprint.json`。

### Q: 如何批量编辑？
A: 使用 `--edit` 参数传入 JSON 文件，支持批量修改、变体选择、结构调整。

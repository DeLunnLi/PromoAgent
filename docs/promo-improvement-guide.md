# 推广文案与配图改进指南

## 当前问题诊断

**配图问题：**
1. 太抽象 —— 只有图标，没有展示「使用效果」
2. 缺少结果感 —— 用户不知道运行后能得到什么
3. 平台感不足 —— 看起来像通用模板

**文案问题：**
1. 缺少具体场景 —— "开源项目"太泛，没有代入感
2. 缺少情感共鸣 —— 太像产品介绍，不像真实分享
3. 缺少前后对比 —— 没有展示「改进前后的差异」

---

## 改进方案

### 1. 新增配图风格（4 种可选）

```bash
# 效果展示型（推荐）—— 显示资料检查与发布素材界面
SOURCE2LAUNCH_IMAGE_STYLE=result source2launch optimize . --output launch-assets/

# 前后对比型 —— 暗示优化提升
SOURCE2LAUNCH_IMAGE_STYLE=beforeafter source2launch optimize . --output launch-assets/

# 原有的风格仍然可用
SOURCE2LAUNCH_IMAGE_STYLE=poster source2launch optimize . --output launch-assets/      # 标准插画
SOURCE2LAUNCH_IMAGE_STYLE=minimal source2launch optimize . --output launch-assets/     # 极简
SOURCE2LAUNCH_IMAGE_STYLE=terminal source2launch optimize . --output launch-assets/    # 深色终端
SOURCE2LAUNCH_IMAGE_STYLE=vibrant source2launch optimize . --output launch-assets/     # 马卡龙色
```

**效果展示型（result）特点：**
- 深色科技蓝背景
- Stylized 终端窗口界面
- 显示项目摘要、平台文案、配图计划等抽象卡片
- 检查项列表和状态指示，不出现数字评分
- 让用户一眼看到「工具能给出什么结果」

**前后对比型（beforeafter）特点：**
- 左右分栏设计
- 左侧：混乱/暗淡（优化前）
- 右侧：清晰/发光（优化后）
- 暗示转变和提升
- 适合讲故事风格

---

### 2. 改进版文案（含具体场景和对比）

查看改进版文案示例：

- `launch-assets/promo-xhs-improved.md` —— 小红书改进版
- `launch-assets/promo-wechat-improved.md` —— 微信改进版

**小红书改进版特点：**

| 原版 | 改进版 |
|------|--------|
| "做了开源项目，star 一直不动" | "做了开源项目 3 个月，Star 一直停在 20 几个" |
| 功能介绍为主 | 添加「用户在 issue 里说我没讲清楚」的具体场景 |
| 文字描述改进 | **表格展示**改进前后对比 |
| 结尾引导评论 | "你 README 首屏现在是怎么写的？" |

**微信改进版特点：**

- **风格 A**：完整故事线（受挫 → 发现问题 → 改进）
- **风格 B**：简洁版但保留核心痛点
- **风格 C**：方法论视角（Visitor 10 秒体验）
- 添加具体数字和情感细节

---

## 使用示例

### 场景 1：想要效果展示型配图

```bash
# 使用 result 风格生成配图
SOURCE2LAUNCH_IMAGE_STYLE=result source2launch optimize . --output launch-assets/

# 生成的配图会显示：
# - 项目证据卡片
# - 平台文案卡片
# - 配图计划和检查项列表
```

### 场景 2：想要前后对比型配图

```bash
# 使用 beforeafter 风格生成配图
SOURCE2LAUNCH_IMAGE_STYLE=beforeafter source2launch optimize . --output launch-assets/

# 生成的配图会暗示：
# - 优化前的混乱
# - 优化后的清晰
```

### 场景 3：结合改进版文案使用

```bash
# 1. 生成优化包（包含 AI 文案）
SOURCE2LAUNCH_IMAGE_STYLE=result source2launch optimize . --output launch-assets/

# 2. 参考 launch-assets/promo-xhs-improved.md
#    将 AI 生成的文案替换为改进版的结构
#
#    关键修改：
#    - 添加具体时间（3 个月）和数字（20 几个 Star）
#    - 添加「用户在 issue 里说」的具体场景
#    - 添加改进前后对比表格
```

---

## 改进文案要点

### 小红书文案改进要点

1. **添加具体时间/数字**
   - ❌ "做了开源项目"
   - ✅ "做了开源项目 3 个月，Star 一直停在 20 几个"

2. **添加真实场景**
   - ❌ "README 没写好"
   - ✅ "用户在 issue 里说『看了 README 还是没懂这个项目解决什么问题』"

3. **使用对比表格**
   ```markdown
   | 检查项 | 我之前 | 诊断后 |
   |--------|--------|--------|
   | 一句话定位 | 45 字太啰嗦 | 改成 30 字场景句 |
   ```

4. **情感细节**
   - "当时挺受打击的"
   - "我可能还会继续自我感觉良好地写文档"

### 微信文案改进要点

1. **故事线完整**
   - 开头：问题/受挫
   - 中间：发现/转变
   - 结尾：收获/启发

2. **具体数字**
   - "从泛泛介绍改成了有证据链的发布草稿"
   - "准备补录 5 秒演示"

3. **个人口吻**
   - "说实话"
   - "亲测"
   - "我发现"

---

## 配图风格对比

| 风格 | 适用场景 | 视觉特点 |
|------|----------|----------|
| **result** | 效果展示、素材导向 | 显示资料检查、平台文案和配图计划，强调工具价值 |
| **beforeafter** | 讲故事、转变叙事 | 左右对比，暗示提升 |
| poster | 通用、安全 | 标准插画，三图标 |
| minimal | 极简爱好者 | 清爽简约，星形+括号 |
| terminal | 专业开发者 | 深色 IDE 风格 |
| vibrant | 年轻受众 | 马卡龙色，可爱风格 |

---

## 快速上手

```bash
# 1. 复制配置文件模板
cp .env.example .env
# 填入 SOURCE2LAUNCH_MODELSCOPE_API_KEY

# 2. 使用效果展示型配图生成完整包
SOURCE2LAUNCH_IMAGE_STYLE=result source2launch optimize . --output launch-assets/

# 3. 查看生成的配图
open launch-assets/images/xhs-cover.jpg

# 4. 参考改进版文案，替换为自己的具体场景
#    - 修改时间/数字
#    - 添加你的真实使用场景
#    - 调整前后对比内容
```

---

## 后续优化建议

1. **录制 GIF 演示**：README 首屏添加 5-10 秒运行演示
2. **真实使用案例**：收集更多用户「使用前后」的故事
3. **A/B 测试**：尝试不同标题，观察哪个 CTR 更高
4. **发布时间**：工作日 20:00-22:00 或周末上午

---

## 相关文件

- `source2launch/image.py` —— 配图提示词与图片生成入口
- `launch-assets/promo-xhs-improved.md` —— 小红书改进版文案
- `launch-assets/promo-wechat-improved.md` —— 微信改进版文案

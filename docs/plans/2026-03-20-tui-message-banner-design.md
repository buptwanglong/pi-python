# TUI 消息区与 Banner 展示优化 — 设计文档

**日期:** 2026-03-20  
**范围:** basket-tui native（消息区 render + Banner 区）

---

## 1. 目标与背景

- **问题：** 消息区中 User / Tool / Assistant 视觉区分不足（Tool 与 User 同为灰色）、模型输出上下无空行显得挤；Banner 区层次不清、略显凌乱。
- **目标：** 在不改变现有架构（body_lines、render_messages、layout 消费）的前提下，优化颜色、间距与 Banner 层次，提升可读性与区分度。

---

## 2. 消息区优化

### 2.1 Tool 与 User 区分（方案 A：Tool 绿色系底）

- **现状：** User 块 `on grey23`，Tool 块 `on grey19`，两者都是灰色，难以区分。
- **设计：**
  - **User：** 保持 `on grey23`，白字，不变。
  - **Tool：** 改为绿色系底色，在 256 色下选用偏暗的绿（如 `on dark_green` 或 xterm 色表中深绿），保证可读、不刺眼。
  - Tool 块内：工具名首行可保持黄/金强调，正文用浅色（如 dim white 或浅绿灰），与 User 的「灰底白字」形成明确对比。
- **实现要点：** 仅修改 `packages/basket-tui/basket_tui/native/pipeline/render.py` 中 Tool 块所用背景与文字样式常量；保持 Padding/expand 等布局不变。若终端仅支持 256 色，使用 256 色表中绿色系（如 22/28/29 等），避免依赖 24-bit。

### 2.2 Assistant 消息前后空行（方案 A：前后各一行）

- **现状：** Assistant 内容直接与前后块相连，上下无空行，显得挤。
- **设计：**
  - 在每条 Assistant 内容**前**增加 1 行空行，**后**增加 1 行空行（在 `render_messages` 中，打印 assistant 内容前/后各一次空行）。
  - User / Tool 块仍为块内 padding，块与块之间保持现有「每条消息后两行空行」逻辑不变；仅 Assistant 段落获得额外呼吸感。
- **实现要点：** 在 `render.py` 的 `render_messages` 循环中，当 `role == "assistant"` 时：先 `console.print()` 一次（空行），再打印 Markdown/Text，再 `console.print()` 一次（空行），再进入「每条消息后两空行」的统一逻辑。保证输出为 ANSI 行列表，不改变 body_lines 的消费方式。

---

## 3. Banner 区优化（方案 B：层次清晰）

- **现状：** 4 行（Basket、version、空行、tagline），颜色有橙/灰但层次不够，与下方分隔线关系弱。
- **设计：**
  - **品牌行：** 保持「Basket」为主品牌，可加粗（bold）或更醒目橙色，整行权重最高。
  - **Version 行：** 更淡的次要信息（如 dim 或 256 色灰），明确从属于品牌。
  - **Tagline：** 单独一行，通过缩进或细左边框（如 `│` 或单字符竖线 + 空格）与品牌/version 形成视觉分组；颜色可用现有浅橙或略淡，不抢品牌。
  - **分隔线：** Banner 与下方 chrome 之间用 256 色淡灰或双线 `═` 做分隔，与 layout 中现有 `sep_char` 配合（若 layout 仍传 width，banner 不负责画分隔线则仅在 banner 文案上做层次；若希望分隔线风格统一，可在 layout 或 banner 约定同一字符/色）。
- **实现要点：**
  - 修改 `packages/basket-tui/basket_tui/native/ui/banner.py`：`build_banner_lines()` 返回的若干行中，对每行应用上述样式（bold/dim/缩进/边框符）；保持返回 `list[str]` ANSI 行，供 layout 原样使用。
  - 若分隔线样式变更，在 `layout.py` 中调整 `sep_char` 或分隔线 Control 的样式（可选，与「Banner 层次」解耦亦可）。
- **约束：** 不增加 Banner 占行数（仍为 4 行或 3 行若去掉中间空行），不改变 `build_banner_lines(version)` 的签名与返回类型。

---

## 4. 涉及文件与测试

| 区域       | 文件 | 变更概要 |
|------------|------|----------|
| 消息区     | `packages/basket-tui/basket_tui/native/pipeline/render.py` | Tool 绿底样式；Assistant 前后各 1 空行 |
| Banner     | `packages/basket-tui/basket_tui/native/ui/banner.py`       | 品牌/version/tagline 层次与分隔线风格 |
| 布局（可选）| `packages/basket-tui/basket_tui/native/ui/layout.py`       | 仅当统一分隔线样式时微调 sep |

**测试：**

- `tests/native/test_render.py`：已有用例保持通过；可增一条「Assistant 前后有空行」的断言（如检查渲染结果中 assistant 内容前后存在空行）；Tool 块可增断言「输出包含绿色 ANSI」或「无 grey19」等与实现方式匹配的检查。
- `tests/native/test_banner.py`：保证 `build_banner_lines` 返回行数/内容结构不变或符合新约定；可增加对 ANSI 中 bold/dim 或特定分隔符的断言（视最终实现而定）。

---

## 5. 验收

- User 块：灰底白字，不变。
- Tool 块：绿色系底，与 User 一眼可区分；工具名与正文可读。
- Assistant：每条内容上下各有一行空行，与 User/Tool 块视觉分离清晰。
- Banner：品牌突出、version 次要、tagline 有缩进或细边框；分隔线统一（若实现中调整了 layout）。
- 现有测试通过，无回归。

---

*设计确认后，实现计划见 `docs/plans/2026-03-20-tui-message-banner-plan.md`（由 writing-plans 生成）。*

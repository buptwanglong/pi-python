# Basket Native TUI — 对话区滚动与粘性底部

> **状态**：已通过 brainstorming 确认（2026-03-19）。  
> **范围**：`basket-tui` **native**（`prompt_toolkit` + gateway WebSocket）中对话输出区域（`body_lines` → `FormattedTextControl`）。

---

## 1. 目标与验收

| 维度 | 目标 |
|------|------|
| **滚动** | 对话内容超过中间区域可视高度时，可 **滚轮** 与 **Page Up / Page Down** 浏览历史。 |
| **自动跟底** | 默认情况下，新输出到达后视口 **自动滚到最底**（最新内容可见）。 |
| **粘性底部（A）** | 用户 **向上滚动** 后，新输出 **不再** 自动拉回底部；直到用户按 **Ctrl+End**（或与原型一致的快捷键）恢复 **跟随最新**。 |
| **Resize** | 终端尺寸变化后不崩溃；`follow_tail` 为真时仍 **贴底**；否则 **clamp** 滚动偏移。 |

---

## 2. 架构与职责

| 组件 | 职责 |
|------|------|
| **滚动状态**（`run.py` 闭包或小型不可变快照 + 可变容器） | 维护 `follow_tail: bool`、`body_scroll: int`（与 PTK `Window` 的 `vertical_scroll` 语义一致，见 §4 风险）。 |
| **`build_layout`（`layout.py`）** | 对话 `Window`：`get_vertical_scroll`、`always_hide_cursor=True`；`FormattedTextControl`：`get_cursor_position`，与滚动状态一致，避免 `do_scroll` 把视口锁回顶部。 |
| **`run.py` 键绑定** | `pageup` / `pagedown` / `c-end`：更新状态并 `invalidate`；不与现有 `Ctrl+C`、`Esc`、picker 快捷键冲突。 |
| **`Application`** | `mouse_support=True`，使对话区 **滚轮** 可用；若与 `get_vertical_scroll` 冲突，实现中统一为「只改 `body_scroll` + invalidate」。 |
| **统一追加出口** | 所有写入 `body_lines` 的路径经 **`output_put`（或等价单入口）**，保证追加后 `follow_tail` / `invalidate` 行为一致（含 `input_handler` 内当前直接 `append`/`extend` 处）。 |

---

## 3. 数据流与状态机

**状态**

- `follow_tail`：初始 `True`。
- `body_scroll`：用户非跟随模式下的垂直偏移；跟随模式下由 `get_vertical_scroll` 按内容高度与窗口高度计算贴底。

**新内容（WebSocket / `output_put` / 用户消息回显等）**

- 追加 `body_lines` 后 `invalidate`。
- `follow_tail == True`：下一帧绘制时 `get_vertical_scroll` 返回贴底所需值。
- `follow_tail == False`：不自动改变用户视口；若内容缩短导致越界则 **clamp** `body_scroll`。

**用户操作**

- **Page Up / 滚轮向上**：`follow_tail = False`，减小 `body_scroll`（≥ 0），`invalidate`。
- **Page Down / 滚轮向下**：增大 `body_scroll`；若已达底部则 `follow_tail = True`。
- **Ctrl+End**：`follow_tail = True`，下一帧贴底。

**Resize**

- 重算最大可滚动量；`follow_tail` 为真则贴底；否则 clamp `body_scroll`。

---

## 4. 测试、风险与实现注意

**自动化**

- 抽取纯函数：`clamp_scroll`、`page 增量`、`抵底判定` 等，用 **pytest** 覆盖边界（不足一屏、超长、resize 后 clamp）。

**手工**

- 长输出 → 上滚 → 再收新消息视口不动 → Ctrl+End 回底；滚轮与 Page 键行为一致。

**风险**

- **`wrap_lines=True`** 时，`UIContent.line_count` 为 **折行后的行数**，与 `len(body_lines)` 不等。`max_scroll` / `get_vertical_scroll` 必须与 **同一套行高语义** 一致（可结合上一帧 `render_info` 或 spike 验证）。
- **`get_vertical_scroll` 与滚轮**：须确认滚轮修改的是否与回调状态同步，必要时滚轮只更新 `body_scroll`。

**方案回顾（brainstorming）**

- **推荐**：方案一（`Window.get_vertical_scroll` + `FormattedTextControl.get_cursor_position` + 粘性状态）。  
- **备选**：若与 PTK 持续冲突，再评估只读 `Buffer`（方案二）。

---

## 5. 相关文件（实现时）

- `packages/basket-tui/basket_tui/native/run.py` — 状态、键绑定、`mouse_support`、`output_put` 统一入口。  
- `packages/basket-tui/basket_tui/native/ui/layout.py` — 对话 `Window` 滚动与光标锚点。  
- `packages/basket-tui/basket_tui/native/ui/input_handler.py` — 改为通过 `output_put`（或传入的 append 回调）写入，避免绕过滚动语义。  
- `packages/basket-tui/tests/native/` — 新增纯函数单元测试（路径随模块拆分而定）。

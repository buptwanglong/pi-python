# Basket Native TUI — 大模型流式消息展示（方案一：叠加层）

> **状态**：已通过 brainstorming 确认（2026-03-20）。  
> **范围**：`basket-tui` **native** 中 assistant 回复的流式展示：流式阶段纯文本打字机效果，整段结束后再整块 Markdown 定格。

---

## 1. 目标与验收

| 维度 | 目标 |
|------|------|
| **流式阶段** | 收到 `text_delta` 时，对话区**立即**在末尾以**纯文本**（按 width 折行、无 Markdown）逐字/逐块显示，形成打字机效果。 |
| **定格阶段** | `agent_complete` 后，该段内容以现有 **Markdown 渲染**（`render_messages`）整块替换流式预览并保留在 `body_lines` 中，无重复段落。 |
| **状态** | `phase == "streaming"` 时 footer 已有提示；本设计不改变 phase 逻辑，仅增加“正文区流式叠加层”的展示与重绘。 |

---

## 2. 架构与数据流

- **body_lines**：仅存已落盘内容；只在 `agent_complete`、用户发送、tool 块、系统消息时 append，流式过程中**不**往其中写入预览。
- **流式叠加层**：当 `phase == "streaming"` 且 `assembler._buffer` 非空时，界面显示的“当前正文”= **body_lines** + **纯文本折行**（`assembler._buffer` 按 width 折行，不做 Markdown）。
- **获取“当前正文”**：由调用方提供 **get_body_lines()**：每次重绘时调用，返回 `body_lines + 流式预览行`（非流式时仅返回 `body_lines`）。Layout 只依赖该 getter。
- **agent_complete 时**：保持现有逻辑——本段 assistant 经 `render_messages` 渲染后逐行 `output_put` 进 `body_lines`，并清空 buffer；叠加层因 buffer 清空而自然消失。

---

## 3. 组件职责

| 组件 | 变更 |
|------|------|
| **pipeline/render.py** | 新增 `stream_preview_lines(text: str, width: int) -> list[str]`：纯文本按 `width` 折行，返回行列表；不做 ANSI/Markdown。空串返回 `[]`。 |
| **run.py** | 定义 **get_body_lines()**：基础为 `list(body_lines)`；若 `phase == "streaming"` 且 `assembler._buffer` 非空则追加 `stream_preview_lines(assembler._buffer, width)`。将 **get_body_lines** 传给 `build_layout`。**\_body_line_count()** 改为基于 **get_body_lines()** 计算。定义 **on_streaming_update**（如 `lambda: app_ref[0].invalidate() if app_ref else None`）并传给 `make_handlers`。 |
| **ui/layout.py** | 参数由 `body_lines: list[str]` 改为 **get_body_lines: Callable[[], list[str]]**。Body 的 `FormattedTextControl` 使用 `text=lambda: ANSI("\n".join(get_body_lines()))`。Debug 日志中对行数的统计改为对 `get_body_lines()` 的返回值。 |
| **handle/dispatch.py** | **handle_text_delta** 增加可选参数 `on_streaming_update: Optional[Callable[[], None]] = None`；在更新 assembler 与 ui_state 之后，若提供则调用一次以触发 UI invalidate。 |
| **handle/handlers.py** | **make_handlers** 增加可选参数 `on_streaming_update: Optional[Callable[[], None]] = None`，并在构造 `on_text_delta` 的 lambda 时传给 **handle_text_delta**。 |

---

## 4. 边界与错误处理

- **空 buffer**：`stream_preview_lines("", width)` 返回 `[]`；且仅在 buffer 非空时追加预览。
- **phase 与 complete 衔接**：仅在 `phase == "streaming"` 且 buffer 非空时显示叠加层；`agent_complete` 时先清 buffer 再设 phase 为 idle，叠加层自然消失。
- **重绘触发**：handlers 与 app 在同一 asyncio 循环中运行，在 `on_text_delta` 内调用 `on_streaming_update()` 触发 invalidate 安全。
- **首帧前**：若 app 尚未创建时收到 text_delta，`on_streaming_update` 内已做 `if app_ref` 判断，避免无效调用。

---

## 5. 测试

- **stream_preview_lines**：单测——空串、单行短于/长于 width、多段（含 `\n`）、超长单词等，断言行宽与行数。
- **get_body_lines 行为**：未流式时等于 `body_lines`；流式且 buffer 非空时等于 `body_lines + stream_preview_lines(buffer, width)`。
- **集成**：模拟 WebSocket 发送若干 `text_delta` 再发送 `agent_complete`；断言流式过程中“当前正文”行数或内容随 delta 增加，complete 后叠加层消失且最终正文包含一次完整 Markdown 渲染的 assistant 块。

---

## 6. 相关文件（实现时）

- `packages/basket-tui/basket_tui/native/pipeline/render.py` — `stream_preview_lines`。
- `packages/basket-tui/basket_tui/native/run.py` — `get_body_lines`、`_body_line_count`、`on_streaming_update`、传参给 layout 与 make_handlers。
- `packages/basket-tui/basket_tui/native/ui/layout.py` — `get_body_lines` 参数与 body 控制。
- `packages/basket-tui/basket_tui/native/handle/dispatch.py` — `handle_text_delta` 增加 `on_streaming_update`。
- `packages/basket-tui/basket_tui/native/handle/handlers.py` — `make_handlers` 增加 `on_streaming_update` 并传入 dispatch。

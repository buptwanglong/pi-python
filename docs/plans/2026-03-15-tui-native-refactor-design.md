# tui-native 按层拆分重构 — 设计

**日期**: 2026-03-15  
**方案**: 方案 2 — 按层拆成多文件（dispatch、ws_loop、layout、input_handler），run.py 只做组装。

**目标**: 拆分 + 去重 + 可测；职责清晰，每文件缩短；共享状态通过引用传递，不增加状态对象层。

---

## 1. 文件与职责

| 文件 | 职责 | 主要内容 |
|------|------|----------|
| **dispatch.py** | 消息分发与输出 | `_dispatch_ws_message`、`_make_output_put`；依赖 stream、render。 |
| **ws_loop.py** | WebSocket 连接与循环 | `run_ws_loop(ws_url, width, queue_ref, loop_ref, ready_event, thread_queue, output_queue, header_state, ui_state)`：内部 assembler、last_output_count、reader 调 dispatch、consumer 处理 thread_queue。 |
| **layout.py** | 构建 UI 结构 | `build_layout(width, base_url, header_state, ui_state, body_lines, input_buffer)` 返回 `Layout`；header、footer、body、sep、input 行。 |
| **input_handler.py** | 输入与命令、picker 去重 | `handle_input(text, base_url, thread_queue, body_lines) -> "send" \| "exit" \| "handled"`；`open_picker(kind, base_url, thread_queue, body_lines)`；内部 `_run_picker(kind, ...)` 统一 session/agent/model。 |
| **run.py** | 组装与入口 | `_get_width`；创建 queue/state；起线程跑 run_ws_loop；poll、_accept_input 调 handle_input/open_picker；build_layout；KeyBindings；Application.run_async。 |

**共享状态**: header_state、ui_state、body_lines、thread_queue、output_queue 在 run.py 创建，以引用传入各层；不新增状态对象。

---

## 2. 各模块接口与依赖

**dispatch.py**
- 入参：`msg, assembler, width, output_put, last_output_count, header_state=None, ui_state=None`（与现一致）。
- 依赖：StreamAssembler、render_messages（stream、render）。
- 不依赖 prompt_toolkit、websockets。

**ws_loop.py**
- 入口：`async def run_ws_loop(ws_url, width, queue_ref, loop_ref, ready_event, thread_queue=None, output_queue=None, header_state=None, ui_state=None)`；逻辑为当前 _async_main（连接、reader、bridge、consumer、重连）。
- 内部创建 assembler、last_output_count、output_put（dispatch._make_output_put）；reader 中调用 dispatch._dispatch_ws_message。
- 依赖：dispatch、stream、websockets、asyncio。
- 不依赖 prompt_toolkit。

**layout.py**
- 入口：`def build_layout(width, base_url, header_state, ui_state, body_lines, input_buffer)`；返回 `Layout`。
- 内部：header_control、footer_control、body_control、sep、VSplit（❯ + BufferControl），HSplit 组成 Layout。
- 依赖：prompt_toolkit（Layout、HSplit、VSplit、Window、FormattedTextControl、BufferControl、ANSI）。
- 不依赖 run、ws_loop、dispatch。

**input_handler.py**
- `handle_input(text, base_url, thread_queue, body_lines) -> Literal["send", "exit", "handled"]`：空→"handled"；/session|/sessions→_run_picker("session")→"handled"；/agent|/agents→_run_picker("agent")；/model|/models→_run_picker("model")；/new→put(new_session)→"handled"；/abort→put(abort)→"handled"；/settings→body_lines 两行→"handled"；/help→body_lines.extend(HELP_LINES)→"handled"；/exit 或 handle_slash_command 返回 "exit"→"exit"；其它 /→body_lines 未知命令→"handled"；否则→"send"。
- `open_picker(kind, base_url, thread_queue, body_lines)`：调用 _run_picker(kind, ...)。
- `_run_picker(kind, base_url, thread_queue, body_lines)`：session→run_session_picker→put(("switch_session", id))；agent/model→run_agent_picker→put(("switch_agent", name))；失败 body_lines.append 错误。
- 依赖：commands（HELP_LINES、handle_slash_command）、pickers（run_session_picker、run_agent_picker）。
- 不依赖 prompt_toolkit、run、ws_loop、layout。

**run.py**
- 保留 _get_width；导入 run_ws_loop、build_layout、handle_input、open_picker。
- 创建 queue/state，起线程 asyncio.run(run_ws_loop(...))，等待 ready；body_lines、input_buffer、_poll_output、_schedule_poll；_accept_input 内调 handle_input/open_picker 并 invalidate/exit；KeyBindings（Enter、Ctrl+P/G/L、Ctrl+C/D、Esc）；build_layout；Application；run_async；finally put(None)、join。

---

## 3. 测试与兼容

- **现有测试**：test_run.py、test_run_integration.py 中凡用 _dispatch_ws_message、_make_output_put 的，改为从 `basket_tui.native.dispatch` 导入（或 run 从 dispatch 再导出、测试仍从 run 导入，在实现计划中选定）。
- **可选新增**：test_dispatch.py 存放纯 dispatch 用例；test_input_handler.py 对 handle_input/open_picker 单测（mock pickers）。
- **行为**：不改变 TUI 行为与快捷键，仅调整代码分布。

---

## 4. 实现顺序建议

1. 新增 dispatch.py，迁移 _dispatch_ws_message、_make_output_put；run.py、测试改为从 dispatch 导入。
2. 新增 ws_loop.py，迁移 _async_main 为 run_ws_loop；run.py 调用 run_ws_loop。
3. 新增 input_handler.py，实现 handle_input、open_picker、_run_picker；run.py _accept_input 与快捷键改为调用 input_handler。
4. 新增 layout.py，实现 build_layout；run.py 用 build_layout 替换内联布局构建。
5. 可选：test_dispatch.py、test_input_handler.py；整理 test_run 中 dispatch 相关用例归属。

---

**批准**: 设计已确认。实现计划见 `docs/plans/2026-03-15-tui-native-refactor-plan.md`。

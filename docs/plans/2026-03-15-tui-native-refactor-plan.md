# tui-native 按层拆分重构 — 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 run.py 按层拆成 dispatch.py、ws_loop.py、layout.py、input_handler.py，run.py 只做组装；去重 picker 逻辑；测试改为从新模块导入，行为不变。

**Architecture:** 方案 2 — 每层单文件；共享状态（header_state、ui_state、body_lines、thread_queue、output_queue）在 run.py 创建并以引用传入；不新增状态对象。

**Tech Stack:** 现有 basket_tui.native（stream、render、commands、pickers）、prompt_toolkit、websockets。

**设计依据:** `docs/plans/2026-03-15-tui-native-refactor-design.md`

---

## Task 1: 新增 dispatch.py，迁移 _dispatch_ws_message 与 _make_output_put

**Files:**
- Create: `packages/basket-tui/basket_tui/native/dispatch.py`
- Modify: `packages/basket-tui/basket_tui/native/run.py`
- Modify: `packages/basket-tui/tests/native/test_run.py`
- Modify: `packages/basket-tui/tests/native/test_run_integration.py`

**Step 1:** 创建 `dispatch.py`，从 run.py 复制 `_dispatch_ws_message`、`_make_output_put` 及其所需 import（logging、queue、threading、typing、StreamAssembler、render_messages）。保留签名与逻辑不变。

**Step 2:** 在 run.py 中删除 `_dispatch_ws_message`、`_make_output_put` 定义，增加 `from .dispatch import _dispatch_ws_message, _make_output_put`。确认 run.py 内 _async_main 仍通过该导入调用。

**Step 3:** 将 test_run.py 和 test_run_integration.py 中 `from basket_tui.native.run import _dispatch_ws_message` 改为 `from basket_tui.native.dispatch import _dispatch_ws_message`（若测试中有 _make_output_put 也改为从 dispatch 导入）。

**Step 4:** 运行 `cd packages/basket-tui && poetry run pytest tests/native/ -v`，Expected: 全部 PASS。

**Step 5:** 提交：`git add packages/basket-tui/basket_tui/native/dispatch.py packages/basket-tui/basket_tui/native/run.py packages/basket-tui/tests/native/test_run.py packages/basket-tui/tests/native/test_run_integration.py && git commit -m "refactor(basket-tui): extract dispatch layer to native/dispatch.py"`

---

## Task 2: 新增 ws_loop.py，迁移 _async_main 为 run_ws_loop

**Files:**
- Create: `packages/basket-tui/basket_tui/native/ws_loop.py`
- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1:** 创建 `ws_loop.py`，从 run.py 复制 `_async_main` 全部逻辑（含 import asyncio、json、logging、queue、threading、websockets、Union；StreamAssembler；dispatch._dispatch_ws_message、_make_output_put）。将函数名改为 `run_ws_loop`，签名与参数名与设计一致：`async def run_ws_loop(ws_url, width, queue_ref, loop_ref, ready_event, thread_queue=None, output_queue=None, header_state=None, ui_state=None)`。

**Step 2:** 在 run.py 中删除 `_async_main` 及其中用到的 _dispatch_ws_message、_make_output_put 的本地定义（已在 Task 1 改为从 dispatch 导入）。增加 `from .ws_loop import run_ws_loop`。将 `asyncio.run(_async_main(...))` 改为 `asyncio.run(run_ws_loop(...))`。

**Step 3:** 运行 `cd packages/basket-tui && poetry run pytest tests/native/ -v` 以及手动 `basket tn` 快速验证连接与发消息，Expected: 测试 PASS，TUI 正常。

**Step 4:** 提交：`git add packages/basket-tui/basket_tui/native/ws_loop.py packages/basket-tui/basket_tui/native/run.py && git commit -m "refactor(basket-tui): extract WebSocket loop to native/ws_loop.py"`

---

## Task 3: 新增 input_handler.py，实现 handle_input、open_picker、_run_picker

**Files:**
- Create: `packages/basket-tui/basket_tui/native/input_handler.py`
- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1:** 创建 `input_handler.py`。实现 `_run_picker(kind: Literal["session","agent","model"], base_url, thread_queue, body_lines)`：根据 kind 调用 run_session_picker(base_url) 或 run_agent_picker(base_url)；session 则 put(("switch_session", id))，agent/model 则 put(("switch_agent", name))；异常时 body_lines.append("[system] Failed to switch: ...")。从 pickers 导入 run_session_picker、run_agent_picker。

**Step 2:** 实现 `handle_input(text, base_url, thread_queue, body_lines) -> Literal["send", "exit", "handled"]`：text 去空后为空返回 "handled"；lower 后为 "/session" 或 "/sessions" 则 _run_picker("session", ...) 返回 "handled"；"/agent"/"/agents" → _run_picker("agent", ...)；"/model"/"/models" → _run_picker("model", ...)；"/new" → put(("new_session",))；"/abort" → put(("abort",))；"/settings" → body_lines 追加两行占位；"/help" → body_lines.extend(HELP_LINES)；然后若 handle_slash_command(text) 返回 "exit" 则返回 "exit"，返回 "handled" 则若以 "/" 开头则 body_lines.append 未知命令，返回 "handled"；否则返回 "send"。依赖 commands.HELP_LINES、handle_slash_command。

**Step 3:** 实现 `open_picker(kind, base_url, thread_queue, body_lines)`：调用 _run_picker(kind, base_url, thread_queue, body_lines)。

**Step 4:** 在 run.py 中：删除 _open_session_picker、_open_agent_picker、_open_model_picker 及 _accept_input 内与 slash/picker 相关的长分支；改为 `from .input_handler import handle_input, open_picker`。_accept_input 内：取得 text，调用 `result = handle_input(text, base_url, thread_queue, body_lines)`，若 result == "exit" 则 put(None)、get_app().exit()；若 result == "handled" 则 get_app().invalidate()；若 result == "send" 则 thread_queue.put(text)。Ctrl+P/G/L 分别调用 `open_picker("session", ...)`、`open_picker("agent", ...)`、`open_picker("model", ...)`，然后 get_app().invalidate()。base_url 使用 run.py 内已有的 _http_base_url(ws_url) 或等价变量。

**Step 5:** 运行 `cd packages/basket-tui && poetry run pytest tests/native/ -v` 与手动 `basket tn` 测试 /session、/agent、/help、发消息，Expected: PASS 且行为一致。

**Step 6:** 提交：`git add packages/basket-tui/basket_tui/native/input_handler.py packages/basket-tui/basket_tui/native/run.py && git commit -m "refactor(basket-tui): extract input handling to native/input_handler.py, dedupe pickers"`

---

## Task 4: 新增 layout.py，实现 build_layout

**Files:**
- Create: `packages/basket-tui/basket_tui/native/layout.py`
- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1:** 创建 `layout.py`，导入 prompt_toolkit 的 Layout、HSplit、VSplit、Window、FormattedTextControl、BufferControl、ANSI。实现 `def build_layout(width, base_url, header_state, ui_state, body_lines, input_buffer)`：构建 header_control（FormattedTextControl 显示 URL、agent、session）、footer_control（connection | phase）、body_control（ANSI("\n".join(body_lines))）、sep_control（分隔线）、input 行（VSplit 含 ❯ 与 BufferControl(buffer=input_buffer)）；返回 `Layout(HSplit([Window(header), Window(body), Window(footer), Window(sep), VSplit([prompt, Window(input_control)])]))`。类型与 run.py 当前一致（lambda 读 header_state、ui_state、body_lines）。

**Step 2:** 在 run.py 中删除内联的 sep_control、header_control、footer_control、body_control、input_control 及 Layout(HSplit([...])) 的构建；改为 `from .layout import build_layout`，调用 `layout = build_layout(width, base_url, header_state, ui_state, body_lines, input_buffer)`，Application 使用该 layout。

**Step 3:** 运行 `cd packages/basket-tui && poetry run pytest tests/native/ -v` 与手动 `basket tn` 检查界面布局，Expected: PASS 且界面一致。

**Step 4:** 提交：`git add packages/basket-tui/basket_tui/native/layout.py packages/basket-tui/basket_tui/native/run.py && git commit -m "refactor(basket-tui): extract layout to native/layout.py"`

---

## Task 5: 可选 — test_dispatch.py、test_input_handler.py

**Files:**
- Create: `packages/basket-tui/tests/native/test_dispatch.py`（可选：将 test_run 中仅测 _dispatch_ws_message 的用例迁入或保留在 test_run 仅改 import，不重复）
- Create: `packages/basket-tui/tests/native/test_input_handler.py`

**Step 1:** 若需 test_dispatch.py：从 test_run.py 复制所有 _dispatch_ws_message 相关用例到 test_dispatch.py，导入改为 `from basket_tui.native.dispatch import _dispatch_ws_message`；再从 test_run.py 删除这些用例（避免重复）。或保持现状（test_run 已从 dispatch 导入），不新建 test_dispatch.py。

**Step 2:** 新建 test_input_handler.py。对 handle_input：mock thread_queue、body_lines；断言 handle_input("", base_url, q, lines) 返回 "handled"；handle_input("/exit", ...) 返回 "exit"；handle_input("hello", ...) 返回 "send"；handle_input("/help", ...) 返回 "handled" 且 body_lines 含 HELP_LINES 内容。对 open_picker：mock run_session_picker 返回 "sid1"，断言 thread_queue 收到 ("switch_session", "sid1")。运行 pytest tests/native/test_input_handler.py -v，Expected: PASS。

**Step 3:** 提交：`git add packages/basket-tui/tests/native/test_input_handler.py && git commit -m "test(basket-tui): add tests for input_handler"`

---

## 完成验收

- `cd packages/basket-tui && poetry run pytest tests/native/ -v` 全部通过。
- 手动：`basket tn` 下验证连接、发消息、/session、/agent、/help、Ctrl+P/G/L、Esc、/exit，行为与重构前一致。
- run.py 行数明显减少；dispatch、ws_loop、layout、input_handler 各文件职责单一。

---

**执行选项:** 可按任务顺序在本会话中逐项执行，或新会话使用 executing-plans 执行。

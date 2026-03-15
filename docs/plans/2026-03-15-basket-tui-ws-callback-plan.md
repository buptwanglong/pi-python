# basket-tui WebSocket 回调抽象 — 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用 WebSocket 连接抽象（send_* + 多 hook 入站）替代 asyncio.Queue，并统一定义 WebSocket 与 TUI 之间的类型（GatewayHandlers、GatewayConnectionProtocol）。

**Architecture:** 新增 `GatewayConnection` 协议与 `GatewayWsConnection` 实现；connection 持有 `GatewayHandlers`，reader 按消息 type 调用对应 on_*；TUI 通过 `make_handlers(...)` 提供实现（内部复用按类型拆分的 dispatch 逻辑）；run.py 不再创建 input_queue，改为持有 connection 并调用 send_*。

**Tech Stack:** Python 3.12+, asyncio, websockets, prompt_toolkit, TypedDict/Protocol。

**设计文档:** `docs/plans/2026-03-15-basket-tui-ws-callback-design.md`

---

## Task 1: 定义类型（GatewayHandlers + Protocol）

**Files:**
- Create: `packages/basket-tui/basket_tui/native/types.py`
- Modify: `packages/basket-tui/basket_tui/native/__init__.py`（导出新类型，可选）

**Step 1: 写类型定义与 Protocol 的失败测试**

在 `packages/basket-tui/tests/native/test_types.py` 中写测试：从 `basket_tui.native.types` 导入 `GatewayHandlers`、`GatewayConnectionProtocol`；构造满足 Protocol 的 mock（含 send_message、send_abort 等），断言类型可被 isinstance 或类型检查接受（或仅做导入与调用签名测试）。

```python
# test_types.py
import pytest
from basket_tui.native.types import GatewayHandlers, GatewayConnectionProtocol

def test_gateway_handlers_optional_keys():
    h: GatewayHandlers = {}
    assert h == {}

def test_protocol_has_send_methods():
    """Protocol 用于类型标注；仅验证导入与存在性。"""
    assert GatewayConnectionProtocol is not None
```

**Step 2: 运行测试确认失败**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_types.py -v`  
Expected: FAIL (ModuleNotFoundError or import error)

**Step 3: 实现 types.py**

Create `packages/basket-tui/basket_tui/native/types.py`:

```python
from typing import Any, Callable, Protocol, TypedDict

class GatewayHandlers(TypedDict, total=False):
    on_text_delta: Callable[[str], None]
    on_thinking_delta: Callable[[str], None]
    on_tool_call_start: Callable[[str, dict[str, Any] | None], None]
    on_tool_call_end: Callable[[str, str | None, str | None], None]
    on_agent_complete: Callable[[], None]
    on_agent_error: Callable[[str], None]
    on_session_switched: Callable[[str], None]
    on_agent_switched: Callable[[str], None]
    on_agent_aborted: Callable[[], None]
    on_system: Callable[[str, dict[str, Any]], None]

class GatewayConnectionProtocol(Protocol):
    async def send_message(self, text: str) -> None: ...
    async def send_abort(self) -> None: ...
    async def send_new_session(self) -> None: ...
    async def send_switch_session(self, session_id: str) -> None: ...
    async def send_switch_agent(self, agent_name: str) -> None: ...
    async def close(self) -> None: ...
```

**Step 4: 运行测试确认通过**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_types.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/types.py packages/basket-tui/tests/native/test_types.py
git commit -m "feat(basket-tui): add GatewayHandlers and GatewayConnectionProtocol types"
```

---

## Task 2: 从 dispatch 拆出按类型的小函数

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/dispatch.py`
- Test: `packages/basket-tui/tests/native/test_run.py`（现有 _dispatch_ws_message 测试应仍通过）

**Step 1: 写测试**

在 `packages/basket-tui/tests/native/test_dispatch.py`（新建）中：对每个新导出的 per-type 函数（如 `handle_text_delta`、`handle_agent_complete`）写单测，行为与当前 `_dispatch_ws_message` 对该 type 的行为一致（例如 handle_text_delta(assembler, "hi") 后 assembler._buffer == "hi"）。

**Step 2: 运行测试确认失败**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_dispatch.py -v`  
Expected: FAIL（函数尚未存在）

**Step 3: 在 dispatch.py 中拆出 per-type 函数**

- 从 `_dispatch_ws_message` 中按 `typ` 分支拆成：`handle_text_delta(assembler, delta)`、`handle_thinking_delta(assembler, delta)`、`handle_tool_call_start(...)`、`handle_tool_call_end(...)`、`handle_agent_complete(assembler, width, output_put, last_output_count)`、`handle_agent_error(output_put, error)`、`handle_session_switched(header_state, output_put, session_id)`、`handle_agent_switched(...)`、`handle_agent_aborted(assembler, output_put)`、`handle_system(event, payload)`（或对 ready/error 等做小封装）。
- `_dispatch_ws_message` 改为根据 `msg.get("type")` 调用上述函数，保持原有签名与行为不变。

**Step 4: 运行所有 dispatch 相关测试**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_run.py tests/native/test_dispatch.py tests/native/test_run_integration.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/dispatch.py packages/basket-tui/tests/native/test_dispatch.py
git commit -m "refactor(basket-tui): extract per-type handlers from _dispatch_ws_message"
```

---

## Task 3: 实现 make_handlers（返回 GatewayHandlers）

**Files:**
- Create or Modify: `packages/basket-tui/basket_tui/native/handlers.py`（新建，或放在 dispatch.py 内）
- Test: `packages/basket-tui/tests/native/test_handlers.py`

**Step 1: 写测试**

`make_handlers(assembler, width, output_put, last_output_count, header_state, ui_state)` 返回的 GatewayHandlers 中，调用 `on_text_delta("x")` 后 assembler._buffer 含 "x"；调用 `on_agent_complete()` 后 last_output_count 与 output_put 被正确调用（用 list 收集 output_put 的 line）。

**Step 2: 运行测试确认失败**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_handlers.py -v`  
Expected: FAIL

**Step 3: 实现 make_handlers**

在 `handlers.py` 中实现 `make_handlers(...)`，返回的 GatewayHandlers 各字段委托给 Task 2 的 handle_* 函数（传入 assembler、width、output_put 等闭包）。

**Step 4: 运行测试确认通过**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_handlers.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/handlers.py packages/basket-tui/tests/native/test_handlers.py
git commit -m "feat(basket-tui): add make_handlers for GatewayHandlers from dispatch state"
```

---

## Task 4: 实现 GatewayWsConnection（reader + send_*，无 queue）

**Files:**
- Create: `packages/basket-tui/basket_tui/native/connection.py`
- Test: `packages/basket-tui/tests/native/test_connection.py`

**Step 1: 写测试**

- Mock `websockets.connect`；构造 `GatewayHandlers`（on_text_delta=append to list）；用 connection 跑 reader 直到收到两条 text_delta 的 JSON；断言 list 收到对应 delta。
- 断言 `await conn.send_message("hi")` 导致 mock ws.send 被调用且 JSON 为 `{"type":"message","content":"hi"}`；同理 send_abort、send_new_session、send_switch_session、send_switch_agent。

**Step 2: 运行测试确认失败**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_connection.py -v`  
Expected: FAIL

**Step 3: 实现 GatewayWsConnection**

- 构造函数：`__init__(self, ws_url: str, handlers: GatewayHandlers, ready_event: asyncio.Event, *, header_state=None, ui_state=None)`。
- 内部 `_run()`：`async with websockets.connect(ws_url) as ws`，保存 `self._ws`，set ready_event，启动 `reader_task`（async for raw in ws → json.loads → 按 type 调 handlers 中对应 on_*），然后 `await self._closed.wait()` 或类似（无 consumer 循环）。
- 提供 `async def send_message(self, text: str) -> None` 等，内部 `await self._ws.send(json.dumps({...}))`；若已断开则 raise 或 no-op。
- `async def close(self) -> None`：设关闭标志，关闭 ws，结束 reader。
- 断线重连：可在 _run 的 while True 里 try/except，重连后再次 set ready_event 并调 `on_system("reconnected", {})`（与现有 ws_loop 行为对齐）。

**Step 4: 运行测试确认通过**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_connection.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/connection.py packages/basket-tui/tests/native/test_connection.py
git commit -m "feat(basket-tui): add GatewayWsConnection with send_* and handler callbacks"
```

---

## Task 5: input_handler 改为使用 GatewayConnection

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/input_handler.py`
- Modify: `packages/basket-tui/tests/native/test_input_handler.py`

**Step 1: 写/改测试**

将 test_input_handler 中所有 `input_queue.put_nowait(...)` 的预期改为：传入 mock GatewayConnectionProtocol（记录 send_message/send_abort/send_switch_session 等调用），断言在 handle_input 或 open_picker 后 mock 收到对应调用；发送消息时需在 TUI 侧用 `asyncio.create_task(conn.send_message(text))`，测试里可 run_until_complete 或 mock create_task。

**Step 2: 运行测试确认失败**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_input_handler.py -v`  
Expected: FAIL（input_handler 仍用 queue）

**Step 3: 改 input_handler 签名与实现**

- `handle_input(text, base_url, connection: GatewayConnectionProtocol, body_lines)`；`open_picker(kind, base_url, connection, body_lines)`。
- 所有原 `input_queue.put_nowait(text)` 改为 `asyncio.get_event_loop().create_task(connection.send_message(text))`（或 run.py 传入 loop）；原 `put_nowait(("abort",))` 改为 `create_task(connection.send_abort())`；`put_nowait(("new_session",))` → `create_task(connection.send_new_session())`；`put_nowait(("switch_session", id))` → `create_task(connection.send_switch_session(id))`；`put_nowait(("switch_agent", name))` → `create_task(connection.send_switch_agent(name))`。
- 返回值 "exit" 时 run.py 侧调用 `connection.close()`，不再 put_nowait(None)。

**Step 4: 运行测试确认通过**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_input_handler.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/input_handler.py packages/basket-tui/tests/native/test_input_handler.py
git commit -m "refactor(basket-tui): input_handler uses GatewayConnection instead of queue"
```

---

## Task 6: run.py 使用 connection + handlers，移除 queue

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/run.py`
- Test: `packages/basket-tui/tests/native/test_run.py`（若有 run 层测试则调整）

**Step 1: 写/调整测试**

若有测试依赖 run_tui_native_attach 的 queue 行为，改为传入 mock connection 与 mock handlers；或只测「连接超时」等分支（mock GatewayWsConnection 不 set ready_event）。

**Step 2: 修改 run.py**

- 删除 `input_queue = asyncio.Queue()`。
- 创建 `StreamAssembler`、`last_output_count`、`body_lines`、`output_put` 与 `app_ref` 不变；用 `make_handlers(assembler, width, output_put, last_output_count, header_state, ui_state)` 得到 `handlers`。
- 创建 `GatewayWsConnection(ws_url, handlers, ready_event, header_state=..., ui_state=...)`，`conn = ...`；用 `asyncio.create_task(conn.run())` 或 `conn.run()` 在后台跑（需在 connection 实现里提供 `async def run(self)` 作为入口，内部做 connect + reader + 重连）。
- `handle_input(..., connection=conn, body_lines=body_lines)`；`open_picker(..., connection=conn, body_lines=body_lines)`。
- 退出时：`create_task(conn.close())` 或 `await conn.close()`，然后 cancel connection task 并 await。
- Esc/abort：`create_task(conn.send_abort())`。

**Step 3: 运行所有 native 测试**

Run: `cd packages/basket-tui && poetry run pytest tests/native/ -v`  
Expected: PASS

**Step 4: Commit**

```bash
git add packages/basket-tui/basket_tui/native/run.py
git commit -m "refactor(basket-tui): run.py uses GatewayConnection and handlers, no input queue"
```

---

## Task 7: 移除 ws_loop 的 queue 与 consumer，或弃用

**Files:**
- Modify or Remove: `packages/basket-tui/basket_tui/native/ws_loop.py`
- Modify: `packages/basket-tui/basket_tui/native/run.py`（确保不再 import run_ws_loop）

**Step 1: 确认 run.py 已完全使用 connection**

run.py 应只 import 并启动 GatewayWsConnection，不再调用 run_ws_loop。

**Step 2: 删除或精简 ws_loop.py**

若 GatewayWsConnection 已包含重连与 reader 逻辑，可删除 `run_ws_loop`；若有其他调用方（如非 TUI 的 attach 模式），保留 `run_ws_loop` 并标注 deprecated，或改为委托给 GatewayWsConnection。搜索仓库中 `run_ws_loop` 的引用并一并改为 connection。

**Step 3: 运行全量测试**

Run: `cd packages/basket-tui && poetry run pytest -v`  
Expected: PASS

**Step 4: Commit**

```bash
git add packages/basket-tui/basket_tui/native/ws_loop.py packages/basket-tui/basket_tui/native/run.py
git commit -m "chore(basket-tui): remove or deprecate run_ws_loop in favor of GatewayWsConnection"
```

---

## Task 8: 文档与导出

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/__init__.py`
- Modify: `packages/basket-tui/README.md`（若需说明新 API）

**Step 1: 导出类型与 connection**

在 `__init__.py` 中导出 `GatewayHandlers`、`GatewayConnectionProtocol`、`GatewayWsConnection`（及 `make_handlers` 若在独立模块），便于上层或测试使用。

**Step 2: 运行测试**

Run: `cd packages/basket-tui && poetry run pytest -v`  
Expected: PASS

**Step 3: Commit**

```bash
git add packages/basket-tui/basket_tui/native/__init__.py
git commit -m "docs(basket-tui): export GatewayHandlers, GatewayConnectionProtocol, GatewayWsConnection"
```

---

## 执行方式

计划已保存至 `docs/plans/2026-03-15-basket-tui-ws-callback-plan.md`。

**两种执行方式：**

1. **Subagent-Driven（本会话）** — 按任务派发子 agent，每步完成后你做 review，迭代快。  
2. **Parallel Session（新会话）** — 在新会话中用 executing-plans，在独立 worktree 里按检查点批量执行。

你更倾向哪种？若选 1，我会用 subagent-driven-development 在本会话按任务推进；若选 2，我会说明如何在新会话中打开 worktree 并用 executing-plans 执行。

# basket-tui 单 asyncio 循环重构 — 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 basket-tui native 从「双线程 + queue.Queue + 轮询」改为单 asyncio 循环，保留 prompt_toolkit，消除 threading 与跨线程队列。

**Architecture:** 调用方已在 asyncio 中；run_tui_native_attach 创建 asyncio.Queue 与 asyncio.Event，用 asyncio.create_task 启动 run_ws_loop；WS consumer 从 asyncio.Queue await get()；输出通过 run 层传入的 output_put 回调（body_lines.append + app.invalidate()）写 UI；输入/命令经同一 asyncio.Queue 从 UI 传到 WS。

**Tech Stack:** asyncio, prompt_toolkit, websockets。设计见 `docs/plans/2026-03-15-basket-tui-single-loop-design.md`。

---

## Task 1: ws_loop 改为接收 asyncio.Queue 与 output_put 回调

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/ws_loop.py`

**Step 1: 为 run_ws_loop 新签名写占位与测试**

- 在 `ws_loop.py` 中把 `run_ws_loop` 的签名改为接收 `input_queue: asyncio.Queue`（类型 `Union[str, None, tuple, ...]`）和 `output_put: Callable[[str], None]`，以及 `ready_event: asyncio.Event`；移除 `queue_ref`, `loop_ref`, `thread_queue`, `output_queue`。
- 在 `tests/native/test_run.py` 或新建 `tests/native/test_ws_loop.py` 中增加：用 mock websockets、asyncio.Queue 的异步测试，consumer 从 input_queue.get() 取到 str 时发送 message 类型（或仅测 consumer 逻辑可被触发）。若现有测试依赖旧签名，先改为 skip 或标记 xfail，避免阻塞。

**Step 2: 运行测试确认失败或跳过**

Run: `cd packages/basket-tui && poetry run pytest tests/native/ -v -k ws_loop 2>/dev/null || poetry run pytest tests/native/test_run.py -v`
Expected: 需能跑通（若尚无 ws_loop 单测则先通过 run 相关测试）。

**Step 3: 实现 ws_loop 新逻辑**

- 删除 `bridge()` 协程及对 `thread_queue`、`run_in_executor` 的使用。
- 删除 `queue_ref`、`loop_ref` 的 append/clear；内部不再使用 asyncio_queue，consumer 直接 `item = await input_queue.get()`。
- 首次 `async with websockets.connect(...)` 成功后调用 `ready_event.set()`（若传入的是 asyncio.Event）。
- `output_put` 由调用方传入（run 层闭包），直接调用，不再通过 queue。
- 保持 reader + consumer 结构；consumer 退出（收到 None）后正常关闭 ws 并 return。

**Step 4: 运行测试**

Run: `cd packages/basket-tui && poetry run pytest tests/native/ -v`
Expected: 与 WS/run 相关的测试需更新后通过（见后续 Task）。

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/ws_loop.py packages/basket-tui/tests/
git commit -m "refactor(tui): ws_loop accept asyncio.Queue and output_put callback"
```

---

## Task 2: dispatch 的 output_put 由 run 层注入，支持回调形式

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/dispatch.py`（若需）
- Modify: `packages/basket-tui/basket_tui/native/ws_loop.py`（在调用 _make_output_put 或传入 output_put 处）

**Step 1: 确认 dispatch 接口**

- `_dispatch_ws_message` 已接受 `output_put: Callable[[str], None]`，无需改。
- `_make_output_put` 当前接受 `output_queue: Optional[queue.Queue]` 和 `print_lock`；run 层将改为传入「写 body_lines + invalidate」的闭包，因此 run_ws_loop 不再调用 _make_output_put，而是直接接收 run 层传进来的 `output_put`。若 ws_loop 内部仍有 _make_output_put 的调用（例如无 output_put 时 fallback 到 print），保留 fallback 逻辑但默认路径为传入的 output_put。
- 无需改 dispatch 的 _dispatch_ws_message 签名。

**Step 2: 在 ws_loop 中仅使用传入的 output_put**

- 确保 run_ws_loop 的 `output_put` 参数必传（或内部无 output_put 时用 print+lock 的 fallback）。去掉对 output_queue、print_lock 的依赖；所有 output 都走 output_put。

**Step 3: 运行测试**

Run: `cd packages/basket-tui && poetry run pytest tests/native/ -v`
Expected: PASS（dispatch 单测仍用 out.append 作为 output_put）。

**Step 4: Commit**

```bash
git add packages/basket-tui/basket_tui/native/ws_loop.py packages/basket-tui/basket_tui/native/dispatch.py
git commit -m "refactor(tui): ws_loop use only injected output_put, no queue/lock"
```

---

## Task 3: input_handler 改为使用 asyncio.Queue

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/input_handler.py`
- Test: `packages/basket-tui/tests/native/test_input_handler.py`

**Step 1: 写/更新测试：handle_input 与 open_picker 使用 asyncio.Queue**

- 在测试里创建 `q = asyncio.Queue()`，调用 `handle_input(..., q, body_lines)`；对需发送的命令执行 `handle_input` 后断言 `q.get_nowait()` 或异步 `q.get()` 得到预期项（如 `("abort",)`、`("new_session",)`、或普通 str）。若有 `test_input_handler.py`，改为使用 asyncio.Queue；若无则 in test_run.py 或 test_input_handler 中增加用例。
- open_picker 会 put 到 queue，测试可 mock picker 返回值后断言 queue 内容。

**Step 2: 运行测试确认失败**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_input_handler.py -v`（或对应测试路径）
Expected: 因 input_handler 仍接受 thread_queue 而失败或需改断言。

**Step 3: 修改 input_handler 签名与实现**

- `handle_input(text, base_url, input_queue, body_lines)`：将 `thread_queue` 改为 `input_queue: asyncio.Queue`；所有 `thread_queue.put(x)` 改为 `input_queue.put_nowait(x)`。
- `open_picker(kind, base_url, input_queue, body_lines)` 与 `_run_picker(..., input_queue, ...)` 同样改为 put_nowait。
- 类型注解：`from typing import Union` 等，queue 项类型可与 ws_loop 约定一致（str | None | tuple）。

**Step 4: 运行测试**

Run: `cd packages/basket-tui && poetry run pytest tests/native/ -v`
Expected: PASS。

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/input_handler.py packages/basket-tui/tests/
git commit -m "refactor(tui): input_handler use asyncio.Queue instead of queue.Queue"
```

---

## Task 4: run.py 单循环：asyncio.Queue、Event、create_task、去掉线程与轮询

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1: 写/更新 run 相关测试（连接超时、退出）**

- 若有 test_run 里依赖 `threading.Thread`、`queue.Queue`、`ready_event.wait(timeout=15)` 的测试，改为 asyncio：例如 `async def test_connection_timeout():` 中 patch run_ws_loop 使其永不 set ready_event，然后 `await run_tui_native_attach(...)` 并断言在约 15 秒内 return 且打印超时信息（或 mock 时间避免真等 15 秒）。或先简化：只保证 `run_tui_native_attach` 可被 await 且不抛，不启动真实 app（通过 mock prompt_toolkit.Application.run_async 立即 return）。
- 运行测试确认当前状态（可能部分失败）。

**Step 2: 实现 run.py 单循环**

- 删除 `import queue`, `import threading`；保留 `import asyncio`。
- 创建 `input_queue: asyncio.Queue = asyncio.Queue()`，类型与 ws_loop 约定一致。
- 创建 `ready_event = asyncio.Event()`。
- 定义 `output_put` 闭包：需能访问 `body_lines` 和 `app_ref`（或 app）；在闭包内 `body_lines.append(line)`，若 `app_ref` 非空则取 app 并 `app.invalidate()`。注意：app 在 build_layout 之后才创建，因此 output_put 可在创建 app 后通过「闭包捕获 app_ref」实现，或先传 body_lines，在 after_render 或第一次渲染前把 app 填入 app_ref。
- 启动 WS 任务：`ws_task = asyncio.create_task(run_ws_loop(ws_url, width, input_queue, output_put, ready_event, header_state=..., ui_state=...))`。run_ws_loop 签名需与 Task 1/2 一致（无 queue_ref/loop_ref/thread_queue/output_queue）。
- 等待就绪：`await asyncio.wait_for(ready_event.wait(), timeout=15.0)`；若超时则 `print("[system] Connection timed out.", flush=True)`，`ws_task.cancel()`，`await ws_task`（捕获 CancelledError），return。
- 构建 layout、Application 时传入 `body_lines`、`header_state`、`ui_state`；在创建 app 后把 app 放入 `app_ref`，以便 output_put 可 invalidate。
- 删除 `_schedule_poll` 和 `after_render=lambda _: _schedule_poll()`；不再轮询 output_queue。
- `_accept_input` 中：`handle_input(..., input_queue, body_lines)`；若 "send" 则 `input_queue.put_nowait(text)`；若 "exit" 则 `input_queue.put_nowait(None)` 然后 `get_app().exit()`。
- Ctrl+P / Ctrl+G / Ctrl+L 的 open_picker 传入 `input_queue`。
- 退出键：先 `input_queue.put_nowait(None)` 再 `get_app().exit()`。
- 在 `try: await app.run_async(); finally:` 中 `app_ref.clear()`；`input_queue.put_nowait(None)`；`ws_task.cancel()`；`await ws_task`（捕获 CancelledError）。
- 删除 ws_thread、thread_queue、output_queue、queue_ref、loop_ref、ready_event.wait(timeout=15) 的线程版。

**Step 3: 运行测试**

Run: `cd packages/basket-tui && poetry run pytest tests/native/ -v`
Expected: 所有 native 测试通过。

**Step 4: 手动冒烟**

Run: `cd packages/basket-assistant && poetry run basket tui-native`（需先 `basket gateway start`），输入一条消息确认能收发并显示后退出。
Expected: 无报错，输出正常。

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/run.py packages/basket-tui/tests/
git commit -m "refactor(tui): single asyncio loop, remove thread and queue.Queue"
```

---

## Task 5: 清理与类型检查

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/run.py`, `ws_loop.py`, `input_handler.py`
- Modify: `packages/basket-tui/basket_tui/native/dispatch.py`（若仍导出 _make_output_put 且被其他地方使用）

**Step 1: 移除未使用的导入与变量**

- run.py：确认无 `queue`、`threading`、`queue_ref`、`loop_ref`。
- ws_loop.py：确认无 `queue`、`threading`、`run_in_executor`、bridge、asyncio_queue（若仅 consumer 用 input_queue 则无 asyncio_queue）。

**Step 2: 统一类型注解**

- input_queue 项类型：在 ws_loop 与 input_handler 中一致使用 `Union[str, None, Tuple[str, ...]]` 或 Literal/Union 的 tuple 形式，便于 mypy。

**Step 3: mypy 与 ruff**

Run: `cd packages/basket-tui && poetry run mypy basket_tui/native/ && poetry run ruff check basket_tui/native/`
Expected: 无错误。

**Step 4: Commit**

```bash
git add packages/basket-tui/basket_tui/native/
git commit -m "chore(tui): remove unused imports, align types for single-loop"
```

---

## Task 6: 文档与 README

**Files:**
- Modify: `packages/basket-tui/README.md`（若需说明架构变更）

**Step 1: 更新 README（可选）**

- 在 Development 或架构说明中简短注明：TUI 运行在单 asyncio 循环内，与 gateway 通过 WebSocket 通信，无多线程。无需大改。

**Step 2: Commit**

```bash
git add packages/basket-tui/README.md
git commit -m "docs(tui): note single-loop architecture in README"
```

---

## Execution Handoff

计划已保存到 `docs/plans/2026-03-15-basket-tui-single-loop-plan.md`。

**两种执行方式：**

1. **本会话子 agent 驱动** — 按任务逐个派发子 agent，每步后你做 review，迭代快。
2. **并行会话** — 在新会话中用 executing-plans，在独立 worktree 里按检查点批量执行。

选哪种？

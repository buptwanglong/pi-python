# basket-tui 单 asyncio 循环架构 — 设计

**日期**: 2026-03-15  
**方案**: 方案一 — 单 asyncio 循环 + 保留 prompt_toolkit，去掉线程与 queue.Queue。

**目标**: 单线程、单事件循环；无 `threading`、无 `queue.Queue`、无轮询；共享状态仅在同一线程读写，消除数据竞争。

---

## 1. 架构与职责划分

- **调用方**: `basket-assistant` 在已有 asyncio loop 里 `await run_tui_native_attach(ws_url, ...)`。
- **run_tui_native_attach** 在同一 loop 上：
  1. 创建 **asyncio.Queue**（用户输入/命令：`str | None | tuple`）。
  2. 启动 **WebSocket 协程**（`run_ws_loop` 异步版）：连接 gateway、reader、consumer 为同一 loop 上的 asyncio 任务；consumer 从 asyncio.Queue `await get()` 取用户消息或命令并发送到 gateway。
  3. 构建并 **run prompt_toolkit Application**（`await app.run_async()`）；输入提交时在回调里向 asyncio.Queue `put`，不再使用 thread_queue。
  4. **输出**: WS 侧在收到 gateway 消息、组装完行后，直接更新 `body_lines` 并调用 `app.invalidate()`（同线程）；不再使用 output_queue 和定时轮询。

| 模块 | 职责 | 变更要点 |
|------|------|----------|
| run.py | 创建 asyncio.Queue、启动 WS 任务、构建并运行 app、把 queue 传给 input 与 WS | 去掉 ws_thread、thread_queue、output_queue、ready_event、_schedule_poll；WS 用 asyncio.create_task |
| ws_loop.py | 纯 asyncio：connect、reader、consumer；consumer 从 asyncio.Queue get | 去掉 thread_queue 与 run_in_executor(bridge)；入参改为 asyncio.Queue；output 改为「写 body_lines + invalidate」的回调 |
| input_handler.py | 处理输入与命令，需发到 WS 时对 asyncio.Queue put | 入参从 thread_queue 改为 asyncio.Queue |
| dispatch.py / render.py / stream.py | 保持「消息→组装→渲染→输出」 | 输出从 output_put(queue.put) 改为 output_put(callback)，callback 内写 body_lines + app.invalidate() |
| layout.py | 只读 state 渲染 | 可不变 |

---

## 2. 数据流与生命周期

**用户输入 → Gateway**

1. 用户回车 → `_accept_input` → `handle_input(...)`；若 `"send"` 则 `input_queue.put_nowait(text)`。
2. WS consumer `item = await input_queue.get()`；`str` 则发 message；`None` 退出；tuple 发对应 type。
3. 命令（/new、/abort、picker 结果）经同一 asyncio.Queue 由 consumer 处理。

**Gateway → UI**

1. reader → `_dispatch_ws_message` → 在 agent_complete 等时机调用 `output_put(line)`。
2. `output_put` 新实现：闭包内 `body_lines.append(line)` + `app.invalidate()`；同线程，无需 call_soon_thread_safe。
3. 无 output_queue、无轮询、无跨线程写 body_lines。

**连接就绪**

- 先 `asyncio.create_task(run_ws_loop(...))`；run_ws_loop 内首次连接成功后 set(ready_event)；主流程 `await asyncio.wait_for(ready_event.wait(), timeout=15)` 后再构建 layout 和 Application。可用 asyncio.Event。

**退出与清理**

1. 用户 Ctrl+C / Ctrl+D 或 /exit：对 asyncio.Queue `put(None)`，再 `app.exit()`。
2. consumer 收到 None 后退出；run_ws_loop 结束；主流程在 app.run_async() 返回后 cancel WS task 并 await。
3. 无 ws_thread.join()。

---

## 3. 错误处理与边界情况

- **WebSocket 断线重连**: 与现一致，run_ws_loop 内 while True + backoff；output_put 写 body_lines + invalidate。
- **连接超时**: `await asyncio.wait_for(ready_event.wait(), timeout=15)` 超时则打印并 return，cancel WS task 并 await。
- **output_put 时 app 已销毁**: 回调内若 app_ref 非空且 app 仍 running 才 invalidate，或 try/except 忽略。
- **Picker 阻塞**: 可保持同步；后续可改为 async（非本次必须）。
- **退出顺序**: 先 put(None) 再 app.exit()；app 返回后 cancel 并 await WS task。

---

## 4. 测试策略

- **dispatch / render / stream**: 现有单测沿用 `output_put = out.append`，不改。
- **commands / input_handler**: 入参改为 asyncio.Queue 后，测试里用 asyncio.Queue() 并 put/get 验证。
- **run.py**: 去掉对 threading/queue 的 patch；可测连接超时分支（mock run_ws_loop 不 set ready，断言超时后 return）。
- **ws_loop**: 可单测 consumer 从 asyncio.Queue 取 str/None/tuple 时发送对应 WS 或退出（mock websockets.connect）。
- 集成：若有「起 gateway + tui」测试，改为 await run_tui_native_attach + 超时或触发 exit；无则非必须。

---

## 5. 不做的

- 不引入新 UI 库、不增加新线程、不保留任何 queue.Queue 或基于时间的轮询。

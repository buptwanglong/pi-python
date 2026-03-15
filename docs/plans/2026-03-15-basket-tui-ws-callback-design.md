# basket-tui WebSocket 回调抽象设计

**日期**: 2026-03-15  
**目标**: 用「WebSocket 连接抽象 + 回调」替代 asyncio.Queue；出站为 send_* 方法，入站为按类型拆分的多个 hook，并统一定义 WebSocket 与 TUI 之间的类型。

---

## 1. 架构与角色

- **抽象**: `GatewayConnection` — 表示连上 gateway 的一条 WebSocket。
- **职责**:
  - **出站**: 提供 `send_message(text)`、`send_abort()` 等 async 方法；TUI 在回车/快捷键回调里调用（同 asyncio loop，可用 `asyncio.create_task(conn.send_message(text))`）。
  - **入站**: 内部运行 reader 协程，收到 gateway 消息后按 `type` 解析并调用对应的 **on_*** hook；无队列，直接回调。
- **TUI**:
  - 连接建立后持有 `GatewayConnection` 实例。
  - 通过 **handlers 对象** 注册一组合适的 on_* hook；在 hook 内更新 `body_lines`、`header_state`、`ui_state` 并 `app.invalidate()`。
  - 用户输入/命令时调用 `conn.send_message(...)` / `conn.send_abort()` 等，不再向 asyncio.Queue put。

**结论**: 无队列；WebSocket 连接即抽象；触发输入 = 调用 send_*，收到输入 = 多个 on_* hook，类型见下。

---

## 2. 出站（触发输入）— 类型与方法

采用 **方式甲**：每个动作为一个 async 方法，方法签名即出站参数类型。

| 方法 | 含义 |
|------|------|
| `async def send_message(text: str) -> None` | 发送用户消息 |
| `async def send_abort() -> None` | 中止当前轮次 |
| `async def send_new_session() -> None` | 创建新会话 |
| `async def send_switch_session(session_id: str) -> None` | 切换会话 |
| `async def send_switch_agent(agent_name: str) -> None` | 切换 agent |
| `async def close() -> None` | 主动关闭连接（TUI 退出时调用） |

协议层可定义 `Protocol`（例如 `GatewayConnectionProtocol`）包含上述方法，便于测试与多实现。

---

## 3. 入站（收到输入）— 多 hook 与参数类型

入站按 gateway 消息类型拆成多个 hook，每个 hook 参数类型固定。TUI 通过 **handlers 对象** 提供实现（方式 B）。

**Handlers 类型定义**（可选字段，TUI 只实现需要的 hook）:

```python
from typing import Any, Callable, TypedDict

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
    on_system: Callable[[str, dict[str, Any]], None]  # ready, agent_disconnected, error 等
```

**gateway type → hook 映射**:

| gateway `type` | hook | 参数 |
|----------------|------|------|
| `text_delta` | `on_text_delta` | `delta: str` |
| `thinking_delta` | `on_thinking_delta` | `delta: str` |
| `tool_call_start` | `on_tool_call_start` | `tool_name: str`, `arguments: dict \| None` |
| `tool_call_end` | `on_tool_call_end` | `tool_name: str`, `result: str \| None`, `error: str \| None` |
| `agent_complete` | `on_agent_complete` | 无 |
| `agent_error` | `on_agent_error` | `error: str` |
| `session_switched` | `on_session_switched` | `session_id: str` |
| `agent_switched` | `on_agent_switched` | `agent_name: str` |
| `agent_aborted` | `on_agent_aborted` | 无 |
| `ready`, `agent_disconnected`, `error` | `on_system` | `event: str`, `payload: dict[str, Any]` |

Connection 实现侧：reader 解析 JSON 后按 `type` 查表调用对应 handler（若存在）；未注册的 type 可忽略或走 `on_system`。

---

## 4. 组件职责与变更要点

| 模块 | 当前 | 变更后 |
|------|------|--------|
| **run.py** | 创建 asyncio.Queue，传 queue + output_put 给 ws_loop，TUI 回调里 put | 创建/拿到 `GatewayConnection`，传入 `GatewayHandlers`；TUI 回调里 `create_task(conn.send_message(text))` 等；不再创建 input_queue |
| **ws_loop / connection 实现** | run_ws_loop(url, width, input_queue, output_put, ...)；consumer 从 queue get 再 send | 改为 `GatewayWsConnection(ws_url, width, handlers)`：内部 connect + reader；收到消息调 handlers 中对应 on_*；暴露 send_* 方法（直接 `await ws.send(...)`），无 consumer 协程、无 queue |
| **dispatch.py** | _dispatch_ws_message(msg, assembler, width, output_put, ...) | 逻辑迁移：要么并入 connection 的 reader 分支（根据 type 调 on_*），要么由 TUI 的 handlers 实现里调用现有 StreamAssembler + render_messages，再 output_put（即 body_lines.append + invalidate） |
| **TUI handlers** | — | 新建：实现 GatewayHandlers，在 on_text_delta 等里更新 StreamAssembler、在 on_agent_complete 里 render_messages 并 output_put；on_session_switched 等更新 header_state 并 output_put 一行 |
| **input_handler.py** | 发消息/命令时 input_queue.put_nowait(text) 或 put_nowait((cmd, ...)) | 改为接收 `GatewayConnection`，调用 `asyncio.create_task(conn.send_message(text))` 或 `conn.send_abort()` 等 |

**StreamAssembler / render** 保留在 TUI 侧，由 TUI 的 on_* 实现按需调用；connection 层不依赖 StreamAssembler，只依赖 GatewayHandlers 的签名。

---

## 5. 生命周期与错误

- **连接就绪**: connection 实现内部首次 connect 成功后 set(ready_event)；run.py 仍可 `await asyncio.wait_for(ready_event.wait(), timeout=15)` 后再建 layout/app。
- **断线重连**: 在 connection 实现内部 while True + backoff；重连成功后可通过 `on_system("reconnected", {})` 或单独 hook 通知 TUI 打一行 "[system] Connected."。
- **退出**: TUI 退出时调用 `conn.close()`；connection 内部关闭 ws 并结束 reader task；run.py 在 app.run_async() 返回后 cancel connection task 并 await。
- **handler 异常**: 调用 on_* 时 try/except，单条消息失败不拖垮 reader；可 log 并可选调用 on_agent_error 或 on_system("error", {...})。

---

## 6. 测试策略

- **GatewayConnection 协议**: 可定义 Protocol，mock 实现用于 run.py / input_handler 单测（不依赖真实 WebSocket）。
- **Connection 实现**: 单测用 mock websockets、注入 GatewayHandlers，发模拟 JSON 序列，断言调用了正确的 on_* 及参数；send_* 断言发送的 JSON 类型与 payload。
- **TUI handlers**: 单测构造最小 GatewayHandlers（如只实现 on_agent_complete），喂 StreamAssembler 与 output_put，调 handler 断言 body_lines/header_state 变化。
- **dispatch 迁移**: 若保留 _dispatch_ws_message 的纯函数形态供 handlers 复用，现有单测可保留；若完全拆到 handlers 内，则用上述 handler 单测覆盖。

---

## 7. 不做的

- 不保留 asyncio.Queue 用于 TUI ↔ WebSocket 通信。
- 不入站使用「单一联合类型 + 一个 on_message」；坚持按类型多 hook + handlers 对象。
- 出站不引入统一 Outbound 联合类型（采用方式甲，方法即类型）。

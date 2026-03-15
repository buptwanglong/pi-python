# TUI 数据流强类型化 — 设计文档

**目标：** 将 TUI 与 Gateway 之间的 WebSocket 数据流（入站、内部、出站）全部改为强类型，类型定义放在共享包中，供 basket-gateway 与 basket-tui 共同使用。

**范围：** 入站 + 内部 + 出站（选项 C）；类型共享包（选项 C）。

---

## 1. 架构与包职责

- **basket-protocol（新包）**
  - 定义网关 WebSocket 线协议的**入站消息**（服务端→客户端）与**出站消息**（客户端→服务端）的强类型。
  - 提供：**解析**（JSON/dict → 入站类型）、**序列化**（出站类型 → JSON/dict）。
  - 无业务逻辑，不依赖 basket-ai / basket-agent / basket-gateway / basket-tui。

- **basket-gateway**
  - 发送到 WebSocket 时，先构造 protocol 的出站类型（若适用），再序列化。
  - 接收的客户端消息（若需强类型）用 protocol 入站类型解析。
  - 从 agent 事件组装的 payload 先建成 protocol 入站消息类型再序列化发送。

- **basket-tui**
  - 收到 JSON 后用 basket-protocol 解析为入站强类型；内部流水线（connection → dispatch → handlers）全程使用这些类型。
  - 发送时用 protocol 出站类型构造并序列化（send_message、send_abort、send_switch_session 等）。

- **basket-assistant**
  - 不直接依赖 basket-protocol；通过 basket-gateway 与 basket-tui 使用同一套协议。

---

## 2. 协议类型定义（basket-protocol）

### 入站消息（服务端 → 客户端）

- 使用 **dataclass**（或 Pydantic）定义，每种消息一个类型：
  - `TextDelta(delta: str)`
  - `ThinkingDelta(delta: str)`
  - `ToolCallStart(tool_name: str, arguments: dict | None)`
  - `ToolCallEnd(tool_name: str, result: Any, error: str | None)`
  - `AgentComplete()`
  - `AgentError(error: str)`
  - `SessionSwitched(session_id: str)`
  - `AgentSwitched(agent_name: str)`
  - `AgentAborted()`
  - 系统类：`Ready()`, `AgentDisconnected()`, `Error(error: str)` 或统一 `System(event: str, payload: dict)`
- **解析**：`parse_inbound(data: dict) -> InboundMessage`，返回上述类型的 Union；未知 type 可返回 `Unknown(type, payload)` 或抛异常。
- **序列化（服务端发送）**：`inbound_to_dict(msg: InboundMessage) -> dict`，将入站类型转为线格式 dict，供 gateway 发送给客户端。

### 出站消息（客户端 → 服务端）

- `Message(content: str)` → `{"type": "message", "content": "..."}`
- `Abort()`
- `NewSession()`
- `SwitchSession(session_id: str)`
- `SwitchAgent(agent_name: str)`
- **序列化**：`serialize_outbound(msg: OutboundMessage) -> str`（JSON 字符串）。

### 包结构

- `basket_protocol/`：`__init__.py` 导出所有类型 + `parse_inbound` + `serialize_outbound`；实现可放在 `messages.py` 或拆为 `inbound.py` / `outbound.py`。
- 依赖：仅 `python ^3.12`；若用 Pydantic 则加 pydantic。

### 与 basket-assistant 事件的关系

- basket-assistant 的 TextDeltaEvent 等为进程内事件；basket-protocol 为线协议。Gateway 从 agent 事件**组装**为 protocol 入站类型再序列化；basket-protocol 不依赖 basket-assistant。

---

## 3. 数据流与调用链

### 入站（Gateway → TUI）

1. **Connection**：`GatewayWsConnection` 收 `raw` → `json.loads(raw)` → `dict`。
2. **解析**：`basket_protocol.parse_inbound(data)` → `InboundMessage`。
3. **分发**：按类型调用对应 handler；handler 签名为 `Callable[[TextDelta], None]` 等，不再传标量。
4. **Dispatch**：`_dispatch_ws_message(msg: InboundMessage)`，用 isinstance 分派到 `handle_text_delta(assembler, msg.delta, ...)` 等；handle_* 可继续接收标量，在边界解包。
5. **GatewayHandlers**：TypedDict 改为 `on_text_delta: Callable[[TextDelta], None]` 等；`make_handlers` 中 lambda 接收 `event: TextDelta` 再调 `handle_text_delta(assembler, event.delta, ...)`。

### 出站（TUI → Gateway）

- `send_message(text)` 构造 `Message(content=text)`，`serialize_outbound(msg)` 得 JSON，再 `ws.send(...)`；其余 send_* 同理。

### Gateway 侧

- 发送：由 agent 事件构造 `TextDelta(delta=...)` 等，再序列化发送。
- 接收：若需解析客户端 message/switch_session 等，使用协议中的「客户端出站」类型（服务端入站）解析。

### 内部流水线

- `StreamAssembler.text_delta(delta: str)` 等保持不变；强类型仅用于连接边界与 dispatch 入参。

---

## 4. 错误处理与测试

### 错误处理

- **解析失败**：未知 type 或缺字段 → 返回 `Unknown(...)` 或抛异常；TUI `_dispatch` 中 catch 后打 log、忽略该条。
- **序列化**：出站类型正确则一般不抛；若用 Pydantic 校验失败由调用方捕获并打 log。
- **Handler 异常**：保持现状，单条 handler 异常只记 log，不关连接。

### 测试

- **basket-protocol**：单元测试覆盖 `parse_inbound`（每种 type 一条）、`serialize_outbound`（每种出站类型）；未知 type/缺字段边界。
- **basket-tui**：现有 test_dispatch / test_connection / test_run 改为传入强类型或保留「dict → parse → dispatch」集成测试。
- **basket-gateway**：若改用 protocol 发送，补发送 text_delta 后客户端可解析为 TextDelta 的测试或沿用 E2E。

---

## 批准记录

- 方案：方案一（新建 basket-protocol）
- 范围：入站 + 内部 + 出站；类型共享包
- 第 1–4 节设计均已通过。

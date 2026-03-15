# TUI 数据流强类型化 — 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 新增 basket-protocol 包定义网关 WebSocket 入站/出站强类型，basket-tui 与 basket-gateway 改用该类型解析与序列化，实现整条数据流强类型化。

**Architecture:** 新建 packages/basket-protocol，仅含类型与 parse_inbound/serialize_outbound；basket-tui 在 connection 层解析为 InboundMessage、handler 签名改为接收强类型、send_* 使用 Outbound 类型序列化；basket-gateway 发送时构造 protocol 类型再序列化。

**Tech Stack:** Python 3.12, dataclass（或 Pydantic）, Poetry monorepo.

**设计文档:** `docs/plans/2026-03-15-tui-strong-typed-data-flow-design.md`

---

## Task 1: 创建 basket-protocol 包骨架与入站类型

**Files:**
- Create: `packages/basket-protocol/pyproject.toml`
- Create: `packages/basket-protocol/basket_protocol/__init__.py`
- Create: `packages/basket-protocol/basket_protocol/inbound.py`
- Test: `packages/basket-protocol/tests/test_inbound.py`

**Step 1: 添加 pyproject.toml**

在 `packages/basket-protocol/pyproject.toml` 中定义包：name = "basket-protocol", python = "^3.12", packages = [{include = "basket_protocol"}]，无额外依赖。dev-dependencies: pytest, pytest-asyncio。

**Step 2: 写入入站 dataclass 与 parse_inbound 占位**

在 `basket_protocol/inbound.py` 中定义：TextDelta(delta: str), ThinkingDelta(delta: str), ToolCallStart(tool_name: str, arguments: dict | None), ToolCallEnd(tool_name: str, result: Any, error: str | None), AgentComplete(), AgentError(error: str), SessionSwitched(session_id: str), AgentSwitched(agent_name: str), AgentAborted(), System(event: str, payload: dict)。定义 InboundMessage 为上述类型的 Union。实现 `parse_inbound(data: dict) -> InboundMessage`：根据 data.get("type") 分支构造对应类型，未知 type 返回或抛异常（设计文档约定）。在 `__init__.py` 中导出 InboundMessage、各入站类型、parse_inbound。

**Step 3: 写 parse_inbound 的失败测试**

在 `packages/basket-protocol/tests/test_inbound.py` 中写 test_parse_inbound_text_delta：传入 `{"type": "text_delta", "delta": "hi"}`，断言 parse_inbound 返回 TextDelta(delta="hi")。再写 test_parse_inbound_unknown_type：传入 `{"type": "unknown"}`，断言行为（返回 Unknown 或抛异常，与设计一致）。

**Step 4: 运行测试确认失败**

Run: `cd packages/basket-protocol && poetry install && poetry run pytest tests/test_inbound.py -v`  
Expected: 若尚未实现 parse_inbound 或类型未导出则 FAIL。

**Step 5: 实现 parse_inbound 使测试通过**

补全 inbound.py 与 __init__.py，使 test_parse_inbound_text_delta 与 test_parse_inbound_unknown_type 通过。

**Step 6: 运行测试确认通过**

Run: `cd packages/basket-protocol && poetry run pytest tests/test_inbound.py -v`  
Expected: PASS

**Step 7: Commit**

```bash
git add packages/basket-protocol
git commit -m "feat(basket-protocol): add inbound message types and parse_inbound"
```

---

## Task 2: 补全入站类型与 parse_inbound 覆盖所有 type

**Files:**
- Modify: `packages/basket-protocol/basket_protocol/inbound.py`
- Modify: `packages/basket-protocol/tests/test_inbound.py`

**Step 1: 为每种入站 type 写测试**

在 test_inbound.py 中为 thinking_delta, tool_call_start, tool_call_end, agent_complete, agent_error, session_switched, agent_switched, agent_aborted, ready, agent_disconnected, error 各写一条 test_parse_inbound_*，断言 parse_inbound 返回对应类型且字段正确。

**Step 2: 运行测试**

Run: `cd packages/basket-protocol && poetry run pytest tests/test_inbound.py -v`  
Expected: 新增测试部分 FAIL 直到实现补全。

**Step 3: 补全 parse_inbound 分支**

在 inbound.py 的 parse_inbound 中为每种 type 构造对应 dataclass，缺字段用默认值（与现有 gateway 行为一致，如 delta 默认 ""）。

**Step 4: 运行测试**

Run: `cd packages/basket-protocol && poetry run pytest tests/test_inbound.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add packages/basket-protocol
git commit -m "feat(basket-protocol): parse all inbound message types"
```

---

## Task 3: 出站类型与 serialize_outbound

**Files:**
- Create: `packages/basket-protocol/basket_protocol/outbound.py`
- Modify: `packages/basket-protocol/basket_protocol/__init__.py`
- Create: `packages/basket-protocol/tests/test_outbound.py`

**Step 1: 写出站 dataclass**

在 outbound.py 中定义 Message(content: str), Abort(), NewSession(), SwitchSession(session_id: str), SwitchAgent(agent_name: str)。定义 OutboundMessage 为上述 Union。

**Step 2: 实现 serialize_outbound(msg: OutboundMessage) -> str**

根据类型返回 json.dumps({"type": "message", "content": msg.content}) 等。在 __init__.py 导出 OutboundMessage、各出站类型、serialize_outbound。

**Step 3: 写测试**

在 test_outbound.py 中 test_serialize_message、test_serialize_abort、test_serialize_switch_session 等，断言 serialize_outbound 返回的 JSON 与预期一致。

**Step 4: 运行测试**

Run: `cd packages/basket-protocol && poetry run pytest tests/test_outbound.py -v`  
Expected: PASS（若先写测试再实现则先 FAIL 再 PASS）

**Step 5: Commit**

```bash
git add packages/basket-protocol
git commit -m "feat(basket-protocol): add outbound types and serialize_outbound"
```

---

## Task 4: basket-tui 依赖 basket-protocol 并在 connection 层解析

**Files:**
- Modify: `packages/basket-tui/pyproject.toml`
- Modify: `packages/basket-tui/basket_tui/native/connection/client.py`
- Modify: `packages/basket-tui/basket_tui/native/connection/types.py`
- Test: `packages/basket-tui/tests/native/test_connection.py`

**Step 1: 添加依赖**

在 basket-tui/pyproject.toml 的 dependencies 中添加 basket-protocol = {path = "../basket-protocol", develop = true}。

**Step 2: 修改 GatewayHandlers 签名**

在 connection/types.py 中，将 on_text_delta 改为 Callable[[TextDelta], None]，on_thinking_delta 改为 Callable[[ThinkingDelta], None]，以此类推，使用 basket_protocol 的入站类型。需从 basket_protocol 导入 TextDelta, ThinkingDelta 等。

**Step 3: client 中解析后分发**

在 client.py 的 _dispatch 中：先 data = json.loads(raw) 后，调用 msg = parse_inbound(data)；再根据 isinstance(msg, TextDelta) 等调用对应 handler(msg)，不再用 msg.get("delta", "")。

**Step 4: 写/改测试**

在 test_connection.py 中，reader 仍 yield JSON 字符串；断言 on_text_delta 被调用时收到的是 TextDelta 实例且 delta 正确。必要时把 test 里构造的 dict 改为经 parse_inbound( dict ) 得到强类型再传给 dispatch，或保持从 JSON 读入再 dispatch 的路径。

**Step 5: 运行测试**

Run: `cd packages/basket-tui && poetry install && poetry run pytest tests/native/test_connection.py -v`  
Expected: PASS

**Step 6: Commit**

```bash
git add packages/basket-tui
git commit -m "feat(basket-tui): use basket-protocol for inbound parsing and handler types"
```

---

## Task 5: basket-tui handlers 与 dispatch 接收强类型

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/handle/handlers.py`
- Modify: `packages/basket-tui/basket_tui/native/handle/dispatch.py`
- Test: `packages/basket-tui/tests/native/test_dispatch.py`, `tests/native/test_handlers.py`, `tests/native/test_run.py`

**Step 1: make_handlers 传入强类型**

在 handlers.py 中，on_text_delta 的 lambda 改为接收 event: TextDelta，调用 handle_text_delta(assembler, event.delta, ui_state)。其余 on_* 同理（从 event 取字段）。

**Step 2: dispatch 层接受 InboundMessage**

若保留 _dispatch_ws_message，其签名改为 msg: InboundMessage；内部用 isinstance(msg, TextDelta) 等分派，调用 handle_text_delta(assembler, msg.delta, ...)。若 dispatch 仅被 client 调用且 client 已解析，则 client 直接按类型调 handler，可不再需要 _dispatch_ws_message(msg: dict) 的 dict 版本；若有测试仍传 dict，则测试改为先 parse_inbound 再传入。

**Step 3: 更新测试**

test_dispatch 与 test_handlers、test_run 中所有传入 dict 的地方改为传入强类型（如 TextDelta(delta="hi")）。运行 pytest 确保通过。

**Step 4: 运行测试**

Run: `cd packages/basket-tui && poetry run pytest tests/native/ -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add packages/basket-tui
git commit -m "refactor(basket-tui): dispatch and handlers use protocol inbound types"
```

---

## Task 6: basket-tui 出站使用 protocol 类型序列化

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/connection/client.py`

**Step 1: send_* 改为构造 Outbound 并序列化**

在 client.py 中，send_message(text) 改为 msg = Message(content=text)，然后 ws.send(serialize_outbound(msg))。send_abort、send_new_session、send_switch_session、send_switch_agent 同理使用 Abort(), NewSession(), SwitchSession(session_id=...), SwitchAgent(agent_name=...) 后 serialize_outbound。

**Step 2: 运行测试**

Run: `cd packages/basket-tui && poetry run pytest tests/native/ -v`  
Expected: PASS

**Step 3: Commit**

```bash
git add packages/basket-tui
git commit -m "feat(basket-tui): send outbound messages via basket-protocol"
```

---

## Task 7: basket-gateway 发送时使用 protocol 类型

**Files:**
- Modify: `packages/basket-gateway/pyproject.toml`
- Modify: `packages/basket-gateway/basket_gateway/gateway.py`

**Step 1: 添加 basket-protocol 依赖**

在 basket-gateway/pyproject.toml 的 dependencies 中添加 basket-protocol = {path = "../basket-protocol", develop = true}。

**Step 2: 发送前构造入站类型并序列化**

在 gateway.py 中，订阅 text_delta 时构造 TextDelta(delta=e.get("delta", ""))，再发送 serialize_outbound 的等价物——注意 protocol 里 serialize_outbound 是「出站（客户端→服务端）」；服务端发给客户端的是「入站」消息，需在 protocol 中提供 to_dict 或 serialize_inbound（或统一命名，如服务端发送的用 serialize_server_to_client）。设计文档中「Gateway 从 agent 事件组装为 protocol 入站类型再序列化」：即服务端发送的是「入站」类型的线格式，所以 protocol 应提供「入站类型 → dict/JSON」的序列化（例如 each dataclass has to_dict() 或 module 级 serialize_inbound(msg: InboundMessage) -> str）。在 Task 1–2 的 inbound 中补充：入站类型可序列化为 JSON（供 gateway 发送），即实现 serialize_inbound 或 to_dict。本任务中 gateway 改为构造 TextDelta(...)、ThinkingDelta(...) 等，再调用 serialize_inbound 或 json.dumps(msg.to_dict()) 后发送。

**Step 3: 运行 gateway 相关测试**

Run: `cd packages/basket-gateway && poetry install && poetry run pytest -v`  
Expected: PASS

**Step 4: Commit**

```bash
git add packages/basket-gateway
git commit -m "feat(basket-gateway): send WebSocket messages via basket-protocol"
```

---

## Task 8: 边界与文档收尾

**Files:**
- Modify: `packages/basket-protocol/README.md`（若存在）或补充 docstring）
- 可选：`docs/plans/2026-03-15-tui-strong-typed-data-flow-design.md` 中补充「入站类型序列化（服务端发送）」说明

**Step 1: 在 basket-protocol 中补充入站序列化**

若 gateway 需要「服务端→客户端」的序列化，在 inbound.py 增加 serialize_inbound(msg: InboundMessage) -> str，或为各入站类型提供 as_dict()，再 json.dumps。确保 gateway 与 tui 的线格式一致。

**Step 2: 运行全量测试**

Run: `cd packages/basket-tui && poetry run pytest -v`；`cd packages/basket-gateway && poetry run pytest -v`；`cd packages/basket-protocol && poetry run pytest -v`  
Expected: 全部 PASS

**Step 3: Commit**

```bash
git add packages/basket-protocol packages/basket-gateway docs/plans
git commit -m "docs: protocol serialization and design doc update"
```

---

## 执行方式

计划已保存到 `docs/plans/2026-03-15-tui-strong-typed-data-flow-plan.md`。可选两种执行方式：

1. **本会话子 agent 驱动** — 按任务拆给子 agent，每任务后你做 review，迭代快。  
2. **并行会话** — 在新会话（建议用 executing-plans 的 worktree）中按计划逐任务执行，带检查点。

你选哪种？

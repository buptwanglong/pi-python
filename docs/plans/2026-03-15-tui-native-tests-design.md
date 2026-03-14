# tui-native 测试补充 — 设计

**日期**: 2026-03-15  
**目的**: 先补齐 `_dispatch_ws_message` 的单元测试（header_state、ui_state、agent_aborted、agent_error、error、last_output_count），再增加 1～2 个集成场景测试（多 tool + assistant、或两轮 agent_complete）。

**范围**: `packages/basket-tui/tests/native/`，仅扩展现有 test_run.py 与 test_run_integration.py，不新开文件。

---

## 1. A — 补齐 dispatch 单元测试（test_run.py）

**目标**: 为 `_dispatch_ws_message` 的可见行为补全单测，不依赖 WebSocket / prompt_toolkit。

### 1.1 共用方式

- 在 test_run.py 增加一个最小 helper（如 `_dispatch_setup()`），返回 `(assembler, out, output_put, last_output_count, header_state, ui_state)`，默认 `header_state` / `ui_state` 为可写 dict，便于新用例只传需要的 state。
- 不引入 prompt_toolkit/websockets，只测 `_dispatch_ws_message` 的入参、出参与 side effect。

### 1.2 新增用例

| 用例 | 行为 |
|------|------|
| **header_state — session_switched** | 传入 `header_state`，发 `session_switched`，断言 `header_state["session"] == msg["session_id"]`，且 output 含 session 文案。 |
| **header_state — agent_switched** | 传入 `header_state`，发 `agent_switched`，断言 `header_state["agent"] == msg["agent_name"]`，且 output 含 agent 文案。 |
| **ui_state — phase** | 传入 `ui_state`，依次发 `text_delta` → 断言 `phase == "streaming"`；`tool_call_start` → 断言 `phase == "tool_running"`；`agent_complete` → 断言 `phase == "idle"`；`agent_error` → 断言 `phase == "error"`。可拆成 2～4 个用例。 |
| **agent_aborted** | 先 `text_delta("x")` 或 `tool_call_start`，再 `agent_aborted`；断言 output 含 "Aborted"，且 assembler 的 buffer/thinking_buffer/current_tool 已清空（在可观测范围内）。 |
| **agent_error** | 发 `agent_error` 且带 `error` 文案，断言 output 一行包含该文案。 |
| **error (gateway)** | 发 `type: "error"`，断言 output 含 gateway 错误文案。 |
| **last_output_count** | 先 tool_call_start + tool_call_end（一条 tool），再 text_delta("ok") + agent_complete（一条 assistant）；断言 `last_output_count[0] == 2`，且 output 中先出现 tool 内容再出现 assistant 内容（strip ANSI 后断言顺序或 substring）。 |

### 1.3 验收

- `pytest packages/basket-tui/tests/native/test_run.py -v` 全部通过。
- `_dispatch_ws_message` 分支覆盖率明显提升（目标：覆盖当前所有分支）。

---

## 2. B — 集成场景（test_run_integration.py）

**目标**: 用 1～2 个端到端序列验证「多消息一次 agent_complete」或「多轮」下的输出顺序与内容。

### 2.1 场景 1：一轮含多 tool + 一条 assistant

- 序列：`tool_call_start` + `tool_call_end`（tool A），`tool_call_start` + `tool_call_end`（tool B），`text_delta("Done.")`，`agent_complete`。
- 断言：assembler.messages 长度为 3（tool, tool, assistant）；output（strip ANSI）中依次出现 tool A 内容、tool B 内容、"Done."（或 assistant 片段）。

### 2.2 场景 2（可选）：两轮 agent_complete

- 序列：第一轮 text_delta + agent_complete，第二轮 text_delta + agent_complete。
- 断言：messages 长度为 2；last_output_count 为 2；output 中两段 assistant 内容均出现且顺序正确。

### 2.3 验收

- `pytest packages/basket-tui/tests/native/test_run_integration.py -v` 全部通过。

---

## 3. 错误处理与约束

- 所有新测试不启动真实 WebSocket、不依赖 prompt_toolkit 事件循环；仅调用 `_dispatch_ws_message` 或 StreamAssembler + render 路径。
- 若某分支在实现上不可观测（如仅 log），可略过该分支的断言，不强行写断言。

---

## 4. 实现顺序

1. 实现 A：test_run.py 中 helper + 上述 dispatch 用例，跑通并提交。
2. 实现 B：test_run_integration.py 中场景 1（必选）、场景 2（可选），跑通并提交。

---

**批准**: 设计已确认，实现计划见 `docs/plans/2026-03-15-tui-native-tests-plan.md`。

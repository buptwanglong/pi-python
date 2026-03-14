# tui-native 测试补充 — 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 test_run.py 中补齐 _dispatch_ws_message 的单元测试（header_state、ui_state、agent_aborted、agent_error、error、last_output_count），在 test_run_integration.py 中增加 1～2 个集成场景（多 tool + assistant、可选两轮 agent_complete）。

**Architecture:** 不新开测试文件；test_run.py 增加一个 _dispatch_setup() helper 和若干新用例；test_run_integration.py 增加序列测试。所有测试仅调用 _dispatch_ws_message / StreamAssembler，不启动 WebSocket 或 prompt_toolkit。

**Tech Stack:** pytest, pytest-asyncio（若需要），现有 basket_tui.native.run / stream。

**设计依据:** `docs/plans/2026-03-15-tui-native-tests-design.md`

---

## Phase A: dispatch 单元测试（test_run.py）

### Task 1: 添加 _dispatch_setup helper

**Files:**
- Modify: `packages/basket-tui/tests/native/test_run.py`

**Step 1:** 在文件顶部（import 之后）添加 helper 函数，返回 (assembler, out, output_put, last_output_count, header_state, ui_state)，默认 header_state 与 ui_state 为 `{}`，便于新用例传入并断言。

```python
def _dispatch_setup():
    """Return (assembler, out, output_put, last_output_count, header_state, ui_state) for _dispatch_ws_message tests."""
    assembler = StreamAssembler()
    width = 80
    out = []
    output_put = out.append
    last_output_count = [0]
    header_state = {}
    ui_state = {}
    return assembler, out, output_put, last_output_count, header_state, ui_state
```

**Step 2:** 运行现有测试，确保无回归：`cd packages/basket-tui && poetry run pytest tests/native/test_run.py -v`，Expected: 全部 PASS。

**Step 3:** 提交：`git add packages/basket-tui/tests/native/test_run.py && git commit -m "test(basket-tui): add _dispatch_setup helper for native run tests"`

---

### Task 2: header_state — session_switched 与 agent_switched

**Files:**
- Modify: `packages/basket-tui/tests/native/test_run.py`

**Step 1:** 添加 test_dispatch_session_switched_updates_header_state：用 _dispatch_setup，设 header_state["session"] = "old"，调用 _dispatch_ws_message session_switched session_id="s1"，断言 header_state["session"] == "s1" 且 out 中有一行含 "s1"。

**Step 2:** 添加 test_dispatch_agent_switched_updates_header_state：同理，agent_switched agent_name="my_agent"，断言 header_state["agent"] == "my_agent" 且 out 含 "my_agent"。

**Step 3:** 运行：`cd packages/basket-tui && poetry run pytest tests/native/test_run.py -v -k "header_state or session_switched or agent_switched"`，Expected: 注意现有 test_dispatch_session_switched_prints_line 等不传 header_state，新用例传 header_state 并断言 state。若现有用例未传 header_state，保持不动（_dispatch_ws_message 接受 None）。新用例需传 header_state 和 ui_state（可选），签名已支持。运行全部 test_run：`poetry run pytest tests/native/test_run.py -v`，Expected: PASS。

**Step 4:** 提交：`git add packages/basket-tui/tests/native/test_run.py && git commit -m "test(basket-tui): dispatch header_state updated on session_switched and agent_switched"`

---

### Task 3: ui_state — phase 更新

**Files:**
- Modify: `packages/basket-tui/tests/native/test_run.py`

**Step 1:** 添加 test_dispatch_ui_state_phase_streaming：_dispatch_setup，发 text_delta，断言 ui_state["phase"] == "streaming"。

**Step 2:** 添加 test_dispatch_ui_state_phase_tool_running：发 tool_call_start，断言 ui_state["phase"] == "tool_running"。

**Step 3:** 添加 test_dispatch_ui_state_phase_idle：发 agent_complete（可先 text_delta 再 agent_complete），断言 ui_state["phase"] == "idle"。

**Step 4:** 添加 test_dispatch_ui_state_phase_error：发 agent_error，断言 ui_state["phase"] == "error"。

**Step 5:** 运行：`cd packages/basket-tui && poetry run pytest tests/native/test_run.py -v -k "ui_state or phase"`，Expected: PASS。再运行全量 test_run.py，Expected: PASS。

**Step 6:** 提交：`git add packages/basket-tui/tests/native/test_run.py && git commit -m "test(basket-tui): dispatch ui_state phase on text_delta, tool_call_start, agent_complete, agent_error"`

---

### Task 4: agent_aborted 与 agent_error、error 类型

**Files:**
- Modify: `packages/basket-tui/tests/native/test_run.py`

**Step 1:** 添加 test_dispatch_agent_aborted_clears_and_prints：先 text_delta("x") 或 tool_call_start，再 agent_aborted；断言 out 中有一行含 "Aborted"，且 assembler._buffer == ""、assembler._current_tool is None（或已清空）。

**Step 2:** 添加 test_dispatch_agent_error_prints_message：发 agent_error error="Something failed"，断言 out 有一行含 "Something failed"。

**Step 3:** 添加 test_dispatch_error_type_prints_gateway_error：发 type "error" error="Gateway down"，断言 out 含 "Gateway" 或 "down"（或实际 output 文案）。

**Step 4:** 运行：`cd packages/basket-tui && poetry run pytest tests/native/test_run.py -v`，Expected: PASS。

**Step 5:** 提交：`git add packages/basket-tui/tests/native/test_run.py && git commit -m "test(basket-tui): dispatch agent_aborted, agent_error, error type"`

---

### Task 5: last_output_count 多消息一轮

**Files:**
- Modify: `packages/basket-tui/tests/native/test_run.py`

**Step 1:** 添加 test_dispatch_last_output_count_after_tool_and_assistant：先 tool_call_start + tool_call_end（一条 tool），再 text_delta("ok") + agent_complete；断言 last_output_count[0] == 2；断言 out（可 strip ANSI）中先出现 tool 相关文本再出现 "ok"（或 assistant 片段）。使用 _dispatch_setup 或手写 assembler/out/last_output_count，并传入 header_state=None、ui_state 可选。

**Step 2:** 运行：`cd packages/basket-tui && poetry run pytest tests/native/test_run.py -v -k last_output_count`，Expected: PASS。全量 test_run.py：PASS。

**Step 3:** 提交：`git add packages/basket-tui/tests/native/test_run.py && git commit -m "test(basket-tui): dispatch last_output_count advances for tool then assistant"`

---

## Phase B: 集成场景（test_run_integration.py）

### Task 6: 一轮多 tool + 一条 assistant

**Files:**
- Modify: `packages/basket-tui/tests/native/test_run_integration.py`

**Step 1:** 添加 test_dispatch_multiple_tools_then_assistant_in_one_turn：序列 tool_call_start/end（tool A），tool_call_start/end（tool B），text_delta("Done.")，agent_complete。断言 len(assembler.messages) == 3；output（strip ANSI）中依次出现 tool A 内容、tool B 内容、"Done."（或 assistant 片段）。复用文件内 _strip_ansi。

**Step 2:** 运行：`cd packages/basket-tui && poetry run pytest tests/native/test_run_integration.py -v`，Expected: PASS。

**Step 3:** 提交：`git add packages/basket-tui/tests/native/test_run_integration.py && git commit -m "test(basket-tui): integration multiple tools then assistant in one turn"`

---

### Task 7（可选）: 两轮 agent_complete

**Files:**
- Modify: `packages/basket-tui/tests/native/test_run_integration.py`

**Step 1:** 添加 test_dispatch_two_rounds_agent_complete：第一轮 text_delta("First") + agent_complete，第二轮 text_delta("Second") + agent_complete。断言 len(assembler.messages) == 2，last_output_count[0] == 2，output 中 "First" 与 "Second" 均出现且顺序合理。

**Step 2:** 运行：`cd packages/basket-tui && poetry run pytest tests/native/test_run_integration.py -v`，Expected: PASS。

**Step 3:** 提交：`git add packages/basket-tui/tests/native/test_run_integration.py && git commit -m "test(basket-tui): integration two rounds agent_complete"`

---

## 完成验收

- 运行：`cd packages/basket-tui && poetry run pytest tests/native/ -v`，所有用例通过。
- 可选：`poetry run pytest packages/basket-tui/tests/native/ --cov=basket_tui.native.run --cov-report=term-missing` 查看 _dispatch_ws_message 覆盖率。

---

**执行选项：** 可按任务顺序在本会话中逐项实现，或在新会话使用 executing-plans 按检查点执行。

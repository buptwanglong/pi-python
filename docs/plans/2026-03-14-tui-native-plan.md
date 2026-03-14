# Terminal-Native TUI (tui-native) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a new subcommand `basket tui-native` (alias `basket tn`) that uses line-by-line stdout + prompt_toolkit for input, giving Markdown rendering and terminal-native selection/copy while matching existing TUI features (pickers, settings, shortcuts).

**Architecture:** New module inside basket-tui (e.g. `basket_tui.native`). Content (header, messages, tool blocks, footer) is rendered to ANSI and written line-by-line to stdout so it stays in terminal scrollback and is selectable. Input and overlays (session/agent/model pickers, settings) use prompt_toolkit. Same gateway WebSocket URL and message protocol as existing attach mode.

**Tech Stack:** Python 3.12+, prompt_toolkit, Rich (Markdown→ANSI), websockets, basket-assistant gateway client/events.

---

## Phase 1: Foundation and CLI entry

### Task 1: Add prompt_toolkit dependency to basket-tui

**Files:**
- Modify: `packages/basket-tui/pyproject.toml`

**Step 1:** Add optional or main dependency `prompt_toolkit` (e.g. `prompt_toolkit = "^3.0"`).

**Step 2:** Run `cd packages/basket-tui && poetry lock && poetry install`. Verify no conflict.

**Step 3:** Commit: "deps(basket-tui): add prompt_toolkit for native TUI"

---

### Task 2: Create native TUI package layout and line renderer (no I/O yet)

**Files:**
- Create: `packages/basket-tui/basket_tui/native/__init__.py`
- Create: `packages/basket-tui/basket_tui/native/render.py` (line renderer: messages + width → list of ANSI lines)
- Test: `packages/basket-tui/tests/native/test_render.py`

**Step 1: Write failing test**

In `tests/native/test_render.py`: test that `render_messages(messages, width=80)` returns a list of strings, each of visible length ≤ 80; include one assistant message with simple Markdown (`**bold**`) and assert the output contains ANSI and the bold text.

**Step 2:** Run test — expect FAIL (module/function missing).

**Step 3:** Implement minimal `render.py`: function `render_messages(messages, width)` that iterates messages, uses Rich to render assistant content as Markdown→ANSI, splits by newline, and wraps each line to `width` (use Rich or a small helper so no line exceeds width). Return list of lines.

**Step 4:** Run test — expect PASS.

**Step 5:** Commit: "feat(basket-tui): native line renderer for messages"

---

### Task 3: Stream assembler (in-memory state only)

**Files:**
- Create: `packages/basket-tui/basket_tui/native/stream.py`
- Test: `packages/basket-tui/tests/native/test_stream.py`

**Step 1: Write failing test**

Test that after feeding `text_delta("Hello")`, `text_delta(" world")`, `agent_complete()`, the assembler’s message list has one assistant message with content "Hello world". Test that `tool_call_start("bash", {...})` and `tool_call_end("bash", result="ok")` add a tool block to the state.

**Step 2:** Run test — FAIL.

**Step 3:** Implement `StreamAssembler` with methods for text_delta, thinking_delta (optional), tool_call_start, tool_call_end, agent_complete; internal state: list of messages + current streaming buffer + current tool block. On agent_complete, append assistant message from buffer and clear buffer.

**Step 4:** Run test — PASS.

**Step 5:** Commit: "feat(basket-tui): native stream assembler"

---

### Task 4: Register `tui-native` / `tn` in basket-assistant and stub runner

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/main.py`
- Create: `packages/basket-tui/basket_tui/native/run.py` (stub that prints "tui-native not implemented" and exits, or connects once we have WS)

**Step 1:** In main.py, beside `use_tui = (args[0] == "tui")`, add `use_tui_native = len(args) >= 1 and args[0] in ("tui-native", "tn")`. If true, pop the subcommand from args like tui. Parse `--agent` (and any other shared flags) the same way.

**Step 2:** After the block that runs `run_tui_mode_attach` for `use_tui`, add a block for `use_tui_native`: ensure gateway is running (same logic as tui), get `attach_url`, then call `run_tui_native_attach(attach_url, agent_name=tui_agent, max_cols=tui_max_cols)`. Import from basket_tui.native.run or basket_tui.native.

**Step 3:** Implement `run_tui_native_attach` in basket_tui/native/run.py as an async function that for now only connects to the WebSocket, prints one line "[system] Connected (native)." and exits (or runs a minimal prompt_toolkit prompt once). This proves the CLI and gateway discovery path.

**Step 4:** Run from repo root: `poetry run basket tui-native` (or `basket tn`) and confirm gateway starts if needed and the stub runs.

**Step 5:** Commit: "feat(basket-assistant): add tui-native/tn subcommand and stub runner"

---

## Phase 2: WebSocket loop and minimal chat

### Task 5: WebSocket reader and event dispatch in native run

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1:** In `run_tui_native_attach`, after connecting WebSocket, start a background task that reads JSON messages and dispatches by `type`: `text_delta`, `thinking_delta`, `tool_call_start`, `tool_call_end`, `agent_complete`, `agent_error`. Pass payloads to a `StreamAssembler` instance and to a simple "output" callback that for now appends lines to an in-memory list (or prints them to stdout).

**Step 2:** On `agent_complete`, call the line renderer with current message list + stream buffer, then output the new lines (e.g. print to stdout). Ensure no full-screen clear — only append lines so terminal scrollback is preserved.

**Step 3:** Manual test: run `basket tui-native`, send a message from another client or a script to the same gateway and verify the native client prints the reply (or run a one-shot send from the stub input if already wired).

**Step 4:** Commit: "feat(basket-tui): native WebSocket dispatch and line output"

---

### Task 6: prompt_toolkit input loop and send message

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1:** Add a prompt_toolkit-based input loop (or Application with a single multiline input at bottom). On submit: if text is `/help`, print help lines to stdout and re-prompt; if text is a normal message, send `{"type":"message","content":text}` over the WebSocket and add the user message to the message list, then redraw (append) the new user line(s) to stdout.

**Step 2:** Coordinate WebSocket reader and input loop (asyncio: run WebSocket reader in a task and prompt_toolkit in the main thread, or run both in one event loop with prompt_toolkit’s async support). Ensure incoming assistant messages and tool blocks trigger a redraw (append only) of the new content.

**Step 3:** Manual test: run `basket tui-native`, type a message, Enter; verify it appears in the terminal and the assistant reply streams and appears selectable; select text in terminal and copy.

**Step 4:** Commit: "feat(basket-tui): native prompt_toolkit input and send message"

---

## Phase 3: Slash commands and pickers

### Task 7: Slash command routing and /help, /exit

**Files:**
- Create: `packages/basket-tui/basket_tui/native/commands.py` (or inline in run.py)
- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1:** On input submit, if text starts with `/`, parse command (e.g. `/help`, `/exit`, `/session`, `/agent`, `/model`, `/new`, `/abort`, `/settings`). Implement `/help` (print list of commands to stdout) and `/exit` (clean shutdown and exit). Others can stub to "Not implemented yet" or no-op.

**Step 2:** Wire in run.py so that slash commands are handled before sending to gateway.

**Step 3:** Manual test: `/help`, `/exit`.

**Step 4:** Commit: "feat(basket-tui): native slash commands /help, /exit"

---

### Task 8: Session picker (prompt_toolkit overlay)

**Files:**
- Create: `packages/basket-tui/basket_tui/native/pickers.py`
- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1:** Add a function that fetches session list (from gateway API or config; reuse same source as existing TUI). Display with prompt_toolkit full-screen list (arrow keys, Enter to select, Esc to cancel). On select, send session switch to gateway (same API as existing TUI) and update local session state; optionally reload history and redraw.

**Step 2:** Wire `/session` (and optionally `/sessions`) to open this picker.

**Step 3:** Manual test: `/session`, choose a session, verify switch.

**Step 4:** Commit: "feat(basket-tui): native session picker"

---

### Task 9: Agent and model pickers

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/pickers.py`
- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1:** Implement agent picker (list agents from gateway/config, prompt_toolkit list, on select send agent switch and update state). Implement model picker similarly.

**Step 2:** Wire `/agent`, `/agents`, `/model`, `/models` to these pickers.

**Step 3:** Manual test: switch agent and model.

**Step 4:** Commit: "feat(basket-tui): native agent and model pickers"

---

### Task 10: /new, /abort, /settings (and footer/header)

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/run.py`, `render.py`

**Step 1:** Implement `/new` (reset session via gateway), `/abort` (send abort to gateway, clear stream state, print "[system] Aborted."). Implement `/settings` as a prompt_toolkit overlay (toggle deliver, tool expansion, thinking visibility if supported by gateway).

**Step 2:** Add header line (connection URL, agent, session) and footer line (status, model, tokens) to the line renderer output; refresh footer on each update without clearing scrollback (e.g. overwrite last line or reserve last line for footer).

**Step 3:** Manual test: /new, /abort, /settings; confirm header/footer visible.

**Step 4:** Commit: "feat(basket-tui): native /new, /abort, /settings and header/footer"

---

## Phase 4: Polish and tests

### Task 11: Reconnect and error handling

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1:** On WebSocket close/error, print "[system] Disconnected. Reconnecting..." and start a backoff reconnect loop. On success, print "[system] Connected." and optionally reload history. On parse error or agent_error, print "[system] Error: ..." and log.

**Step 2:** On terminal resize, get new size and re-render last N lines or full content (without clearing scrollback if possible) so layout is correct.

**Step 3:** Manual test: kill gateway and restart, resize terminal.

**Step 4:** Commit: "feat(basket-tui): native reconnect and error handling"

---

### Task 12: Unit tests for render and stream

**Files:**
- Extend: `packages/basket-tui/tests/native/test_render.py`
- Extend: `packages/basket-tui/tests/native/test_stream.py`

**Step 1:** Add tests for edge cases: empty message list, very long line wrapping, Markdown code block; stream assembler with multiple tool calls, thinking delta on/off.

**Step 2:** Run full test suite for basket-tui; fix any regressions.

**Step 3:** Commit: "test(basket-tui): native render and stream tests"

---

### Task 13: Integration test (mock WebSocket)

**Files:**
- Create: `packages/basket-tui/tests/native/test_run_integration.py` (or in basket-assistant if run is there)

**Step 1:** Start a mock WebSocket server that sends a few text_delta and one agent_complete. Run native TUI in a subprocess or with a fake stdin/stdout; assert that stdout contains the expected assistant text (strip ANSI for assertion if needed).

**Step 2:** Run test; commit: "test(basket-tui): native integration test with mock WS"

---

### Task 14: Documentation and help text

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/main.py` (help text for tui-native)
- Modify: `packages/basket-assistant/CONFIG.md` or README if it documents subcommands

**Step 1:** Add help line for `basket tui-native` and `basket tn` in main.py. Document that it uses terminal-native selection/copy and same gateway as `basket tui`.

**Step 2:** Commit: "docs: tui-native subcommand and usage"

---

## Done

After all tasks: run full test suite, manual smoke test of `basket tui` and `basket tui-native`, then mark plan complete.

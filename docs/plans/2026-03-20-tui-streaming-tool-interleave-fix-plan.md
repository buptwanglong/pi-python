# TUI Streaming + Tool Call Interleave Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix message display corruption when LLM streaming and tool calls happen simultaneously in TUI mode, by flushing and rendering messages immediately at each state transition instead of batch-rendering at turn end.

**Architecture:** Add `flush_buffer()` to `StreamAssembler` so the streaming text buffer can be committed on demand. Update `handle_tool_call_start` to flush+render before recording the tool, and `handle_tool_call_end` to render the tool block immediately. Update `handle_agent_complete` to only render remaining un-rendered messages. Wire new parameters through `make_handlers`.

**Tech Stack:** Python 3.12+, pytest, prompt_toolkit, Rich (rendering)

---

### Task 1: Add `flush_buffer()` to StreamAssembler — Tests

**Files:**
- Test: `packages/basket-tui/tests/native/test_stream.py`

**Step 1: Write the failing tests**

Append these two tests to the end of `packages/basket-tui/tests/native/test_stream.py`:

```python
def test_flush_buffer_commits_and_clears():
    """flush_buffer() commits non-empty _buffer as assistant message, clears buffer, returns True."""
    a = StreamAssembler()
    a.text_delta("Hello")
    a.text_delta(" world")
    result = a.flush_buffer()
    assert result is True
    assert len(a.messages) == 1
    assert a.messages[0] == {"role": "assistant", "content": "Hello world"}
    assert a._buffer == ""


def test_flush_buffer_empty_noop():
    """flush_buffer() on empty buffer returns False and adds no message."""
    a = StreamAssembler()
    result = a.flush_buffer()
    assert result is False
    assert len(a.messages) == 0
    assert a._buffer == ""
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_stream.py::test_flush_buffer_commits_and_clears tests/native/test_stream.py::test_flush_buffer_empty_noop -v`

Expected: FAIL with `AttributeError: 'StreamAssembler' object has no attribute 'flush_buffer'`

---

### Task 2: Add `flush_buffer()` to StreamAssembler — Implementation

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/pipeline/stream.py` (insert after `agent_complete` method, before `abort`)

**Step 3: Write minimal implementation**

Insert the following method in `StreamAssembler` class, between `agent_complete()` (line 108) and `abort()` (line 110):

```python
    def flush_buffer(self) -> bool:
        """Commit current _buffer as assistant message if non-empty.

        Returns True if content was committed, False if buffer was empty.
        Used by tool_call_start to commit streaming text before the tool block.
        """
        if not self._buffer:
            return False
        self.messages.append({"role": "assistant", "content": self._buffer})
        buffer_len = len(self._buffer)
        self._buffer = ""
        logger.info(
            "Buffer flushed",
            extra={"buffer_len": buffer_len, "total_messages": len(self.messages)},
        )
        return True
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_stream.py -v`

Expected: ALL PASS (including the two new tests and 4 existing tests)

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/pipeline/stream.py packages/basket-tui/tests/native/test_stream.py
git commit -m "feat(tui): add StreamAssembler.flush_buffer() for immediate text commit"
```

---

### Task 3: Update `handle_tool_call_start` — Tests

**Files:**
- Test: `packages/basket-tui/tests/native/test_dispatch.py`

**Step 6: Write the failing tests**

Append these tests to the end of `packages/basket-tui/tests/native/test_dispatch.py`:

```python
def test_handle_tool_call_start_flushes_buffer_and_renders():
    """When buffer has content, tool_call_start flushes it as assistant msg and renders via output_put."""
    assembler, width, out, output_put, last_output_count = _minimal_setup()
    # Simulate prior streaming
    assembler.text_delta("I'll read the file")
    assert assembler._buffer == "I'll read the file"

    handle_tool_call_start(
        assembler,
        "read",
        arguments={"path": "/etc/hosts"},
        ui_state={"phase": "streaming"},
        width=width,
        output_put=output_put,
        last_output_count=last_output_count,
    )

    # Buffer should be flushed: assistant message committed
    assert assembler._buffer == ""
    assert any(m["role"] == "assistant" and m["content"] == "I'll read the file" for m in assembler.messages)
    # Tool should be recorded
    assert assembler._current_tool is not None
    assert assembler._current_tool["tool_name"] == "read"
    # Output should contain rendered assistant text
    assert len(out) >= 1
    # last_output_count should track the flushed assistant message
    assert last_output_count[0] >= 1


def test_handle_tool_call_start_empty_buffer_no_flush():
    """When buffer is empty, tool_call_start does not add assistant message."""
    assembler, width, out, output_put, last_output_count = _minimal_setup()

    handle_tool_call_start(
        assembler,
        "bash",
        arguments={},
        ui_state={"phase": "idle"},
        width=width,
        output_put=output_put,
        last_output_count=last_output_count,
    )

    # No assistant message added
    assistant_msgs = [m for m in assembler.messages if m["role"] == "assistant"]
    assert len(assistant_msgs) == 0
    # Tool recorded
    assert assembler._current_tool is not None
    assert assembler._current_tool["tool_name"] == "bash"
```

**Step 7: Run tests to verify they fail**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_dispatch.py::test_handle_tool_call_start_flushes_buffer_and_renders tests/native/test_dispatch.py::test_handle_tool_call_start_empty_buffer_no_flush -v`

Expected: FAIL with `TypeError: handle_tool_call_start() got an unexpected keyword argument 'width'`

---

### Task 4: Update `handle_tool_call_start` — Implementation

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/handle/dispatch.py` (the `handle_tool_call_start` function, lines 65-82)

**Step 8: Replace the function**

Replace the entire `handle_tool_call_start` function (lines 65-82) with:

```python
def handle_tool_call_start(
    assembler: StreamAssembler,
    tool_name: str,
    arguments: Optional[dict] = None,
    ui_state: Optional[dict[str, str]] = None,
    width: int = 80,
    output_put: Optional[Callable[[str], None]] = None,
    last_output_count: Optional[list[int]] = None,
) -> None:
    """Handle tool_call_start: flush buffer, set phase tool_running, record current tool."""
    # Flush streaming buffer BEFORE tool starts so text appears before tool block
    if output_put is not None and last_output_count is not None:
        if assembler.flush_buffer():
            msg = assembler.messages[-1]
            for line in render_messages([msg], width):
                output_put(line)
            last_output_count[0] = len(assembler.messages)

    if ui_state is not None:
        ui_state["phase"] = "tool_running"
    assembler.tool_call_start(tool_name, arguments)
    logger.info(
        "Tool call started",
        extra={
            "tool_name": tool_name,
            "args_keys": list(arguments.keys()) if arguments else [],
            "phase": "tool_running",
        },
    )
```

**Step 9: Run tests to verify they pass**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_dispatch.py -v`

Expected: ALL PASS (existing tests still pass because `width`/`output_put`/`last_output_count` default to no-op values)

**Step 10: Commit**

```bash
git add packages/basket-tui/basket_tui/native/handle/dispatch.py packages/basket-tui/tests/native/test_dispatch.py
git commit -m "feat(tui): handle_tool_call_start flushes streaming buffer before tool"
```

---

### Task 5: Update `handle_tool_call_end` — Tests

**Files:**
- Test: `packages/basket-tui/tests/native/test_dispatch.py`

**Step 11: Write the failing tests**

Append these tests to `packages/basket-tui/tests/native/test_dispatch.py`:

```python
def test_handle_tool_call_end_renders_immediately():
    """tool_call_end renders tool block via output_put immediately (not waiting for agent_complete)."""
    assembler, width, out, output_put, last_output_count = _minimal_setup()
    handle_tool_call_start(assembler, "bash", arguments={"cmd": "echo hi"})
    handle_tool_call_end(
        assembler,
        "bash",
        result="hello",
        error=None,
        width=width,
        output_put=output_put,
        last_output_count=last_output_count,
    )

    # Tool message in assembler
    assert len(assembler.messages) == 1
    assert assembler.messages[0]["role"] == "tool"
    # Rendered immediately via output_put
    assert len(out) >= 1
    # last_output_count tracks the rendered tool message
    assert last_output_count[0] == 1


def test_handle_tool_call_end_error_renders_immediately():
    """tool_call_end with error renders error tool block via output_put immediately."""
    assembler, width, out, output_put, last_output_count = _minimal_setup()
    handle_tool_call_start(assembler, "bash", arguments={})
    handle_tool_call_end(
        assembler,
        "bash",
        result=None,
        error="command not found",
        width=width,
        output_put=output_put,
        last_output_count=last_output_count,
    )

    assert len(assembler.messages) == 1
    assert assembler.messages[0]["role"] == "tool"
    assert len(out) >= 1
    assert last_output_count[0] == 1
```

**Step 12: Run tests to verify they fail**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_dispatch.py::test_handle_tool_call_end_renders_immediately tests/native/test_dispatch.py::test_handle_tool_call_end_error_renders_immediately -v`

Expected: FAIL with `TypeError: handle_tool_call_end() got an unexpected keyword argument 'width'`

---

### Task 6: Update `handle_tool_call_end` — Implementation

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/handle/dispatch.py` (the `handle_tool_call_end` function, lines 85-100)

**Step 13: Replace the function**

Replace the entire `handle_tool_call_end` function (lines 85-100) with:

```python
def handle_tool_call_end(
    assembler: StreamAssembler,
    tool_name: str,
    result: Any = None,
    error: Optional[str] = None,
    width: int = 80,
    output_put: Optional[Callable[[str], None]] = None,
    last_output_count: Optional[list[int]] = None,
) -> None:
    """Handle tool_call_end: append tool message and render immediately."""
    assembler.tool_call_end(tool_name, result=result, error=error)

    # Render tool block immediately instead of waiting for agent_complete
    if output_put is not None and last_output_count is not None:
        msg = assembler.messages[-1]
        for line in render_messages([msg], width):
            output_put(line)
        last_output_count[0] = len(assembler.messages)

    logger.info(
        "Tool call ended",
        extra={
            "tool_name": tool_name,
            "has_result": result is not None,
            "has_error": error is not None,
        },
    )
```

**Step 14: Run tests to verify they pass**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_dispatch.py -v`

Expected: ALL PASS

**Step 15: Commit**

```bash
git add packages/basket-tui/basket_tui/native/handle/dispatch.py packages/basket-tui/tests/native/test_dispatch.py
git commit -m "feat(tui): handle_tool_call_end renders tool block immediately"
```

---

### Task 7: Update `make_handlers` to pass new parameters

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/handle/handlers.py` (lines 44-55, the two lambdas)
- Test: `packages/basket-tui/tests/native/test_handlers.py`

**Step 16: Write failing test**

Append this test to `packages/basket-tui/tests/native/test_handlers.py`:

```python
from basket_protocol import ToolCallEnd, ToolCallStart


def test_make_handlers_tool_call_start_flushes_buffer_and_renders() -> None:
    """on_tool_call_start flushes prior streaming buffer to output_put before recording tool."""
    assembler = StreamAssembler()
    assembler.text_delta("Prior text")
    width = 80
    lines_out: list[str] = []

    def output_put(line: str) -> None:
        lines_out.append(line)

    last_output_count = [0]
    header_state: dict[str, str] = {}
    ui_state: dict[str, str] = {"phase": "streaming"}

    handlers = make_handlers(
        assembler, width, output_put, last_output_count, header_state, ui_state
    )

    handlers["on_tool_call_start"](ToolCallStart(tool_name="bash", arguments={"cmd": "ls"}))

    # Buffer should be flushed
    assert assembler._buffer == ""
    # Assistant message committed
    assert any(m["role"] == "assistant" and m["content"] == "Prior text" for m in assembler.messages)
    # Tool recorded
    assert assembler._current_tool is not None
    # Rendered to output
    assert len(lines_out) >= 1
    assert last_output_count[0] >= 1


def test_make_handlers_tool_call_end_renders_immediately() -> None:
    """on_tool_call_end renders tool block via output_put immediately."""
    assembler = StreamAssembler()
    width = 80
    lines_out: list[str] = []

    def output_put(line: str) -> None:
        lines_out.append(line)

    last_output_count = [0]
    header_state: dict[str, str] = {}
    ui_state: dict[str, str] = {}

    handlers = make_handlers(
        assembler, width, output_put, last_output_count, header_state, ui_state
    )

    handlers["on_tool_call_start"](ToolCallStart(tool_name="read", arguments={}))
    handlers["on_tool_call_end"](ToolCallEnd(tool_name="read", result="file data", error=None))

    # Tool message in assembler
    assert any(m["role"] == "tool" for m in assembler.messages)
    # Rendered immediately
    assert len(lines_out) >= 1
    assert last_output_count[0] >= 1
```

**Step 17: Run tests to verify they fail**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_handlers.py::test_make_handlers_tool_call_start_flushes_buffer_and_renders tests/native/test_handlers.py::test_make_handlers_tool_call_end_renders_immediately -v`

Expected: FAIL — the handlers lambda doesn't pass `width`/`output_put`/`last_output_count` to `handle_tool_call_start`/`handle_tool_call_end`, so flush/render won't happen.

**Step 18: Update `make_handlers` lambdas**

In `packages/basket-tui/basket_tui/native/handle/handlers.py`, replace lines 44-55 (the `on_tool_call_start` and `on_tool_call_end` entries) with:

```python
        "on_tool_call_start": lambda event: handle_tool_call_start(
            assembler,
            event.tool_name,
            arguments=event.arguments,
            ui_state=ui_state,
            width=width,
            output_put=output_put,
            last_output_count=last_output_count,
        ),
        "on_tool_call_end": lambda event: handle_tool_call_end(
            assembler,
            event.tool_name,
            result=event.result,
            error=event.error,
            width=width,
            output_put=output_put,
            last_output_count=last_output_count,
        ),
```

**Step 19: Run tests to verify they pass**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_handlers.py -v`

Expected: ALL PASS

**Step 20: Commit**

```bash
git add packages/basket-tui/basket_tui/native/handle/handlers.py packages/basket-tui/tests/native/test_handlers.py
git commit -m "feat(tui): wire flush+render params through make_handlers for tool events"
```

---

### Task 8: Update `_dispatch_ws_message` + integration tests

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/handle/dispatch.py` (the `_dispatch_ws_message` function, lines 217-230)
- Test: `packages/basket-tui/tests/native/test_run_integration.py`

**Step 21: Write failing integration test**

Append this test to `packages/basket-tui/tests/native/test_run_integration.py`:

```python
def test_dispatch_text_then_tool_then_text_renders_in_order():
    """Text → tool → text: each segment rendered immediately in correct order, not batched at end."""
    assembler = StreamAssembler()
    width = 80
    printed: list[str] = []
    output_put = printed.append
    last_output_count: list[int] = [0]
    ui_state: dict[str, str] = {"phase": "idle"}

    # Step 1: streaming text
    _dispatch_ws_message(
        {"type": "text_delta", "delta": "I'll read the file."},
        assembler, width, output_put, last_output_count, ui_state=ui_state,
    )
    assert assembler._buffer == "I'll read the file."
    lines_before_tool = len(printed)

    # Step 2: tool starts → should flush buffer and render assistant text
    _dispatch_ws_message(
        {"type": "tool_call_start", "tool_name": "read", "arguments": {"path": "/tmp/x"}},
        assembler, width, output_put, last_output_count, ui_state=ui_state,
    )
    assert assembler._buffer == ""  # buffer flushed
    lines_after_tool_start = len(printed)
    assert lines_after_tool_start > lines_before_tool  # assistant text was rendered

    # Step 3: tool ends → should render tool block immediately
    _dispatch_ws_message(
        {"type": "tool_call_end", "tool_name": "read", "result": "file content", "error": None},
        assembler, width, output_put, last_output_count, ui_state=ui_state,
    )
    lines_after_tool_end = len(printed)
    assert lines_after_tool_end > lines_after_tool_start  # tool block rendered

    # Step 4: more streaming text
    _dispatch_ws_message(
        {"type": "text_delta", "delta": "Here is the result."},
        assembler, width, output_put, last_output_count, ui_state=ui_state,
    )

    # Step 5: agent complete → render remaining buffer
    _dispatch_ws_message(
        {"type": "agent_complete"},
        assembler, width, output_put, last_output_count, ui_state=ui_state,
    )

    # Verify message order in assembler
    assert len(assembler.messages) == 3
    assert assembler.messages[0] == {"role": "assistant", "content": "I'll read the file."}
    assert assembler.messages[1]["role"] == "tool"
    assert "read" in assembler.messages[1]["content"]
    assert assembler.messages[2] == {"role": "assistant", "content": "Here is the result."}

    # Verify rendered output order
    combined = _strip_ansi(" ".join(printed))
    pos_pre = combined.find("read the file")
    pos_tool = combined.find("read")
    pos_post = combined.find("result")
    assert pos_pre >= 0 and pos_tool >= 0 and pos_post >= 0
    assert pos_pre < pos_post


def test_dispatch_multiple_tools_immediate_render():
    """Multiple tools in sequence: each tool block rendered immediately, not batched."""
    assembler = StreamAssembler()
    width = 80
    printed: list[str] = []
    output_put = printed.append
    last_output_count: list[int] = [0]
    ui_state: dict[str, str] = {"phase": "idle"}

    # Tool A
    _dispatch_ws_message(
        {"type": "tool_call_start", "tool_name": "bash", "arguments": {}},
        assembler, width, output_put, last_output_count, ui_state=ui_state,
    )
    _dispatch_ws_message(
        {"type": "tool_call_end", "tool_name": "bash", "result": "ok1", "error": None},
        assembler, width, output_put, last_output_count, ui_state=ui_state,
    )
    lines_after_tool_a = len(printed)
    assert lines_after_tool_a >= 1  # tool A rendered immediately

    # Tool B
    _dispatch_ws_message(
        {"type": "tool_call_start", "tool_name": "read", "arguments": {"path": "f"}},
        assembler, width, output_put, last_output_count, ui_state=ui_state,
    )
    _dispatch_ws_message(
        {"type": "tool_call_end", "tool_name": "read", "result": "content", "error": None},
        assembler, width, output_put, last_output_count, ui_state=ui_state,
    )
    lines_after_tool_b = len(printed)
    assert lines_after_tool_b > lines_after_tool_a  # tool B rendered immediately

    # Agent complete (no remaining buffer)
    _dispatch_ws_message(
        {"type": "agent_complete"},
        assembler, width, output_put, last_output_count, ui_state=ui_state,
    )

    assert len(assembler.messages) == 2
    assert last_output_count[0] == 2
```

**Step 22: Run tests to verify they fail**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_run_integration.py::test_dispatch_text_then_tool_then_text_renders_in_order tests/native/test_run_integration.py::test_dispatch_multiple_tools_immediate_render -v`

Expected: FAIL — `_dispatch_ws_message` doesn't pass `width`/`output_put`/`last_output_count` to `handle_tool_call_start`/`handle_tool_call_end`, so no immediate rendering happens.

**Step 23: Update `_dispatch_ws_message`**

In `packages/basket-tui/basket_tui/native/handle/dispatch.py`, replace the `ToolCallStart` branch (lines 217-223) with:

```python
    elif isinstance(parsed, ToolCallStart):
        handle_tool_call_start(
            assembler,
            parsed.tool_name,
            arguments=parsed.arguments,
            ui_state=ui_state,
            width=width,
            output_put=output_put,
            last_output_count=last_output_count,
        )
```

And replace the `ToolCallEnd` branch (lines 224-230) with:

```python
    elif isinstance(parsed, ToolCallEnd):
        handle_tool_call_end(
            assembler,
            parsed.tool_name,
            result=parsed.result,
            error=parsed.error,
            width=width,
            output_put=output_put,
            last_output_count=last_output_count,
        )
```

**Step 24: Run ALL tests to verify everything passes**

Run: `cd packages/basket-tui && poetry run pytest tests/native/ -v`

Expected: ALL PASS

**Important:** The existing integration test `test_dispatch_tool_call_then_agent_complete_prints_tool_block` (lines 39-68) needs to be verified. With the fix, tool block is now rendered at `tool_call_end` (not at `agent_complete`), so the assertion `combined = _strip_ansi(" ".join(printed))` should still contain "bash" or "file1.txt". The `last_output_count` check may need adjustment — read the actual assertion to confirm. If it checks that output happens only after `agent_complete`, update it to reflect that output now happens at `tool_call_end`.

Similarly, `test_dispatch_multiple_tools_then_assistant_in_one_turn` (lines 71-133) should still pass because tool blocks are rendered earlier, and the message order + output order assertions remain valid. But verify: the assertion `assert len(assembler.messages) == 3` at line 116 still holds (2 tool + 1 assistant). The rendered text positions should remain correct since tools render first.

**Step 25: Commit**

```bash
git add packages/basket-tui/basket_tui/native/handle/dispatch.py packages/basket-tui/tests/native/test_run_integration.py
git commit -m "feat(tui): _dispatch_ws_message passes render params to tool handlers"
```

---

### Task 9: Run full test suite and verify no regressions

**Files:**
- No new files; just verification

**Step 26: Run full basket-tui test suite**

Run: `cd packages/basket-tui && poetry run pytest tests/ -v --tb=short`

Expected: ALL PASS. If any existing test fails, it will be because it assumed tool blocks are only rendered at `agent_complete`. Fix by updating the failing assertion to match the new "immediate render" behavior.

**Step 27: Run basket-tui package from root**

Run: `cd /Users/wanglong24/github.com/badlogic/pi-python && poetry run pytest packages/basket-tui/tests/ -v --tb=short`

Expected: ALL PASS

**Step 28: Commit any test fixes if needed**

```bash
git add -u packages/basket-tui/
git commit -m "test(tui): update assertions for immediate tool rendering"
```

Only if Step 26 or 27 required changes. Skip if no fixes needed.

---

### Task 10: Final integration commit

**Step 29: Verify clean working tree**

Run: `git status`

Expected: Clean working tree (nothing to commit)

**Step 30: Tag completion**

No tag needed; just verify all commits are clean:

Run: `git log --oneline -8`

Expected output should show commits for Tasks 2, 4, 6, 7, 8, and optionally 9.

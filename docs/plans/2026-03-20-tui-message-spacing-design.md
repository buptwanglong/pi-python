# TUI Message Block Spacing Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the bug where consecutive message blocks (tool, user, assistant) render with zero visual spacing between them in the TUI.

**Architecture:** Extract a shared `_render_and_output()` helper that appends separator blank lines after each single-message render call. All 3 render sites in `dispatch.py` will use this helper instead of directly calling `render_messages`.

**Tech Stack:** Python 3.12+, Rich library, pytest

---

## Root Cause

`render_messages()` adds 2 blank lines between blocks internally, then `rstrip("\n")` strips trailing newlines. When called with a single message (which happens at all 3 render sites), the trailing blank lines are always the last output — so `rstrip` removes them every time. Messages appear glued together.

## Approach

Instead of batch-rendering (which would require restructuring the immediate-render pattern used by `handle_tool_call_start` and `handle_tool_call_end`), we add a small helper function that appends 1 blank-line separator after each rendered block. This preserves the existing immediate-render architecture while adding consistent spacing.

Why not batch? Because `handle_tool_call_end` renders each tool block **immediately** (not at `agent_complete` time), so we can't batch them — they arrive one at a time.

---

### Task 1: Write failing test for inter-block spacing

**Files:**
- Modify: `packages/basket-tui/tests/native/test_dispatch.py`

**Step 1: Write the failing test**

Add this test at the end of `test_dispatch.py`:

```python
def test_consecutive_tool_blocks_have_spacing_between_them():
    """Two consecutive tool blocks rendered via handle_tool_call_end must have blank-line spacing."""
    assembler, width, out, output_put, last_output_count = _minimal_setup()

    # First tool call
    handle_tool_call_start(assembler, "read", arguments={"path": "/a"})
    handle_tool_call_end(
        assembler, "read", result="content-a", error=None,
        width=width, output_put=output_put, last_output_count=last_output_count,
    )

    # Second tool call
    handle_tool_call_start(assembler, "write", arguments={"path": "/b"})
    handle_tool_call_end(
        assembler, "write", result="ok", error=None,
        width=width, output_put=output_put, last_output_count=last_output_count,
    )

    # There must be at least one empty line between the two tool blocks
    joined = "\n".join(out)
    # Find where first tool result ends and second tool header starts
    idx_content_a = joined.find("content-a")
    idx_write = joined.find("write", idx_content_a + 1 if idx_content_a >= 0 else 0)
    assert idx_content_a >= 0, "First tool result must appear in output"
    assert idx_write > idx_content_a, "Second tool must appear after first"
    between = joined[idx_content_a:idx_write]
    assert "\n\n" in between, (
        f"Expected blank line between consecutive tool blocks, got: {between!r}"
    )
```

**Step 2: Run test to verify it fails**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_dispatch.py::test_consecutive_tool_blocks_have_spacing_between_them -v`
Expected: FAIL with `"Expected blank line between consecutive tool blocks"`

---

### Task 2: Add `_render_and_output` helper with trailing separator

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/handle/dispatch.py`

**Step 1: Add the helper function**

Add this function after the imports (before `handle_text_delta`), around line 27:

```python
def _render_and_output(
    msg: dict[str, Any],
    width: int,
    output_put: Callable[[str], None],
) -> None:
    """Render a single message and output it with a trailing blank-line separator."""
    lines = render_messages([msg], width)
    for line in lines:
        output_put(line)
    # Add blank line separator so consecutive blocks don't appear glued together.
    # render_messages strips trailing newlines via rstrip, so we must add spacing here.
    output_put("")
```

**Step 2: Replace the render call in `handle_tool_call_end` (line 110-112)**

Before:
```python
        msg = assembler.messages[-1]
        for line in render_messages([msg], width):
            output_put(line)
```

After:
```python
        _render_and_output(assembler.messages[-1], width, output_put)
```

**Step 3: Replace the render call in `handle_tool_call_start` (line 78-80)**

Before:
```python
            msg = assembler.messages[-1]
            for line in render_messages([msg], width):
                output_put(line)
```

After:
```python
            _render_and_output(assembler.messages[-1], width, output_put)
```

**Step 4: Replace the render loop in `handle_agent_complete` (lines 149-152)**

Before:
```python
        for m in assembler.messages[start:]:
            lines = render_messages([m], width)
            for line in lines:
                output_put(line)
```

After:
```python
        for m in assembler.messages[start:]:
            _render_and_output(m, width, output_put)
```

**Step 5: Run the failing test — it should now pass**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_dispatch.py::test_consecutive_tool_blocks_have_spacing_between_them -v`
Expected: PASS

---

### Task 3: Run full test suite and fix regressions

**Files:**
- Possibly adjust: `packages/basket-tui/tests/native/test_dispatch.py` (existing tests that count exact `len(out)`)

**Step 1: Run full dispatch tests**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_dispatch.py -v`

**Step 2: Check for assertion failures**

Tests that assert exact `len(out)` values (e.g., `assert len(out) >= 1`) should still pass because the separator adds lines, making output longer.

Tests that assert exact `len(out) == N` may need adjustment if they exist (review output).

**Step 3: Run full package tests**

Run: `cd packages/basket-tui && poetry run pytest -v`
Expected: All tests pass.

**Step 4: Commit**

```bash
git add packages/basket-tui/basket_tui/native/handle/dispatch.py packages/basket-tui/tests/native/test_dispatch.py
git commit -m "fix: add spacing between consecutive message blocks in TUI

Extract _render_and_output() helper that appends a blank-line separator
after each rendered message block. Fixes the visual bug where tool blocks,
user blocks, and assistant blocks appeared glued together."
```

---

### Task 4: Manual verification

**Step 1: Launch TUI and trigger multi-tool output**

Run: `cd packages/basket-assistant && poetry run basket tui`

Send a prompt that triggers multiple tool calls (e.g., "read pyproject.toml and then list the files").

**Step 2: Verify spacing**

Confirm that:
- Each tool block (green background) has visible spacing between it and the next block
- Assistant text has spacing from surrounding tool blocks
- User message blocks have spacing from assistant responses
- No excessive spacing (just 1 blank line between blocks)

---

## Summary of Changes

| File | Change |
|------|--------|
| `dispatch.py` | Add `_render_and_output()` helper (6 lines) |
| `dispatch.py` | Replace 3 render sites to use the helper (3 x 1-line change) |
| `test_dispatch.py` | Add 1 new test for inter-block spacing |
| Total | ~10 lines changed, 1 test added |

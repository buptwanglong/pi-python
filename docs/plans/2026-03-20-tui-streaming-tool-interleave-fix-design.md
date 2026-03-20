# TUI Streaming + Tool Call Interleave Fix Design

**Date:** 2026-03-20
**Status:** Approved

## Problem

When LLM streaming and tool calls happen simultaneously in TUI mode, messages display incorrectly:

1. **Text interleaving**: Streaming preview (plain text) and committed tool blocks (Rich ANSI) appear on screen together, causing visual overlap
2. **Layout corruption**: `agent_complete` batch-renders all messages at once, mixing tool results with assistant text in wrong order

### Root Cause

Two bugs in the event dispatch pipeline:

**Bug 1 — Phase conflict**: `handle_text_delta` sets `phase = "streaming"` even during tool execution. This causes `get_body_lines()` to append streaming preview alongside committed tool blocks.

**Bug 2 — Delayed rendering**: `handle_tool_call_end` appends to `assembler.messages` but does NOT call `output_put`. All rendering waits for `agent_complete`, which batch-renders everything. During the wait, `_buffer` accumulates text that overlaps with tool messages.

## Solution: Immediate Flush and Render (Option A)

Render each message segment immediately as state transitions occur, instead of batching at turn end.

### Timeline with fix

```
TextDelta("I'll read the file...")
  → _buffer = "I'll read the file..."
  → phase = "streaming"
  → streaming preview visible

ToolCallStart("read", {...})
  → flush_buffer() → commit "I'll read the file..." as assistant msg → render immediately
  → phase = "tool_running"
  → streaming preview cleared (buffer empty)

ToolCallEnd("read", result="file content")
  → append tool msg → render tool block immediately
  → last_output_count synced

TextDelta("Here's what I found...")
  → _buffer = "Here's what I found..."
  → phase = "streaming"
  → streaming preview visible

AgentComplete
  → flush remaining buffer → render final assistant msg
  → phase = "idle"
```

## Changes

### 1. StreamAssembler (`stream.py`)

Add `flush_buffer()` method:

```python
def flush_buffer(self) -> bool:
    """Commit current _buffer as assistant message if non-empty. Returns True if committed."""
    if not self._buffer:
        return False
    self.messages.append({"role": "assistant", "content": self._buffer})
    self._buffer = ""
    return True
```

`agent_complete()` unchanged (still calls internal flush + clears thinking buffer).

### 2. Dispatch handlers (`dispatch.py`)

**`handle_tool_call_start`** — new signature adds `width`, `output_put`, `last_output_count`:

```python
def handle_tool_call_start(assembler, tool_name, arguments, ui_state,
                            width, output_put, last_output_count):
    # Flush streaming buffer BEFORE tool starts
    if assembler.flush_buffer():
        msg = assembler.messages[-1]
        for line in render_messages([msg], width):
            output_put(line)
        last_output_count[0] = len(assembler.messages)

    ui_state["phase"] = "tool_running"
    assembler.tool_call_start(tool_name, arguments)
```

**`handle_tool_call_end`** — new signature adds `width`, `output_put`, `last_output_count`:

```python
def handle_tool_call_end(assembler, tool_name, result, error,
                          width, output_put, last_output_count):
    assembler.tool_call_end(tool_name, result=result, error=error)

    # Render tool block immediately
    msg = assembler.messages[-1]
    for line in render_messages([msg], width):
        output_put(line)
    last_output_count[0] = len(assembler.messages)
```

**`handle_agent_complete`** — unchanged logic, but now only renders remaining buffer (tool messages already rendered).

### 3. Handler factory (`handlers.py`)

Update lambdas for `on_tool_call_start` and `on_tool_call_end` to pass `width`, `output_put`, `last_output_count`.

### 4. `get_body_lines` (`run.py`)

No change needed. The `phase == "streaming"` guard already prevents tool_running phase from showing preview. With flush_buffer, the buffer is empty when phase switches to tool_running.

## Files Modified

| File | Change |
|------|--------|
| `stream.py` | Add `flush_buffer()` method |
| `dispatch.py` | Update `handle_tool_call_start` and `handle_tool_call_end` signatures and logic |
| `handlers.py` | Update lambda closures for new parameters |

## Testing

| Test | Description |
|------|-------------|
| `test_flush_buffer_commits_and_clears` | flush_buffer commits non-empty buffer, returns True; no-op when empty |
| `test_flush_buffer_empty_noop` | flush_buffer on empty buffer returns False, no message added |
| `test_tool_call_start_flushes_buffer` | tool_call_start triggers flush, assistant msg rendered before tool |
| `test_tool_call_end_immediate_render` | tool_call_end renders tool block immediately via output_put |
| `test_interleave_text_tool_text` | Full scenario: text → tool → text, messages appear in correct order |
| `test_multiple_tools_sequential` | Multiple tool calls in sequence, each rendered immediately |

## Invariants

- `assembler.messages` list is always in chronological order
- `last_output_count` always equals number of rendered messages
- Streaming preview only visible when `phase == "streaming"` AND `_buffer` is non-empty
- No ANSI-rendered content mixes with plain-text streaming preview

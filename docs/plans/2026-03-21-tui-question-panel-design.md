# TUI Question Panel Design

**Date:** 2026-03-21
**Status:** Approved

## Overview

Add interactive question display to the TUI for `ask_user_question` tool calls. Questions appear in the conversation flow (as assistant text), while a dedicated question panel replaces the input row at the bottom for option selection. Tool blocks for `ask_user_question` and `todo_write` are hidden from the conversation stream.

## Requirements

1. **Question in conversation flow**: The question text is part of the assistant's streaming text — displayed normally in the body.
2. **Bottom question panel**: When a question is active, the input row (❯ + buffer) is replaced by an interactive option selector.
3. **↑/↓ + Enter interaction**: User navigates options with arrow keys, confirms with Enter.
4. **Free text fallback**: Last option is always "自由输入..." — selecting it reveals the input box for arbitrary text.
5. **Tool message suppression**: `ask_user_question` and `todo_write` tool blocks are NOT rendered in the conversation stream (green blocks hidden).
6. **Todo panel unchanged**: Existing todo_panel behavior is preserved.

## Architecture

### Layout (with question active)

```
┌─ header (2 lines) ──────────────────────────┐
│  Body (conversation, scrollable)              │
│  ... assistant text including question ...     │
├─ todo_panel (0-8 lines, optional) ───────────┤
├─ footer (1 line) ────────────────────────────┤
├─ separator ──────────────────────────────────┤
│  ❯ Option A            ← highlighted         │
│    Option B                                   │
│    Option C                                   │
│    自由输入...                                 │
└──────────────────────────────────────────────┘
```

### Layout (no question — normal mode)

```
├─ footer (1 line) ────────────────────────────┤
├─ separator ──────────────────────────────────┤
│  ❯ [input buffer]                             │
└──────────────────────────────────────────────┘
```

## Components

### 1. `question_panel.py` (new module)

**State model:**
```python
question_state: dict = {
    "active": False,
    "tool_call_id": "",
    "question": "",
    "options": [],      # list[str]
    "selected": 0,      # 0-based index; len(options) = free text
}
```

**Functions:**
- `format_question_panel(state: dict, width: int) -> str` — Render ANSI option list
- `question_panel_height(state: dict) -> int` — Height (0 when inactive, else options+1 for free text)

**Rendering rules:**
- Selected item: `❯ Option text` with bright cyan color
- Unselected: `  Option text` with default color
- Free text slot: `  自由输入...` with dim gray
- When free text is selected and user is typing: show input buffer inline

### 2. Protocol: `AskUserQuestion` message type

Add to `basket-protocol/inbound.py`:
```python
class AskUserQuestion(InboundMessage):
    type: str = "ask_user_question"
    tool_call_id: str = ""
    question: str = ""
    options: list[str] = []
```

Register in `parse_inbound()` dispatcher.

### 3. `GatewayHandlers` extension

Add to `connection/types.py`:
```python
on_ask_user_question: Callable[[AskUserQuestion], None]
```

Add dispatch in `connection/client.py`:
```python
elif isinstance(parsed, AskUserQuestion):
    h = self._handlers.get("on_ask_user_question")
    if h:
        h(parsed)
```

### 4. Layout changes (`layout.py`)

New parameters to `build_layout()`:
- `get_question_lines: Callable[[], str] | None`
- `get_question_height: Callable[[], int] | None`
- `is_question_active: Callable[[], bool] | None`

Bottom rows become conditional:
```python
from prompt_toolkit.layout.containers import ConditionalContainer
from prompt_toolkit.filters import Condition

has_question = Condition(lambda: is_question_active() if is_question_active else False)

# Input row: visible when NO question
input_row = ConditionalContainer(
    VSplit([prompt_window, input_window]),
    filter=~has_question,
)

# Question panel: visible when question active
question_row = ConditionalContainer(
    question_window,
    filter=has_question,
)
```

### 5. Key bindings (`run.py`)

When question is active:
- **↑**: `question_state["selected"] = max(0, selected - 1)`
- **↓**: `question_state["selected"] = min(max_idx, selected + 1)`
- **Enter**:
  - If selected < len(options): send `options[selected]` via `conn.send_message`
  - If selected == len(options) (free text): show input buffer, wait for text + Enter
  - Clear question_state (active=False), restore input row
- **Escape**: Clear question (treat as dismiss, let agent continue)

Normal mode: existing behavior unchanged.

### 6. Tool message suppression (`dispatch.py`)

In `handle_tool_call_start`:
```python
# Skip flush+render for suppressed tools
if tool_name in ("ask_user_question", "todo_write"):
    assembler.tool_call_start(tool_name, arguments)
    return  # no render
```

In `handle_tool_call_end`:
```python
# Skip render for suppressed tools
if tool_name in ("ask_user_question", "todo_write"):
    assembler.tool_call_end(tool_name, result=result, error=error)
    # DO trigger question state update for ask_user_question
    return  # no render
```

### 7. Handler wiring (`handlers.py`)

```python
def handle_ask_user_question(question_state, event):
    question_state["active"] = True
    question_state["tool_call_id"] = event.tool_call_id
    question_state["question"] = event.question
    question_state["options"] = list(event.options)
    question_state["selected"] = 0
```

### 8. Answer submission

When user selects an option or enters free text:
```python
answer = options[selected] if selected < len(options) else free_text
# Send as JSON for gateway to match tool_call_id
payload = json.dumps({
    "answer": answer,
    "tool_call_id": question_state["tool_call_id"],
})
await conn.send_message(payload)
# Reset state
question_state["active"] = False
question_state["tool_call_id"] = ""
question_state["options"] = []
question_state["selected"] = 0
```

## Data Flow

```
Gateway sends → {"type": "ask_user_question", tool_call_id, question, options}
  → client.py._dispatch() → on_ask_user_question handler
  → question_state updated (active=True, options=[...], selected=0)
  → app.invalidate() → question_panel renders, input_row hides
  → User ↑/↓ → selected changes → invalidate → re-render
  → User Enter → send_message(JSON answer) → question_state reset → input_row restores
```

## Error Handling

- **Empty options**: Show only "自由输入..." row; user must type free text
- **Agent abort**: Clear question_state, restore input row
- **Disconnect/reconnect**: question_state preserved (pending_asks persist server-side)
- **Multiple questions**: Only latest question shown (LIFO; gateway sends one at a time)

## Test Plan

| Test file | Coverage |
|-----------|----------|
| `test_question_panel.py` | Rendering, height, selection highlight, truncation, empty options |
| `test_dispatch.py` | ask_user_question + todo_write tool blocks not rendered |
| `test_handlers.py` | on_ask_user_question handler updates state |
| `test_client.py` | AskUserQuestion message dispatched to handler |
| Integration | Panel activate → select → confirm → state reset → input restore |

## Files to Create/Modify

### New files:
- `packages/basket-tui/basket_tui/native/ui/question_panel.py`
- `packages/basket-tui/tests/native/test_question_panel.py`

### Modified files:
- `packages/basket-protocol/basket_protocol/inbound.py` — Add AskUserQuestion type
- `packages/basket-tui/basket_tui/native/connection/types.py` — Add handler type
- `packages/basket-tui/basket_tui/native/connection/client.py` — Dispatch AskUserQuestion
- `packages/basket-tui/basket_tui/native/handle/dispatch.py` — Suppress tool rendering
- `packages/basket-tui/basket_tui/native/handle/handlers.py` — Wire ask handler
- `packages/basket-tui/basket_tui/native/ui/layout.py` — Conditional input/question
- `packages/basket-tui/basket_tui/native/run.py` — Key bindings, question state, wiring
- `packages/basket-tui/tests/native/test_dispatch.py` — Suppression tests
- `packages/basket-tui/tests/native/test_handlers.py` — Handler tests

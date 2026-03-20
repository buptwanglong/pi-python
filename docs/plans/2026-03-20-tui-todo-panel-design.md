# TUI TODO Panel Design

**Date:** 2026-03-20
**Status:** Approved

## Problem

`todo_write` tool stores tasks as JSON but the TUI has no visual rendering. Users cannot see task progress during agent execution.

## Solution

Add a fixed TODO panel in the TUI layout, positioned between the conversation body and input row. The panel appears only when active tasks exist and disappears when all tasks are completed.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | Layout-level independent Panel | Clean separation; height-based show/hide; consistent with existing HSplit pattern |
| Visibility | Only when active tasks exist | Minimal visual noise |
| Position | Above input, below conversation | Natural eye focus near input area |
| Height | Fixed max (8 lines) | Prevents conversation area collapse |
| Data source | New `todo_update` WebSocket event | Real-time updates, no polling I/O |
| Payload | Full snapshot (not incremental) | Simple, reliable; todo lists are small (<20 items) |

## Protocol

New event type pushed after `todo_write` execution:

```python
class TodoUpdate(TypedDict):
    todos: list[TodoItem]

class TodoItem(TypedDict):
    id: str
    content: str
    status: Literal["pending", "in_progress", "completed", "cancelled"]
```

## Layout

```
HSplit [
  banner,
  doctor_panel,
  separator,
  header_chrome,
  body_window,        # scrollable, flex weight
  todo_panel,         # NEW: fixed height, dynamic show/hide
  separator,
  input_row
]
```

## Rendering

```
  ⎿  ◼ Explore project context         # in_progress: solid, bright
     ◻ Ask clarifying questions         # pending: hollow, dim
     ◻ Propose approaches
     ✓ Write design doc                 # completed: checkmark, dim
     +2 more completed                  # overflow folding
```

Icon mapping:

| Status | Icon | Color |
|--------|------|-------|
| `in_progress` | `◼` | bright white / cyan |
| `pending` | `◻` | gray (dim) |
| `completed` | `✓` | green (dim) |
| `cancelled` | `✗` | red (dim) |

## Height Logic

```python
MAX_PANEL_LINES = 8

def get_todo_panel_height() -> int:
    active = [t for t in todo_state if t["status"] in ("pending", "in_progress")]
    if not active:
        return 0
    return min(len(active) + 1, MAX_PANEL_LINES)
```

## Sort Order

1. `in_progress` first (most visible)
2. `pending` second
3. `completed` / `cancelled` last (folded when space insufficient)
4. Within same status: preserve original id order

## Data Flow

```
Agent calls todo_write
  → basket-assistant saves JSON + emits todo_update event
  → Gateway pushes {"type": "todo_update", "todos": [...]} via WebSocket
  → TUI dispatch.py: handle_todo_update() updates todo_state
  → app.invalidate() triggers todo_panel re-render
```

## Files to Change

| File | Change |
|------|--------|
| `basket-tui/native/ui/todo_panel.py` | **New**: render logic, ANSI formatting |
| `basket-tui/native/layout.py` | Insert todo_panel in HSplit |
| `basket-tui/native/run.py` | Add `todo_state`, `handle_todo_update`, wire invalidation |
| `basket-tui/native/connection/types.py` | Add `on_todo_update` to `GatewayHandlers` |
| `basket-tui/native/pipeline/dispatch.py` | Handle `todo_update` message type |
| `basket-gateway/` | Push todo_update event after todo_write |
| `basket-assistant/tools/todo_write.py` | Emit todo_update event after execution |

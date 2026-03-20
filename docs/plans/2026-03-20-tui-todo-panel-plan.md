# TUI TODO Panel Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a fixed TODO panel in the TUI that shows real-time task progress when the agent calls `todo_write`.

**Architecture:** The gateway already emits `{"type": "todos", "todos": [...]}` after `todo_write` (see `gateway.py:184-185`). We add a `TodoUpdate` inbound message type in `basket-protocol`, wire it through the TUI connection/dispatch/handler layers, and render it in a new `todo_panel.py` widget inserted into the `HSplit` layout between body and footer.

**Tech Stack:** Python 3.12+, prompt_toolkit (FormattedTextControl, HSplit, Window, Dimension), basket-protocol (frozen dataclasses), ANSI escape codes.

---

### Task 1: Add `TodoUpdate` to basket-protocol inbound types

**Files:**
- Modify: `packages/basket-protocol/basket_protocol/inbound.py`
- Modify: `packages/basket-protocol/basket_protocol/__init__.py`
- Test: `packages/basket-protocol/tests/test_inbound.py`

**Step 1: Write the failing test**

Add to `packages/basket-protocol/tests/test_inbound.py`:

```python
def test_parse_inbound_todo_update() -> None:
    """parse_inbound({'type': 'todos', 'todos': [...]}) returns TodoUpdate."""
    msg = parse_inbound({
        "type": "todos",
        "todos": [
            {"id": "1", "content": "Explore context", "status": "completed"},
            {"id": "2", "content": "Ask questions", "status": "in_progress"},
            {"id": "3", "content": "Propose approaches", "status": "pending"},
        ],
    })
    assert isinstance(msg, TodoUpdate)
    assert len(msg.todos) == 3
    assert msg.todos[0] == {"id": "1", "content": "Explore context", "status": "completed"}
    assert msg.todos[1]["status"] == "in_progress"
    assert msg.todos[2]["status"] == "pending"


def test_parse_inbound_todo_update_empty() -> None:
    """parse_inbound({'type': 'todos', 'todos': []}) returns TodoUpdate with empty list."""
    msg = parse_inbound({"type": "todos", "todos": []})
    assert isinstance(msg, TodoUpdate)
    assert msg.todos == ()


def test_inbound_to_dict_todo_update_roundtrip() -> None:
    """inbound_to_dict(TodoUpdate) returns wire dict; parse_inbound roundtrips."""
    msg = TodoUpdate(todos=(
        {"id": "1", "content": "Task A", "status": "pending"},
    ))
    d = inbound_to_dict(msg)
    assert d == {"type": "todos", "todos": [{"id": "1", "content": "Task A", "status": "pending"}]}
    parsed = parse_inbound(d)
    assert isinstance(parsed, TodoUpdate)
    assert parsed.todos == msg.todos
```

**Step 2: Run test to verify it fails**

Run: `cd packages/basket-protocol && poetry run pytest tests/test_inbound.py::test_parse_inbound_todo_update -v`
Expected: FAIL with `ImportError: cannot import name 'TodoUpdate'`

**Step 3: Write minimal implementation**

In `packages/basket-protocol/basket_protocol/inbound.py`, add the dataclass after `System`:

```python
@dataclass(frozen=True)
class TodoUpdate:
    """Todo list snapshot (full replacement)."""

    todos: tuple[dict[str, Any], ...] = ()
```

> Note: Use `tuple` (not `list`) for frozen dataclass immutability.

In `parse_inbound`, add before the final `return Unknown(...)`:

```python
    if typ == "todos":
        raw_todos = data.get("todos") or []
        return TodoUpdate(todos=tuple(raw_todos))
```

In `inbound_to_dict`, add before the final `raise TypeError`:

```python
    if isinstance(msg, TodoUpdate):
        return {"type": "todos", "todos": list(msg.todos)}
```

Update the `InboundMessage` Union to include `TodoUpdate`:

```python
InboundMessage = Union[
    TextDelta,
    ThinkingDelta,
    ToolCallStart,
    ToolCallEnd,
    AgentComplete,
    AgentError,
    SessionSwitched,
    AgentSwitched,
    AgentAborted,
    System,
    TodoUpdate,
    Unknown,
]
```

In `packages/basket-protocol/basket_protocol/__init__.py`, add `TodoUpdate` to the imports from `.inbound` and to `__all__`.

**Step 4: Run tests to verify they pass**

Run: `cd packages/basket-protocol && poetry run pytest tests/test_inbound.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/basket-protocol/basket_protocol/inbound.py packages/basket-protocol/basket_protocol/__init__.py packages/basket-protocol/tests/test_inbound.py
git commit -m "feat(protocol): add TodoUpdate inbound message type"
```

---

### Task 2: Create `todo_panel.py` — rendering logic

**Files:**
- Create: `packages/basket-tui/basket_tui/native/ui/todo_panel.py`
- Test: `packages/basket-tui/tests/native/test_todo_panel.py`

**Step 1: Write the failing tests**

Create `packages/basket-tui/tests/native/test_todo_panel.py`:

```python
"""Tests for TUI todo panel rendering."""

import re

import pytest

from basket_tui.native.ui.todo_panel import (
    MAX_PANEL_LINES,
    format_todo_panel,
    todo_panel_height,
)


def _strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m|\x1b\]8;;.*?\x1b\\", "", s)


# --- todo_panel_height ---

def test_todo_panel_height_empty_returns_zero():
    """No todos → height 0 (panel hidden)."""
    assert todo_panel_height([]) == 0


def test_todo_panel_height_all_completed_returns_zero():
    """All completed/cancelled → height 0 (panel hidden)."""
    todos = [
        {"id": "1", "content": "A", "status": "completed"},
        {"id": "2", "content": "B", "status": "cancelled"},
    ]
    assert todo_panel_height(todos) == 0


def test_todo_panel_height_with_active_tasks():
    """Active tasks → height = min(active_count + 1, MAX)."""
    todos = [
        {"id": "1", "content": "A", "status": "in_progress"},
        {"id": "2", "content": "B", "status": "pending"},
        {"id": "3", "content": "C", "status": "completed"},
    ]
    # 2 active + 1 separator line = 3
    assert todo_panel_height(todos) == 3


def test_todo_panel_height_capped_at_max():
    """Many active tasks → capped at MAX_PANEL_LINES."""
    todos = [{"id": str(i), "content": f"Task {i}", "status": "pending"} for i in range(20)]
    assert todo_panel_height(todos) == MAX_PANEL_LINES


# --- format_todo_panel ---

def test_format_todo_panel_empty_returns_empty_string():
    """No todos → empty string."""
    assert format_todo_panel([], 80) == ""


def test_format_todo_panel_in_progress_shows_solid_square():
    """in_progress items display ◼ icon."""
    todos = [{"id": "1", "content": "Explore context", "status": "in_progress"}]
    result = _strip_ansi(format_todo_panel(todos, 80))
    assert "◼" in result
    assert "Explore context" in result


def test_format_todo_panel_pending_shows_hollow_square():
    """pending items display ◻ icon."""
    todos = [{"id": "1", "content": "Ask questions", "status": "pending"}]
    result = _strip_ansi(format_todo_panel(todos, 80))
    assert "◻" in result
    assert "Ask questions" in result


def test_format_todo_panel_sort_order():
    """in_progress first, then pending, then completed."""
    todos = [
        {"id": "1", "content": "AAA-pending", "status": "pending"},
        {"id": "2", "content": "BBB-progress", "status": "in_progress"},
        {"id": "3", "content": "CCC-done", "status": "completed"},
    ]
    result = _strip_ansi(format_todo_panel(todos, 80))
    idx_progress = result.index("BBB-progress")
    idx_pending = result.index("AAA-pending")
    assert idx_progress < idx_pending, "in_progress should come before pending"


def test_format_todo_panel_overflow_shows_count():
    """When items exceed MAX_PANEL_LINES, overflow count is shown."""
    todos = [{"id": str(i), "content": f"Task {i}", "status": "pending"} for i in range(20)]
    result = _strip_ansi(format_todo_panel(todos, 80))
    assert "more" in result.lower()


def test_format_todo_panel_all_completed_returns_empty():
    """All completed → empty (panel hidden)."""
    todos = [
        {"id": "1", "content": "Done", "status": "completed"},
        {"id": "2", "content": "Cancelled", "status": "cancelled"},
    ]
    assert format_todo_panel(todos, 80) == ""


def test_format_todo_panel_truncates_long_content():
    """Content longer than available width is truncated with ellipsis."""
    todos = [{"id": "1", "content": "A" * 200, "status": "pending"}]
    result = _strip_ansi(format_todo_panel(todos, 60))
    assert "…" in result
    # Each line should not exceed width
    for line in result.split("\n"):
        assert len(line) <= 60
```

**Step 2: Run test to verify it fails**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_todo_panel.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'basket_tui.native.ui.todo_panel'`

**Step 3: Write minimal implementation**

Create `packages/basket-tui/basket_tui/native/ui/todo_panel.py`:

```python
"""
Todo panel rendering for terminal-native TUI.

Renders a fixed-height panel showing task progress with status icons and ANSI colors.
Panel is hidden (height 0) when no active tasks exist.
"""

from __future__ import annotations

from typing import Any

# Maximum panel height in lines (including separator)
MAX_PANEL_LINES = 8

# Status → (icon, ANSI color code)
_STATUS_STYLE: dict[str, tuple[str, str]] = {
    "in_progress": ("◼", "\x1b[38;2;100;200;255m"),  # bright cyan
    "pending":     ("◻", "\x1b[38;2;123;127;135m"),   # muted gray
    "completed":   ("✓", "\x1b[38;2;80;160;80m"),     # dim green
    "cancelled":   ("✗", "\x1b[38;2;200;80;80m"),     # dim red
}
_ANSI_RESET = "\x1b[0m"
_ANSI_DIM = "\x1b[38;2;123;127;135m"

# Sort priority: lower = higher priority (shown first)
_STATUS_ORDER: dict[str, int] = {
    "in_progress": 0,
    "pending": 1,
    "completed": 2,
    "cancelled": 3,
}


def todo_panel_height(todos: list[dict[str, Any]]) -> int:
    """Return the panel height in lines. 0 means hidden (no active tasks)."""
    active = [t for t in todos if t.get("status") in ("pending", "in_progress")]
    if not active:
        return 0
    # +1 for top separator line
    return min(len(active) + 1, MAX_PANEL_LINES)


def _sort_todos(todos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort: in_progress first, pending second, completed/cancelled last. Stable within group."""
    return sorted(todos, key=lambda t: _STATUS_ORDER.get(t.get("status", "pending"), 99))


def format_todo_panel(todos: list[dict[str, Any]], width: int) -> str:
    """
    Render the todo panel as a single ANSI string (lines joined by newline).

    Returns empty string when no active tasks (panel should be hidden).
    """
    active = [t for t in todos if t.get("status") in ("pending", "in_progress")]
    if not active:
        return ""

    sorted_todos = _sort_todos(todos)
    # Filter: show active items first; completed only if space allows
    active_sorted = [t for t in sorted_todos if t.get("status") in ("pending", "in_progress")]
    done_sorted = [t for t in sorted_todos if t.get("status") in ("completed", "cancelled")]

    # Available lines: MAX_PANEL_LINES - 1 (separator)
    max_items = MAX_PANEL_LINES - 1
    show_items = active_sorted[:max_items]
    remaining = len(active_sorted) - len(show_items) + len(done_sorted)

    lines: list[str] = []

    # Top separator
    sep_char = "─"
    lines.append(f"{_ANSI_DIM}{sep_char * width}{_ANSI_RESET}")

    # Prefix for indentation (matching the design mockup)
    prefix = "     "
    # Max content width = width - prefix - icon - space - padding
    max_content_len = width - len(prefix) - 4  # "◼ " = 2 chars + some margin

    for item in show_items:
        status = item.get("status", "pending")
        icon, color = _STATUS_STYLE.get(status, ("?", _ANSI_DIM))
        content = item.get("content", "")
        if max_content_len > 0 and len(content) > max_content_len:
            content = content[: max_content_len - 1] + "…"
        lines.append(f"{color}{prefix}{icon} {content}{_ANSI_RESET}")

    # Overflow indicator
    if remaining > 0:
        lines.append(f"{_ANSI_DIM}{prefix}  +{remaining} more{_ANSI_RESET}")

    return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_todo_panel.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/ui/todo_panel.py packages/basket-tui/tests/native/test_todo_panel.py
git commit -m "feat(tui): add todo_panel rendering module with tests"
```

---

### Task 3: Add `on_todo_update` to `GatewayHandlers` and wire dispatch

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/connection/types.py`
- Modify: `packages/basket-tui/basket_tui/native/handle/dispatch.py`
- Modify: `packages/basket-tui/basket_tui/native/handle/handlers.py`
- Modify: `packages/basket-tui/basket_tui/native/connection/client.py`
- Test: `packages/basket-tui/tests/native/test_dispatch.py`
- Test: `packages/basket-tui/tests/native/test_handlers.py`

**Step 1: Write the failing tests**

Add to `packages/basket-tui/tests/native/test_dispatch.py`:

```python
from basket_tui.native.handle.dispatch import handle_todo_update


def test_handle_todo_update_stores_todos():
    """handle_todo_update stores the todo list snapshot."""
    todo_state: list[dict] = []
    todos = [
        {"id": "1", "content": "Task A", "status": "pending"},
        {"id": "2", "content": "Task B", "status": "in_progress"},
    ]
    handle_todo_update(todo_state, todos)
    assert len(todo_state) == 2
    assert todo_state[0]["content"] == "Task A"
    assert todo_state[1]["status"] == "in_progress"


def test_handle_todo_update_replaces_previous():
    """handle_todo_update replaces previous state (snapshot semantics)."""
    todo_state: list[dict] = [{"id": "old", "content": "Old", "status": "completed"}]
    handle_todo_update(todo_state, [{"id": "new", "content": "New", "status": "pending"}])
    assert len(todo_state) == 1
    assert todo_state[0]["id"] == "new"


def test_handle_todo_update_empty_clears_state():
    """handle_todo_update with empty list clears state."""
    todo_state: list[dict] = [{"id": "1", "content": "X", "status": "pending"}]
    handle_todo_update(todo_state, [])
    assert len(todo_state) == 0
```

Add to `packages/basket-tui/tests/native/test_handlers.py`:

```python
from basket_protocol import TodoUpdate


def test_make_handlers_on_todo_update_stores_state() -> None:
    """on_todo_update handler stores todos in closed-over todo_state."""
    assembler = StreamAssembler()
    width = 80
    lines_out: list[str] = []
    last_output_count = [0]
    header_state: dict[str, str] = {}
    ui_state: dict[str, str] = {}
    todo_state: list[dict] = []

    handlers = make_handlers(
        assembler, width, lines_out.append, last_output_count,
        header_state, ui_state, todo_state=todo_state,
    )

    assert "on_todo_update" in handlers
    handlers["on_todo_update"](TodoUpdate(todos=(
        {"id": "1", "content": "Test", "status": "pending"},
    )))
    assert len(todo_state) == 1
    assert todo_state[0]["content"] == "Test"
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_dispatch.py::test_handle_todo_update_stores_todos tests/native/test_handlers.py::test_make_handlers_on_todo_update_stores_state -v`
Expected: FAIL with `ImportError`

**Step 3: Implement**

**3a. `connection/types.py`** — add `on_todo_update` to GatewayHandlers:

Add import:
```python
from basket_protocol import (
    ...,
    TodoUpdate,
)
```

Add to `GatewayHandlers` TypedDict:
```python
    on_todo_update: Callable[[TodoUpdate], None]
```

**3b. `handle/dispatch.py`** — add `handle_todo_update`:

```python
def handle_todo_update(
    todo_state: list[dict[str, Any]],
    todos: list[dict[str, Any]],
) -> None:
    """Handle todo_update: replace todo_state with new snapshot."""
    todo_state.clear()
    todo_state.extend(todos)
    logger.info("Todo state updated", extra={"count": len(todos)})
```

Also add to `_dispatch_ws_message`: import `TodoUpdate` from basket_protocol, then add an elif branch:

```python
    elif isinstance(parsed, TodoUpdate):
        # handled by on_todo_update in handlers, not here
        pass
```

> Note: `_dispatch_ws_message` is NOT used — the client.py `_dispatch` calls handlers directly. But we keep it consistent if anyone uses it.

**3c. `handle/handlers.py`** — add `on_todo_update` to make_handlers:

Add parameter `todo_state: list[dict[str, Any]] | None = None` to `make_handlers`.

Import `handle_todo_update` from dispatch.

Add to handlers dict:
```python
    if todo_state is not None:
        from .dispatch import handle_todo_update
        handlers["on_todo_update"] = lambda event: handle_todo_update(
            todo_state, list(event.todos)
        )
```

**3d. `connection/client.py`** — add `TodoUpdate` dispatch:

Import `TodoUpdate` from basket_protocol.

Add elif in `_dispatch` method:
```python
            elif isinstance(parsed, TodoUpdate):
                h = self._handlers.get("on_todo_update")
                if h:
                    h(parsed)
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_dispatch.py tests/native/test_handlers.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/connection/types.py \
      packages/basket-tui/basket_tui/native/handle/dispatch.py \
      packages/basket-tui/basket_tui/native/handle/handlers.py \
      packages/basket-tui/basket_tui/native/connection/client.py \
      packages/basket-tui/tests/native/test_dispatch.py \
      packages/basket-tui/tests/native/test_handlers.py
git commit -m "feat(tui): wire todo_update through connection, dispatch, and handlers"
```

---

### Task 4: Integrate TodoPanel into layout.py

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/ui/layout.py`
- Modify: `packages/basket-tui/basket_tui/native/ui/__init__.py`
- Test: `packages/basket-tui/tests/native/test_layout.py`

**Step 1: Write the failing test**

Add to `packages/basket-tui/tests/native/test_layout.py`:

```python
def test_build_layout_with_todo_panel():
    """build_layout with get_todo_lines returns layout containing todo panel."""
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.data_structures import Point

    input_buffer = Buffer(name="input", multiline=False)

    def get_body_lines():
        return ["line1"]

    def get_todo_lines():
        return "     ◼ Task in progress"

    layout = build_layout(
        width=80,
        base_url="http://localhost:7682",
        header_state={"agent": "default", "session": "s1"},
        ui_state={"phase": "idle", "connection": "connected"},
        get_body_lines=get_body_lines,
        input_buffer=input_buffer,
        footer_line=lambda: "footer",
        get_vertical_scroll=lambda w: 0,
        get_cursor_position=lambda: Point(0, 0),
        on_body_mouse_scroll=lambda w: None,
        get_todo_lines=get_todo_lines,
        get_todo_height=lambda: 2,
    )
    assert layout is not None
```

**Step 2: Run test to verify it fails**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_layout.py::test_build_layout_with_todo_panel -v`
Expected: FAIL with `TypeError: build_layout() got an unexpected keyword argument 'get_todo_lines'`

**Step 3: Implement**

Modify `build_layout` in `packages/basket-tui/basket_tui/native/ui/layout.py`:

Add two new optional keyword parameters:
```python
    get_todo_lines: Callable[[], str] | None = None,
    get_todo_height: Callable[[], int] | None = None,
```

After `body_window` and before `rows.extend([...])`, insert the todo panel Window conditionally:

```python
    todo_window = None
    if get_todo_lines is not None and get_todo_height is not None:
        todo_control = FormattedTextControl(
            text=lambda: ANSI(get_todo_lines() or ""),
            focusable=False,
        )
        todo_window = Window(
            content=todo_control,
            height=lambda: get_todo_height(),
        )
```

In `rows.extend([ ... ])`, insert `todo_window` between `body_window` and `footer`:

```python
    rows_to_add = [
        Window(height=2, content=header_control),
        body_window,
    ]
    if todo_window is not None:
        rows_to_add.append(todo_window)
    rows_to_add.extend([
        Window(height=1, content=footer_control),
        Window(height=1, content=sep_control),
        VSplit([
            Window(width=3, content=FormattedTextControl("❯ "), dont_extend_width=True),
            Window(content=input_control),
        ]),
    ])
    rows.extend(rows_to_add)
```

Update `__init__.py` — no new exports needed (build_layout already exported).

**Step 4: Run tests to verify they pass**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_layout.py -v`
Expected: ALL PASS (both old and new tests)

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/ui/layout.py packages/basket-tui/tests/native/test_layout.py
git commit -m "feat(tui): add todo panel slot to HSplit layout"
```

---

### Task 5: Wire everything in `run.py`

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1: Write the failing test (integration)**

Add to `packages/basket-tui/tests/native/test_run_integration.py` (or create if needed — check existing file first):

```python
def test_run_tui_todo_state_wired():
    """Verify that todo_state is created and passed to make_handlers."""
    # This is a smoke test — full integration tested manually.
    # The key contract: make_handlers receives todo_state kwarg.
    from basket_tui.native.handle.handlers import make_handlers
    from basket_tui.native.pipeline import StreamAssembler

    assembler = StreamAssembler()
    todo_state: list[dict] = []
    handlers = make_handlers(
        assembler, 80, lambda _: None, [0],
        {}, {}, todo_state=todo_state,
    )
    assert "on_todo_update" in handlers
```

**Step 2: Run test to verify it passes (this should already pass after Task 3)**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_run_integration.py -v`

**Step 3: Implement run.py changes**

In `packages/basket-tui/basket_tui/native/run.py`:

**3a.** Add import at top:
```python
from .ui.todo_panel import format_todo_panel, todo_panel_height
```

**3b.** After `last_output_count: list[int] = [0]` (line ~118), add:
```python
    todo_state: list[dict] = []
```

**3c.** Update `make_handlers` call (~line 134) to pass `todo_state`:
```python
    handlers = make_handlers(
        assembler,
        width,
        output_put,
        last_output_count,
        header_state,
        ui_state,
        on_streaming_update=_on_streaming_update,
        todo_state=todo_state,
    )
```

**3d.** Add todo panel callables before `build_layout` call (~line 390):
```python
    def get_todo_lines() -> str:
        return format_todo_panel(todo_state, width)

    def get_todo_height() -> int:
        return todo_panel_height(todo_state)
```

**3e.** Update `build_layout` call to pass `get_todo_lines` and `get_todo_height`:
```python
    layout = build_layout(
        width,
        base_url,
        header_state,
        ui_state,
        get_body_lines,
        input_buffer,
        banner_lines=banner_lines,
        doctor_lines=doctor_lines,
        footer_line=footer_plain,
        get_vertical_scroll=get_vertical_scroll,
        get_cursor_position=get_cursor_position,
        on_body_mouse_scroll=on_body_mouse_scroll,
        get_todo_lines=get_todo_lines,
        get_todo_height=get_todo_height,
    )
```

**Step 4: Run all tests to verify nothing breaks**

Run: `cd packages/basket-tui && poetry run pytest tests/ -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/run.py packages/basket-tui/tests/native/test_run_integration.py
git commit -m "feat(tui): wire todo_state through run.py to layout and handlers"
```

---

### Task 6: Export todo_panel from ui/__init__.py and run full test suite

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/ui/__init__.py`

**Step 1: Add exports**

In `packages/basket-tui/basket_tui/native/ui/__init__.py`, add:

```python
from .todo_panel import MAX_PANEL_LINES, format_todo_panel, todo_panel_height
```

And add to `__all__`:
```python
    "MAX_PANEL_LINES",
    "format_todo_panel",
    "todo_panel_height",
```

**Step 2: Run full test suites across all affected packages**

```bash
cd packages/basket-protocol && poetry run pytest tests/ -v
cd packages/basket-tui && poetry run pytest tests/ -v
```
Expected: ALL PASS

**Step 3: Commit**

```bash
git add packages/basket-tui/basket_tui/native/ui/__init__.py
git commit -m "chore(tui): export todo_panel symbols from ui package"
```

---

### Task 7: Final integration verification

**Step 1: Manual smoke test**

```bash
cd packages/basket-assistant
poetry run basket tui
```

Send a message that triggers `todo_write` (e.g., ask the agent to plan a multi-step task). Verify:
- [ ] Todo panel appears between conversation body and input
- [ ] Icons show correct status (◼ in_progress, ◻ pending)
- [ ] Panel disappears when all tasks complete
- [ ] Panel height is capped at 8 lines for many items
- [ ] Conversation scrolling still works correctly
- [ ] Footer spinner still works

**Step 2: Run all tests with coverage**

```bash
cd packages/basket-tui && poetry run pytest --cov=basket_tui --cov-report=term-missing tests/ -v
cd packages/basket-protocol && poetry run pytest --cov=basket_protocol --cov-report=term-missing tests/ -v
```

Verify: >80% coverage on new code.

**Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "test: verify TUI todo panel integration"
```

---

## File Modification Summary

| # | File | Action | Task |
|---|------|--------|------|
| 1 | `packages/basket-protocol/basket_protocol/inbound.py` | Modify | 1 |
| 2 | `packages/basket-protocol/basket_protocol/__init__.py` | Modify | 1 |
| 3 | `packages/basket-protocol/tests/test_inbound.py` | Modify | 1 |
| 4 | `packages/basket-tui/basket_tui/native/ui/todo_panel.py` | **Create** | 2 |
| 5 | `packages/basket-tui/tests/native/test_todo_panel.py` | **Create** | 2 |
| 6 | `packages/basket-tui/basket_tui/native/connection/types.py` | Modify | 3 |
| 7 | `packages/basket-tui/basket_tui/native/handle/dispatch.py` | Modify | 3 |
| 8 | `packages/basket-tui/basket_tui/native/handle/handlers.py` | Modify | 3 |
| 9 | `packages/basket-tui/basket_tui/native/connection/client.py` | Modify | 3 |
| 10 | `packages/basket-tui/tests/native/test_dispatch.py` | Modify | 3 |
| 11 | `packages/basket-tui/tests/native/test_handlers.py` | Modify | 3 |
| 12 | `packages/basket-tui/basket_tui/native/ui/layout.py` | Modify | 4 |
| 13 | `packages/basket-tui/tests/native/test_layout.py` | Modify | 4 |
| 14 | `packages/basket-tui/basket_tui/native/run.py` | Modify | 5 |
| 15 | `packages/basket-tui/basket_tui/native/ui/__init__.py` | Modify | 6 |

**Key discovery:** The gateway (`gateway.py:184-185`) already sends `{"type": "todos", ...}` after `todo_write`. No gateway changes needed.

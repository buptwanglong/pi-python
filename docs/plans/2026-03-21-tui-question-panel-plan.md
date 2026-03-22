# TUI Question Panel Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add interactive question display to the TUI — bottom panel with ↑/↓/Enter selection replaces input box during `ask_user_question`, and suppress `ask_user_question` + `todo_write` tool blocks from the conversation stream.

**Architecture:** New `question_panel.py` module (mirroring `todo_panel.py` pattern) renders ANSI option list. Layout conditionally swaps input row ↔ question panel. Protocol gets new `AskUserQuestion` message type. Dispatch filters tool rendering for suppressed tools.

**Tech Stack:** Python 3.12+, prompt_toolkit (ConditionalContainer), dataclasses (frozen), ANSI escape codes, pytest

---

### Task 1: Protocol — `AskUserQuestion` message type

**Files:**
- Modify: `packages/basket-protocol/basket_protocol/inbound.py`
- Modify: `packages/basket-protocol/basket_protocol/__init__.py`
- Test: `packages/basket-protocol/tests/test_inbound.py`

**Step 1: Write the failing tests**

Append to `packages/basket-protocol/tests/test_inbound.py`:

```python
def test_parse_inbound_ask_user_question() -> None:
    """parse_inbound({'type': 'ask_user_question', ...}) returns AskUserQuestion."""
    msg = parse_inbound({
        "type": "ask_user_question",
        "tool_call_id": "tc_123",
        "question": "Which approach?",
        "options": ["Option A", "Option B"],
    })
    assert isinstance(msg, AskUserQuestion)
    assert msg.tool_call_id == "tc_123"
    assert msg.question == "Which approach?"
    assert msg.options == ("Option A", "Option B")


def test_parse_inbound_ask_user_question_empty_options() -> None:
    """parse_inbound ask_user_question with empty options returns empty tuple."""
    msg = parse_inbound({
        "type": "ask_user_question",
        "tool_call_id": "tc_456",
        "question": "Free text?",
    })
    assert isinstance(msg, AskUserQuestion)
    assert msg.options == ()


def test_inbound_to_dict_ask_user_question_roundtrip() -> None:
    """inbound_to_dict(AskUserQuestion) returns wire dict; parse_inbound roundtrips."""
    msg = AskUserQuestion(
        tool_call_id="tc_789",
        question="Pick one",
        options=("A", "B", "C"),
    )
    d = inbound_to_dict(msg)
    assert d == {
        "type": "ask_user_question",
        "tool_call_id": "tc_789",
        "question": "Pick one",
        "options": ["A", "B", "C"],
    }
    parsed = parse_inbound(d)
    assert isinstance(parsed, AskUserQuestion)
    assert parsed.tool_call_id == msg.tool_call_id
    assert parsed.question == msg.question
    assert parsed.options == msg.options
```

Update the import block at the top of `test_inbound.py` to add `AskUserQuestion`:

```python
from basket_protocol import (
    AgentAborted,
    AgentComplete,
    AgentError,
    AgentSwitched,
    AskUserQuestion,
    SessionSwitched,
    System,
    TextDelta,
    ThinkingDelta,
    TodoUpdate,
    ToolCallEnd,
    ToolCallStart,
    Unknown,
    inbound_to_dict,
    parse_inbound,
)
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/basket-protocol && poetry run pytest tests/test_inbound.py -v -k "ask_user_question"`
Expected: ImportError — `AskUserQuestion` does not exist yet.

**Step 3: Implement AskUserQuestion dataclass and parse/serialize**

In `packages/basket-protocol/basket_protocol/inbound.py`:

a) Add the dataclass after `TodoUpdate` (before `Unknown`):

```python
@dataclass(frozen=True)
class AskUserQuestion:
    """Ask user a question with optional choices."""

    tool_call_id: str = ""
    question: str = ""
    options: tuple[str, ...] = ()
```

b) Add `AskUserQuestion` to the `InboundMessage` Union (before `Unknown`):

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
    AskUserQuestion,
    Unknown,
]
```

c) Add parse case in `parse_inbound()`, before the final `return Unknown(...)`:

```python
    if typ == "ask_user_question":
        raw_options = data.get("options") or []
        return AskUserQuestion(
            tool_call_id=data.get("tool_call_id", "") or "",
            question=data.get("question", "") or "",
            options=tuple(raw_options),
        )
```

d) Add serialize case in `inbound_to_dict()`, before the `Unknown` branch:

```python
    if isinstance(msg, AskUserQuestion):
        return {
            "type": "ask_user_question",
            "tool_call_id": msg.tool_call_id,
            "question": msg.question,
            "options": list(msg.options),
        }
```

e) In `packages/basket-protocol/basket_protocol/__init__.py`, add `AskUserQuestion` to imports and `__all__`:

Import line:
```python
from .inbound import (
    AgentAborted,
    AgentComplete,
    AgentError,
    AgentSwitched,
    AskUserQuestion,
    ...
)
```

Add to `__all__`:
```python
    "AskUserQuestion",
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/basket-protocol && poetry run pytest tests/test_inbound.py -v`
Expected: ALL PASS (including 3 new tests).

**Step 5: Commit**

```bash
git add packages/basket-protocol/basket_protocol/inbound.py packages/basket-protocol/basket_protocol/__init__.py packages/basket-protocol/tests/test_inbound.py
git commit -m "feat(protocol): add AskUserQuestion inbound message type"
```

---

### Task 2: Question panel rendering module

**Files:**
- Create: `packages/basket-tui/basket_tui/native/ui/question_panel.py`
- Modify: `packages/basket-tui/basket_tui/native/ui/__init__.py`
- Test: `packages/basket-tui/tests/native/test_question_panel.py`

**Step 1: Write the failing tests**

Create `packages/basket-tui/tests/native/test_question_panel.py`:

```python
"""Tests for TUI question panel rendering."""

import re

import pytest

from basket_tui.native.ui.question_panel import (
    format_question_panel,
    question_panel_height,
    new_question_state,
    FREE_TEXT_LABEL,
)


def _strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m|\x1b\]8;;.*?\x1b\\", "", s)


# --- new_question_state ---

def test_new_question_state_returns_inactive():
    """Default state is inactive."""
    state = new_question_state()
    assert state["active"] is False
    assert state["tool_call_id"] == ""
    assert state["question"] == ""
    assert state["options"] == []
    assert state["selected"] == 0


# --- question_panel_height ---

def test_question_panel_height_inactive_returns_zero():
    """Inactive state -> height 0 (panel hidden)."""
    state = new_question_state()
    assert question_panel_height(state) == 0


def test_question_panel_height_active_with_options():
    """Active with 3 options -> height = 3 options + 1 free text = 4."""
    state = new_question_state()
    state["active"] = True
    state["options"] = ["A", "B", "C"]
    assert question_panel_height(state) == 4


def test_question_panel_height_active_no_options():
    """Active with no options -> height = 1 (free text only)."""
    state = new_question_state()
    state["active"] = True
    state["options"] = []
    assert question_panel_height(state) == 1


# --- format_question_panel ---

def test_format_question_panel_inactive_returns_empty():
    """Inactive state -> empty string."""
    state = new_question_state()
    assert format_question_panel(state, 80) == ""


def test_format_question_panel_selected_item_has_marker():
    """Selected item shows ❯ marker."""
    state = new_question_state()
    state["active"] = True
    state["options"] = ["Option A", "Option B"]
    state["selected"] = 0
    result = _strip_ansi(format_question_panel(state, 80))
    lines = result.split("\n")
    assert any("❯" in line and "Option A" in line for line in lines)


def test_format_question_panel_unselected_item_no_marker():
    """Unselected item does NOT show ❯ marker."""
    state = new_question_state()
    state["active"] = True
    state["options"] = ["Option A", "Option B"]
    state["selected"] = 0
    result = _strip_ansi(format_question_panel(state, 80))
    lines = result.split("\n")
    b_lines = [l for l in lines if "Option B" in l]
    assert b_lines, "Option B must appear"
    assert "❯" not in b_lines[0]


def test_format_question_panel_free_text_shown():
    """Free text slot always shown as last item."""
    state = new_question_state()
    state["active"] = True
    state["options"] = ["Option A"]
    result = _strip_ansi(format_question_panel(state, 80))
    assert FREE_TEXT_LABEL in result


def test_format_question_panel_free_text_selected():
    """When selected == len(options), free text is highlighted."""
    state = new_question_state()
    state["active"] = True
    state["options"] = ["Option A"]
    state["selected"] = 1  # free text index
    result = _strip_ansi(format_question_panel(state, 80))
    lines = result.split("\n")
    ft_lines = [l for l in lines if FREE_TEXT_LABEL in l]
    assert ft_lines, "Free text must appear"
    assert "❯" in ft_lines[0]


def test_format_question_panel_truncates_long_option():
    """Option longer than width is truncated with ellipsis."""
    state = new_question_state()
    state["active"] = True
    state["options"] = ["A" * 200]
    state["selected"] = 0
    result = _strip_ansi(format_question_panel(state, 60))
    assert "\u2026" in result
    for line in result.split("\n"):
        assert len(line) <= 60


def test_format_question_panel_no_options_only_free_text():
    """When options is empty, only free text row shown."""
    state = new_question_state()
    state["active"] = True
    state["options"] = []
    state["selected"] = 0
    result = _strip_ansi(format_question_panel(state, 80))
    assert FREE_TEXT_LABEL in result
    lines = [l for l in result.split("\n") if l.strip()]
    assert len(lines) == 1
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_question_panel.py -v`
Expected: ImportError — `question_panel` module does not exist yet.

**Step 3: Implement question_panel.py**

Create `packages/basket-tui/basket_tui/native/ui/question_panel.py`:

```python
"""
Question panel rendering for terminal-native TUI.

Renders an interactive option list at the bottom of the screen when
an ask_user_question tool is active. Panel is hidden (height 0) when inactive.
"""

from __future__ import annotations

from typing import Any

# ANSI styles
_ANSI_RESET = "\x1b[0m"
_ANSI_HIGHLIGHT = "\x1b[38;2;100;200;255m"  # bright cyan (matches todo in_progress)
_ANSI_DIM = "\x1b[38;2;123;127;135m"  # muted gray

# Selection marker
_SELECTED_PREFIX = "  \u276f "  # ❯
_UNSELECTED_PREFIX = "    "
_ITEM_OVERHEAD = len(_UNSELECTED_PREFIX)

# Free text label (always last item)
FREE_TEXT_LABEL = "\u81ea\u7531\u8f93\u5165..."


def new_question_state() -> dict[str, Any]:
    """Return a fresh, inactive question state dict."""
    return {
        "active": False,
        "tool_call_id": "",
        "question": "",
        "options": [],
        "selected": 0,
    }


def question_panel_height(state: dict[str, Any]) -> int:
    """Return the panel height in lines. 0 means hidden (inactive)."""
    if not state.get("active"):
        return 0
    options = state.get("options") or []
    return len(options) + 1  # +1 for free text slot


def format_question_panel(state: dict[str, Any], width: int) -> str:
    """
    Render the question option list as a single ANSI string (lines joined by newline).

    Returns empty string when inactive (panel should be hidden).
    """
    if not state.get("active"):
        return ""

    options: list[str] = state.get("options") or []
    selected: int = state.get("selected", 0)
    max_content_len = max(width - _ITEM_OVERHEAD, 1)

    lines: list[str] = []

    for i, option in enumerate(options):
        is_sel = i == selected
        prefix = _SELECTED_PREFIX if is_sel else _UNSELECTED_PREFIX
        color = _ANSI_HIGHLIGHT if is_sel else _ANSI_RESET
        text = option
        if len(text) > max_content_len:
            text = text[: max_content_len - 1] + "\u2026"
        lines.append(f"{color}{prefix}{text}{_ANSI_RESET}")

    # Free text slot (always last)
    ft_idx = len(options)
    is_ft_sel = selected == ft_idx
    ft_prefix = _SELECTED_PREFIX if is_ft_sel else _UNSELECTED_PREFIX
    ft_color = _ANSI_HIGHLIGHT if is_ft_sel else _ANSI_DIM
    lines.append(f"{ft_color}{ft_prefix}{FREE_TEXT_LABEL}{_ANSI_RESET}")

    return "\n".join(lines)
```

Add exports to `packages/basket-tui/basket_tui/native/ui/__init__.py`:

Add import:
```python
from .question_panel import (
    FREE_TEXT_LABEL,
    format_question_panel,
    new_question_state,
    question_panel_height,
)
```

Add to `__all__`:
```python
    "FREE_TEXT_LABEL",
    "format_question_panel",
    "new_question_state",
    "question_panel_height",
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_question_panel.py -v`
Expected: ALL PASS (11 tests).

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/ui/question_panel.py packages/basket-tui/basket_tui/native/ui/__init__.py packages/basket-tui/tests/native/test_question_panel.py
git commit -m "feat(tui): add question panel rendering module"
```

---

### Task 3: Tool message suppression in dispatch

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/handle/dispatch.py`
- Test: `packages/basket-tui/tests/native/test_dispatch.py`

**Step 1: Write the failing tests**

Append to `packages/basket-tui/tests/native/test_dispatch.py`:

```python
# --- Tool message suppression ---

_SUPPRESSED_TOOLS = ("ask_user_question", "todo_write")


def test_handle_tool_call_start_suppressed_tool_no_render():
    """ask_user_question tool_call_start records tool but does not render to output."""
    for tool_name in _SUPPRESSED_TOOLS:
        assembler, width, out, output_put, last_output_count = _minimal_setup()
        assembler.text_delta("Some text")
        handle_tool_call_start(
            assembler,
            tool_name,
            arguments={"q": "test"},
            ui_state={"phase": "streaming"},
            width=width,
            output_put=output_put,
            last_output_count=last_output_count,
        )
        # Tool recorded in assembler
        assert assembler._current_tool is not None
        assert assembler._current_tool["tool_name"] == tool_name
        # Buffer NOT flushed to output (no render of prior text for suppressed tool)
        assert len(out) == 0, f"{tool_name}: suppressed tool should not render"


def test_handle_tool_call_end_suppressed_tool_no_render():
    """ask_user_question/todo_write tool_call_end records message but does not render."""
    for tool_name in _SUPPRESSED_TOOLS:
        assembler, width, out, output_put, last_output_count = _minimal_setup()
        handle_tool_call_start(assembler, tool_name, arguments={})
        handle_tool_call_end(
            assembler,
            tool_name,
            result="ok",
            error=None,
            width=width,
            output_put=output_put,
            last_output_count=last_output_count,
        )
        # Tool message recorded in assembler
        tool_msgs = [m for m in assembler.messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        # NOT rendered to output
        assert len(out) == 0, f"{tool_name}: suppressed tool should not render"


def test_handle_tool_call_end_normal_tool_still_renders():
    """Normal tools (e.g. 'bash') still render to output."""
    assembler, width, out, output_put, last_output_count = _minimal_setup()
    handle_tool_call_start(assembler, "bash", arguments={"cmd": "ls"})
    handle_tool_call_end(
        assembler,
        "bash",
        result="file.txt",
        error=None,
        width=width,
        output_put=output_put,
        last_output_count=last_output_count,
    )
    assert len(out) >= 1, "Normal tool should render"
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_dispatch.py -v -k "suppressed"`
Expected: FAIL — suppressed tools still render.

**Step 3: Add suppression logic to dispatch.py**

In `packages/basket-tui/basket_tui/native/handle/dispatch.py`:

a) Add constant at module level (after `logger`):

```python
# Tool names whose blocks are suppressed from the conversation stream.
# They are still recorded in the assembler but not rendered via output_put.
_SUPPRESSED_TOOLS = frozenset({"ask_user_question", "todo_write"})
```

b) Modify `handle_tool_call_start`: add early return for suppressed tools AFTER setting `ui_state` phase but BEFORE flush+render. Replace the function body:

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
    if ui_state is not None:
        ui_state["phase"] = "tool_running"

    if tool_name in _SUPPRESSED_TOOLS:
        # Record in assembler but skip flush+render
        assembler.tool_call_start(tool_name, arguments)
        logger.info(
            "Tool call started (suppressed)",
            extra={"tool_name": tool_name, "phase": "tool_running"},
        )
        return

    # Flush streaming buffer BEFORE tool starts so text appears before tool block
    if output_put is not None and last_output_count is not None:
        if assembler.flush_buffer():
            _render_and_output(assembler.messages[-1], width, output_put)
            last_output_count[0] = len(assembler.messages)

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

c) Modify `handle_tool_call_end`: add early return for suppressed tools. Replace the function body:

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

    if tool_name in _SUPPRESSED_TOOLS:
        # Record but do not render
        if last_output_count is not None:
            last_output_count[0] = len(assembler.messages)
        logger.info(
            "Tool call ended (suppressed)",
            extra={"tool_name": tool_name, "has_result": result is not None},
        )
        return

    # Render tool block immediately instead of waiting for agent_complete
    if output_put is not None and last_output_count is not None:
        _render_and_output(assembler.messages[-1], width, output_put)
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

**Step 4: Run tests to verify they pass**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_dispatch.py -v`
Expected: ALL PASS (including 3 new suppression tests + all existing tests).

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/handle/dispatch.py packages/basket-tui/tests/native/test_dispatch.py
git commit -m "feat(tui): suppress ask_user_question and todo_write tool blocks from stream"
```

---

### Task 4: Connection layer — dispatch AskUserQuestion

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/connection/types.py`
- Modify: `packages/basket-tui/basket_tui/native/connection/client.py`
- Test: `packages/basket-tui/tests/native/test_handlers.py`

**Step 1: Write the failing test**

Append to `packages/basket-tui/tests/native/test_handlers.py`:

```python
from basket_protocol import AskUserQuestion


def test_make_handlers_on_ask_user_question_updates_state() -> None:
    """on_ask_user_question handler updates question_state from AskUserQuestion event."""
    assembler = StreamAssembler()
    width = 80
    lines_out: list[str] = []
    last_output_count = [0]
    header_state: dict[str, str] = {}
    ui_state: dict[str, str] = {}
    question_state: dict = {
        "active": False,
        "tool_call_id": "",
        "question": "",
        "options": [],
        "selected": 0,
    }

    handlers = make_handlers(
        assembler, width, lines_out.append, last_output_count,
        header_state, ui_state, question_state=question_state,
    )

    assert "on_ask_user_question" in handlers
    handlers["on_ask_user_question"](AskUserQuestion(
        tool_call_id="tc_001",
        question="Which approach?",
        options=("Option A", "Option B"),
    ))
    assert question_state["active"] is True
    assert question_state["tool_call_id"] == "tc_001"
    assert question_state["question"] == "Which approach?"
    assert question_state["options"] == ["Option A", "Option B"]
    assert question_state["selected"] == 0
```

**Step 2: Run test to verify it fails**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_handlers.py -v -k "ask_user_question"`
Expected: FAIL — `make_handlers` does not accept `question_state` parameter.

**Step 3: Wire AskUserQuestion through connection layer**

a) In `packages/basket-tui/basket_tui/native/connection/types.py`, add import and handler:

Add `AskUserQuestion` to imports:
```python
from basket_protocol import (
    AgentAborted,
    AgentComplete,
    AgentError,
    AgentSwitched,
    AskUserQuestion,
    SessionSwitched,
    System,
    TextDelta,
    ThinkingDelta,
    TodoUpdate,
    ToolCallEnd,
    ToolCallStart,
)
```

Add to `GatewayHandlers` TypedDict:
```python
    on_ask_user_question: Callable[[AskUserQuestion], None]
```

b) In `packages/basket-tui/basket_tui/native/connection/client.py`, add import and dispatch:

Add `AskUserQuestion` to imports (in the `from basket_protocol import (` block):
```python
    AskUserQuestion,
```

Add dispatch case in `_dispatch()` method, after the `TodoUpdate` elif block:
```python
            elif isinstance(parsed, AskUserQuestion):
                h = self._handlers.get("on_ask_user_question")
                if h:
                    h(parsed)
```

c) In `packages/basket-tui/basket_tui/native/handle/dispatch.py`, add `handle_ask_user_question`:

```python
def handle_ask_user_question(
    question_state: dict[str, Any],
    tool_call_id: str,
    question: str,
    options: list[str],
) -> None:
    """Handle ask_user_question: activate question panel with options."""
    question_state["active"] = True
    question_state["tool_call_id"] = tool_call_id
    question_state["question"] = question
    question_state["options"] = options
    question_state["selected"] = 0
    logger.info(
        "Question panel activated",
        extra={"tool_call_id": tool_call_id, "option_count": len(options)},
    )
```

d) In `packages/basket-tui/basket_tui/native/handle/handlers.py`:

Add import:
```python
from .dispatch import (
    handle_agent_aborted,
    handle_agent_complete,
    handle_agent_error,
    handle_agent_switched,
    handle_ask_user_question,
    handle_session_switched,
    handle_system,
    handle_text_delta,
    handle_thinking_delta,
    handle_tool_call_end,
    handle_tool_call_start,
)
```

Add `question_state` parameter to `make_handlers`:
```python
def make_handlers(
    assembler: StreamAssembler,
    width: int,
    output_put: Callable[[str], None],
    last_output_count: list[int],
    header_state: Optional[dict[str, str]] = None,
    ui_state: Optional[dict[str, str]] = None,
    on_streaming_update: Optional[Callable[[], None]] = None,
    todo_state: Optional[list[dict]] = None,
    question_state: Optional[dict] = None,
) -> GatewayHandlers:
```

Add handler wiring after the `todo_state` block:
```python
    if question_state is not None:
        handlers["on_ask_user_question"] = lambda event: handle_ask_user_question(
            question_state, event.tool_call_id, event.question, list(event.options)
        )
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_handlers.py -v`
Expected: ALL PASS (including new test).

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/connection/types.py packages/basket-tui/basket_tui/native/connection/client.py packages/basket-tui/basket_tui/native/handle/dispatch.py packages/basket-tui/basket_tui/native/handle/handlers.py packages/basket-tui/tests/native/test_handlers.py
git commit -m "feat(tui): wire AskUserQuestion through connection and handler layers"
```

---

### Task 5: Layout — conditional input row / question panel

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/ui/layout.py`

**Step 1: Add conditional layout parameters**

In `packages/basket-tui/basket_tui/native/ui/layout.py`, update `build_layout` signature to add:

```python
def build_layout(
    width: int,
    base_url: str,
    header_state: dict[str, str],
    ui_state: dict[str, str],
    get_body_lines: Callable[[], list[str]],
    input_buffer: Any,
    *,
    banner_lines: list[str] | None = None,
    doctor_lines: list[str] | None = None,
    footer_line: Callable[[], str] | None = None,
    get_vertical_scroll: Callable[[Any], int],
    get_cursor_position: Callable[[], Point],
    on_body_mouse_scroll: Callable[[Any], None],
    get_todo_lines: Callable[[], str] | None = None,
    get_todo_height: Callable[[], int] | None = None,
    get_question_lines: Callable[[], str] | None = None,
    get_question_height: Callable[[], int] | None = None,
    is_question_active: Callable[[], bool] | None = None,
) -> Layout:
```

**Step 2: Add ConditionalContainer import and conditional rows**

Add imports at top:
```python
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout.containers import ConditionalContainer
```

Replace the bottom rows section (lines ~180-187 in current code). The current code is:
```python
    rows_to_add.extend([
        Window(height=1, content=footer_control),
        Window(height=1, content=sep_control),
        VSplit([
            Window(width=3, content=FormattedTextControl("❯ "), dont_extend_width=True),
            Window(content=input_control),
        ]),
    ])
```

Replace with:
```python
    # Input row (normal mode)
    input_row = VSplit([
        Window(width=3, content=FormattedTextControl("❯ "), dont_extend_width=True),
        Window(content=input_control),
    ])

    # Question panel (question active mode)
    if get_question_lines is not None and get_question_height is not None and is_question_active is not None:
        has_question = Condition(lambda: is_question_active())

        question_control = FormattedTextControl(
            text=lambda: ANSI(get_question_lines() or ""),
            focusable=False,
        )
        question_window = Window(
            content=question_control,
            height=lambda: get_question_height(),
        )

        rows_to_add.extend([
            Window(height=1, content=footer_control),
            Window(height=1, content=sep_control),
            ConditionalContainer(input_row, filter=~has_question),
            ConditionalContainer(question_window, filter=has_question),
        ])
    else:
        rows_to_add.extend([
            Window(height=1, content=footer_control),
            Window(height=1, content=sep_control),
            input_row,
        ])
```

**Step 3: Run existing tests to verify nothing breaks**

Run: `cd packages/basket-tui && poetry run pytest tests/native/ -v`
Expected: ALL PASS — existing behavior unchanged (new params are optional).

**Step 4: Commit**

```bash
git add packages/basket-tui/basket_tui/native/ui/layout.py
git commit -m "feat(tui): add conditional question panel slot to layout"
```

---

### Task 6: Wire everything in run.py — state, keybindings, answer submission

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1: Add question state and panel wiring**

In `packages/basket-tui/basket_tui/native/run.py`:

a) Add import:
```python
from .ui.question_panel import format_question_panel, new_question_state, question_panel_height
```

Also add `import json` at the top (needed for answer submission).

b) After `todo_state: list[dict] = []` (line 122), add:
```python
    question_state: dict = new_question_state()
```

c) Update `make_handlers` call to pass `question_state`:
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
        question_state=question_state,
    )
```

d) Add question panel accessors (after `get_todo_height` function):
```python
    def get_question_lines() -> str:
        return format_question_panel(question_state, width)

    def get_question_height() -> int:
        return question_panel_height(question_state)

    def is_question_active() -> bool:
        return question_state.get("active", False)
```

e) Update `build_layout` call to pass question params:
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
        get_question_lines=get_question_lines,
        get_question_height=get_question_height,
        is_question_active=is_question_active,
    )
```

**Step 2: Add question-mode key bindings**

a) Modify `_on_enter` to handle question mode:

Replace the existing `_accept_input` function:
```python
    def _accept_input(event: Any) -> None:
        from prompt_toolkit.application import get_app

        # Question mode: submit selected answer
        if question_state.get("active"):
            options = question_state.get("options") or []
            selected = question_state.get("selected", 0)
            if selected < len(options):
                answer = options[selected]
            else:
                # Free text mode: use input buffer text
                answer = (input_buffer.text or "").strip()
                if not answer:
                    return  # ignore empty free text
                input_buffer.reset()

            payload = json.dumps({
                "answer": answer,
                "tool_call_id": question_state.get("tool_call_id", ""),
            })
            asyncio.get_running_loop().create_task(conn.send_message(payload))

            # Display user answer as gray block
            for line in render_messages([{"role": "user", "content": answer}], width):
                output_put(line)

            # Reset question state
            question_state["active"] = False
            question_state["tool_call_id"] = ""
            question_state["question"] = ""
            question_state["options"] = []
            question_state["selected"] = 0
            get_app().invalidate()
            return

        text = (input_buffer.text or "").strip()
        input_buffer.reset()
        result = handle_input(text, base_url, conn, output_put)
        logger.info("User input received", extra={"text_len": len(text), "result": result})
        if result == "exit":
            _cancel_aux_tasks()
            asyncio.get_running_loop().create_task(conn.close())
            get_app().exit()
            return
        if result == "handled":
            get_app().invalidate()
            return
        if result == "send":
            for line in render_messages([{"role": "user", "content": text}], width):
                output_put(line)
            get_app().invalidate()
```

b) Add ↑/↓ key bindings for question navigation:

```python
    @kb.add("up")
    def _on_up(event: Any) -> None:
        if question_state.get("active"):
            sel = question_state.get("selected", 0)
            question_state["selected"] = max(0, sel - 1)
            event.app.invalidate()

    @kb.add("down")
    def _on_down(event: Any) -> None:
        if question_state.get("active"):
            options = question_state.get("options") or []
            max_idx = len(options)  # options + free text slot
            sel = question_state.get("selected", 0)
            question_state["selected"] = min(max_idx, sel + 1)
            event.app.invalidate()
```

c) Update the abort handler (Escape) to also clear question state:

In `_on_escape`, add question dismissal before the abort:
```python
    @kb.add("escape")
    def _on_escape(event: Any) -> None:
        """Esc: dismiss completion/question, or abort current turn."""
        buf = event.app.current_buffer
        if buf is not None and buf.complete_state is not None:
            buf.cancel_completion()
            event.app.invalidate()
            return
        # Dismiss active question
        if question_state.get("active"):
            question_state["active"] = False
            question_state["tool_call_id"] = ""
            question_state["options"] = []
            question_state["selected"] = 0
            event.app.invalidate()
            return
        asyncio.get_running_loop().create_task(conn.send_abort())
        from prompt_toolkit.application import get_app
        get_app().invalidate()
```

d) Update `handle_agent_aborted` handler to also clear question state. In the existing handlers dict, change:
```python
        "on_agent_aborted": lambda event: _on_agent_aborted(assembler, output_put),
```

Add a wrapper function:
```python
    def _on_aborted(event):
        handle_agent_aborted(assembler, output_put)
        question_state["active"] = False
        question_state["tool_call_id"] = ""
        question_state["options"] = []
        question_state["selected"] = 0

    # In the handlers dict, use:
    # "on_agent_aborted": lambda event: _on_aborted(event),
```

**Important:** The abort reset should be done either in `run.py`'s lambda or via a small wrapper — not in `dispatch.py` (which doesn't know about question_state).

Actually, a cleaner approach: add the abort reset directly in `run.py` by wrapping the handler:

After `handlers = make_handlers(...)`, add:
```python
    # Wrap agent_aborted to also clear question state
    _original_on_aborted = handlers.get("on_agent_aborted")
    def _on_aborted_wrapper(event):
        if _original_on_aborted:
            _original_on_aborted(event)
        question_state["active"] = False
        question_state["tool_call_id"] = ""
        question_state["options"] = []
        question_state["selected"] = 0
    handlers["on_agent_aborted"] = _on_aborted_wrapper
```

**Step 3: Run all tests to verify nothing breaks**

Run: `cd packages/basket-tui && poetry run pytest tests/native/ -v`
Expected: ALL PASS.

**Step 4: Commit**

```bash
git add packages/basket-tui/basket_tui/native/run.py
git commit -m "feat(tui): wire question panel state, keybindings, and answer submission"
```

---

### Task 7: Run full test suite and verify

**Files:** None (verification only)

**Step 1: Run all protocol tests**

Run: `cd packages/basket-protocol && poetry run pytest -v`
Expected: ALL PASS.

**Step 2: Run all TUI tests**

Run: `cd packages/basket-tui && poetry run pytest -v`
Expected: ALL PASS.

**Step 3: Run all tests from monorepo root**

Run: `poetry run pytest packages/basket-protocol packages/basket-tui -v`
Expected: ALL PASS.

**Step 4: Final commit (if any fixups needed)**

If any test fixes were needed, commit them:
```bash
git add -u
git commit -m "fix: address test issues from question panel integration"
```

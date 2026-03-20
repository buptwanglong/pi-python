"""Tests for make_handlers (GatewayHandlers from dispatch state)."""

import pytest

from basket_protocol import AgentComplete, TextDelta, TodoUpdate, ToolCallEnd, ToolCallStart
from basket_tui.native.handle import make_handlers
from basket_tui.native.pipeline import StreamAssembler


def test_make_handlers_returns_dict_like_on_text_delta_appends_to_buffer() -> None:
    """make_handlers returns dict-like; on_text_delta(TextDelta(delta='x')) leaves assembler._buffer == 'x'."""
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

    assert handlers is not None
    assert "on_text_delta" in handlers
    on_text_delta = handlers["on_text_delta"]
    assert callable(on_text_delta)

    on_text_delta(TextDelta(delta="x"))
    assert assembler._buffer == "x"


def test_make_handlers_on_agent_complete_invokes_output_put_and_updates_last_output_count() -> None:
    """Calling returned on_agent_complete() invokes output_put with rendered lines and updates last_output_count[0]."""
    assembler = StreamAssembler()
    assembler.text_delta("Hello")
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

    assert "on_agent_complete" in handlers
    on_agent_complete = handlers["on_agent_complete"]
    assert callable(on_agent_complete)

    on_agent_complete(AgentComplete())

    assert len(lines_out) >= 1
    assert any("Hello" in line or "assistant" in line for line in lines_out)
    assert last_output_count[0] == 1


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

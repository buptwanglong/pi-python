"""Tests for native run (dispatch and wiring)."""

import threading
from unittest.mock import patch

import pytest

from basket_tui.native.commands import HELP_LINES, handle_slash_command
from basket_tui.native.run import _dispatch_ws_message, _get_width
from basket_tui.native.stream import StreamAssembler


def _dispatch_setup():
    """Return (assembler, out, output_put, last_output_count, header_state, ui_state) for _dispatch_ws_message tests."""
    assembler = StreamAssembler()
    out: list[str] = []
    output_put = out.append
    last_output_count: list[int] = [0]
    header_state: dict[str, str] = {}
    ui_state: dict[str, str] = {}
    return assembler, out, output_put, last_output_count, header_state, ui_state


def test_get_width_returns_max_cols_when_positive():
    assert _get_width(120) == 120
    assert _get_width(80) == 80


def test_get_width_returns_terminal_columns_or_fallback_when_none():
    w = _get_width(None)
    assert isinstance(w, int)
    assert w >= 1


def test_get_width_returns_fallback_when_max_cols_zero():
    # 0 is treated as "use terminal"; if terminal size fails, fallback 80
    with patch("shutil.get_terminal_size", side_effect=Exception):
        assert _get_width(0) == 80


def test_help_lines_non_empty():
    lines = HELP_LINES
    assert len(lines) >= 1
    assert any("/help" in line for line in lines)
    assert any("/exit" in line for line in lines)


def test_handle_slash_command_help_returns_handled():
    with patch("basket_tui.native.commands.print"):
        assert handle_slash_command("/help") == "handled"


def test_handle_slash_command_exit_returns_exit():
    assert handle_slash_command("/exit") == "exit"


def test_handle_slash_command_stub_returns_handled():
    with patch("basket_tui.native.commands.print"):
        assert handle_slash_command("/session") == "handled"
        assert handle_slash_command("/agent") == "handled"
        assert handle_slash_command("/new") == "handled"


def test_handle_slash_command_non_slash_returns_none():
    assert handle_slash_command("hello") is None
    assert handle_slash_command("") is None


def test_dispatch_text_delta_and_agent_complete_updates_assembler():
    assembler = StreamAssembler()
    width = 80
    out: list[str] = []
    output_put = out.append
    last_output_count: list[int] = [0]
    _dispatch_ws_message(
        {"type": "text_delta", "delta": "Hi"}, assembler, width, output_put, last_output_count
    )
    _dispatch_ws_message(
        {"type": "agent_complete"}, assembler, width, output_put, last_output_count
    )
    assert len(assembler.messages) == 1
    assert assembler.messages[0]["role"] == "assistant"
    assert assembler.messages[0]["content"] == "Hi"
    assert len(out) >= 1


def test_dispatch_tool_call_start_end_adds_tool_message():
    assembler = StreamAssembler()
    width = 80
    output_put = lambda _: None
    last_output_count: list[int] = [0]
    _dispatch_ws_message(
        {"type": "tool_call_start", "tool_name": "bash", "arguments": {"cmd": "ls"}},
        assembler,
        width,
        output_put,
        last_output_count,
    )
    _dispatch_ws_message(
        {"type": "tool_call_end", "tool_name": "bash", "result": "ok", "error": None},
        assembler,
        width,
        output_put,
        last_output_count,
    )
    tool_msgs = [m for m in assembler.messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert "bash" in tool_msgs[0]["content"]


def test_dispatch_unknown_type_no_op():
    assembler = StreamAssembler()
    width = 80
    output_put = lambda _: None
    last_output_count: list[int] = [0]
    _dispatch_ws_message(
        {"type": "unknown_event"}, assembler, width, output_put, last_output_count
    )
    assert len(assembler.messages) == 0


def test_dispatch_session_switched_prints_line():
    assembler = StreamAssembler()
    width = 80
    out: list[str] = []
    output_put = out.append
    last_output_count: list[int] = [0]
    _dispatch_ws_message(
        {"type": "session_switched", "session_id": "abc123"},
        assembler,
        width,
        output_put,
        last_output_count,
    )
    assert len(out) == 1
    assert "abc123" in out[0]


def test_dispatch_agent_switched_prints_line():
    assembler = StreamAssembler()
    width = 80
    out: list[str] = []
    output_put = out.append
    last_output_count: list[int] = [0]
    _dispatch_ws_message(
        {"type": "agent_switched", "agent_name": "explore"},
        assembler,
        width,
        output_put,
        last_output_count,
    )
    assert len(out) == 1
    assert "explore" in out[0]


def test_dispatch_session_switched_updates_header_state():
    assembler, out, output_put, last_output_count, header_state, ui_state = _dispatch_setup()
    header_state["session"] = "old"
    width = 80
    _dispatch_ws_message(
        {"type": "session_switched", "session_id": "s1"},
        assembler,
        width,
        output_put,
        last_output_count,
        header_state=header_state,
        ui_state=ui_state,
    )
    assert header_state["session"] == "s1"
    assert len(out) == 1
    assert "s1" in out[0]


def test_dispatch_agent_switched_updates_header_state():
    assembler, out, output_put, last_output_count, header_state, ui_state = _dispatch_setup()
    header_state["agent"] = "old"
    width = 80
    _dispatch_ws_message(
        {"type": "agent_switched", "agent_name": "my_agent"},
        assembler,
        width,
        output_put,
        last_output_count,
        header_state=header_state,
        ui_state=ui_state,
    )
    assert header_state["agent"] == "my_agent"
    assert len(out) == 1
    assert "my_agent" in out[0]


def test_dispatch_ui_state_phase_streaming():
    assembler, out, output_put, last_output_count, header_state, ui_state = _dispatch_setup()
    width = 80
    _dispatch_ws_message(
        {"type": "text_delta", "delta": "x"},
        assembler,
        width,
        output_put,
        last_output_count,
        header_state=header_state,
        ui_state=ui_state,
    )
    assert ui_state["phase"] == "streaming"


def test_dispatch_ui_state_phase_tool_running():
    assembler, out, output_put, last_output_count, header_state, ui_state = _dispatch_setup()
    width = 80
    _dispatch_ws_message(
        {"type": "tool_call_start", "tool_name": "bash", "arguments": {}},
        assembler,
        width,
        output_put,
        last_output_count,
        header_state=header_state,
        ui_state=ui_state,
    )
    assert ui_state["phase"] == "tool_running"


def test_dispatch_ui_state_phase_idle():
    assembler, out, output_put, last_output_count, header_state, ui_state = _dispatch_setup()
    width = 80
    _dispatch_ws_message(
        {"type": "text_delta", "delta": "hi"},
        assembler,
        width,
        output_put,
        last_output_count,
        header_state=header_state,
        ui_state=ui_state,
    )
    _dispatch_ws_message(
        {"type": "agent_complete"},
        assembler,
        width,
        output_put,
        last_output_count,
        header_state=header_state,
        ui_state=ui_state,
    )
    assert ui_state["phase"] == "idle"


def test_dispatch_ui_state_phase_error():
    assembler, out, output_put, last_output_count, header_state, ui_state = _dispatch_setup()
    width = 80
    _dispatch_ws_message(
        {"type": "agent_error", "error": "Something failed"},
        assembler,
        width,
        output_put,
        last_output_count,
        header_state=header_state,
        ui_state=ui_state,
    )
    assert ui_state["phase"] == "error"


def test_dispatch_agent_aborted_clears_and_prints():
    assembler, out, output_put, last_output_count, header_state, ui_state = _dispatch_setup()
    width = 80
    _dispatch_ws_message(
        {"type": "text_delta", "delta": "x"},
        assembler,
        width,
        output_put,
        last_output_count,
    )
    _dispatch_ws_message(
        {"type": "agent_aborted"},
        assembler,
        width,
        output_put,
        last_output_count,
    )
    assert any("Aborted" in line for line in out)
    assert assembler._buffer == ""
    assert assembler._current_tool is None


def test_dispatch_agent_error_prints_message():
    assembler, out, output_put, last_output_count, _, _ = _dispatch_setup()
    width = 80
    _dispatch_ws_message(
        {"type": "agent_error", "error": "Something failed"},
        assembler,
        width,
        output_put,
        last_output_count,
    )
    assert len(out) == 1
    assert "Something failed" in out[0]


def test_dispatch_error_type_prints_gateway_error():
    assembler, out, output_put, last_output_count, _, _ = _dispatch_setup()
    width = 80
    _dispatch_ws_message(
        {"type": "error", "error": "Gateway down"},
        assembler,
        width,
        output_put,
        last_output_count,
    )
    assert len(out) == 1
    assert "Gateway" in out[0] or "down" in out[0]

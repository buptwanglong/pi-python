"""Tests for native dispatch per-type handlers."""

from basket_tui.native.dispatch import (
    handle_agent_aborted,
    handle_agent_complete,
    handle_agent_error,
    handle_agent_switched,
    handle_session_switched,
    handle_text_delta,
    handle_thinking_delta,
    handle_tool_call_end,
    handle_tool_call_start,
)
from basket_tui.native.stream import StreamAssembler


def _minimal_setup():
    """Minimal args: assembler, width, output_put, last_output_count."""
    assembler = StreamAssembler()
    width = 80
    out: list[str] = []
    output_put = out.append
    last_output_count: list[int] = [0]
    return assembler, width, out, output_put, last_output_count


def test_handle_text_delta_updates_assembler_buffer():
    assembler, *_ = _minimal_setup()
    handle_text_delta(assembler, "hi")
    assert assembler._buffer == "hi"


def test_handle_text_delta_sets_ui_state_phase_streaming():
    assembler, *_ = _minimal_setup()
    ui_state: dict[str, str] = {}
    handle_text_delta(assembler, "x", ui_state=ui_state)
    assert ui_state["phase"] == "streaming"


def test_handle_thinking_delta_updates_assembler():
    assembler, *_ = _minimal_setup()
    handle_thinking_delta(assembler, "think")
    assert assembler._thinking_buffer == "think"


def test_handle_tool_call_start_sets_current_tool():
    assembler, *_ = _minimal_setup()
    handle_tool_call_start(assembler, "bash", arguments={"cmd": "ls"})
    assert assembler._current_tool is not None
    assert assembler._current_tool["tool_name"] == "bash"
    assert assembler._current_tool["arguments"] == {"cmd": "ls"}


def test_handle_tool_call_start_sets_ui_state_phase_tool_running():
    assembler, *_ = _minimal_setup()
    ui_state: dict[str, str] = {}
    handle_tool_call_start(assembler, "bash", arguments={}, ui_state=ui_state)
    assert ui_state["phase"] == "tool_running"


def test_handle_tool_call_end_appends_tool_message():
    assembler, *_ = _minimal_setup()
    handle_tool_call_start(assembler, "read", arguments={})
    handle_tool_call_end(assembler, "read", result="file content", error=None)
    tool_msgs = [m for m in assembler.messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert "read" in tool_msgs[0]["content"]
    assert "file content" in tool_msgs[0]["content"]


def test_handle_tool_call_end_with_error():
    assembler, *_ = _minimal_setup()
    handle_tool_call_start(assembler, "bash", arguments={})
    handle_tool_call_end(assembler, "bash", result=None, error="failed")
    tool_msgs = [m for m in assembler.messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert "error" in tool_msgs[0]["content"] or "failed" in tool_msgs[0]["content"]


def test_handle_agent_complete_commits_and_renders():
    assembler, width, out, output_put, last_output_count = _minimal_setup()
    handle_text_delta(assembler, "Hi")
    handle_agent_complete(assembler, width, output_put, last_output_count)
    assert len(assembler.messages) == 1
    assert assembler.messages[0]["role"] == "assistant"
    assert assembler.messages[0]["content"] == "Hi"
    assert last_output_count[0] == 1
    assert len(out) >= 1


def test_handle_agent_complete_sets_ui_state_phase_idle():
    assembler, width, out, output_put, last_output_count = _minimal_setup()
    ui_state: dict[str, str] = {}
    handle_text_delta(assembler, "x", ui_state=ui_state)
    handle_agent_complete(assembler, width, output_put, last_output_count, ui_state=ui_state)
    assert ui_state["phase"] == "idle"


def test_handle_agent_error_prints_message():
    _, _, out, output_put, _ = _minimal_setup()
    handle_agent_error(output_put, "Something failed")
    assert len(out) == 1
    assert "Something failed" in out[0]
    assert "[system]" in out[0] or "Agent error" in out[0]


def test_handle_agent_error_sets_ui_state_phase_error():
    assembler, *_ = _minimal_setup()
    ui_state: dict[str, str] = {}
    handle_agent_error(lambda _: None, "err", ui_state=ui_state)
    assert ui_state["phase"] == "error"


def test_handle_session_switched_updates_header_and_output():
    header_state: dict[str, str] = {}
    out: list[str] = []
    output_put = out.append
    handle_session_switched(header_state, output_put, "s1")
    assert header_state["session"] == "s1"
    assert len(out) == 1
    assert "s1" in out[0]


def test_handle_session_switched_empty_sid_no_update():
    header_state: dict[str, str] = {"session": "old"}
    out: list[str] = []
    output_put = out.append
    handle_session_switched(header_state, output_put, "")
    assert header_state["session"] == "old"
    assert len(out) == 0


def test_handle_session_switched_none_header_state():
    out: list[str] = []
    output_put = out.append
    handle_session_switched(None, output_put, "s2")
    assert len(out) == 1
    assert "s2" in out[0]


def test_handle_agent_switched_updates_header_and_output():
    header_state: dict[str, str] = {}
    out: list[str] = []
    output_put = out.append
    handle_agent_switched(header_state, output_put, "explore")
    assert header_state["agent"] == "explore"
    assert len(out) == 1
    assert "explore" in out[0]


def test_handle_agent_switched_empty_name_no_update():
    header_state: dict[str, str] = {"agent": "old"}
    out: list[str] = []
    output_put = out.append
    handle_agent_switched(header_state, output_put, "")
    assert header_state["agent"] == "old"
    assert len(out) == 0


def test_handle_agent_aborted_clears_assembler_and_prints():
    assembler, _, out, output_put, _ = _minimal_setup()
    handle_text_delta(assembler, "x")
    handle_tool_call_start(assembler, "bash", arguments={})
    handle_agent_aborted(assembler, output_put)
    assert assembler._buffer == ""
    assert assembler._thinking_buffer == ""
    assert assembler._current_tool is None
    assert any("Aborted" in line for line in out)

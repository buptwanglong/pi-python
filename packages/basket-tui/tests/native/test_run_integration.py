"""Integration test for native run: dispatch of WebSocket events produces expected output."""

import re

import pytest

from basket_tui.native.handle.dispatch import _dispatch_ws_message
from basket_tui.native.pipeline import StreamAssembler, stream_preview_lines

_ANSI = re.compile(r"\x1b\[[0-9;]*m|\x1b\]8;;.*?\x1b\\\\")


def _strip_ansi(s: str) -> str:
    return _ANSI.sub("", s)


def test_dispatch_text_delta_agent_complete_prints_assistant_line():
    """Simulate WebSocket stream: text_delta + agent_complete; assert output contains assistant text."""
    assembler = StreamAssembler()
    width = 80
    printed: list[str] = []
    output_put = printed.append
    last_output_count: list[int] = [0]

    _dispatch_ws_message(
        {"type": "text_delta", "delta": "Hello "}, assembler, width, output_put, last_output_count
    )
    _dispatch_ws_message(
        {"type": "text_delta", "delta": "world"}, assembler, width, output_put, last_output_count
    )
    _dispatch_ws_message({"type": "agent_complete"}, assembler, width, output_put, last_output_count)

    assert len(assembler.messages) == 1
    assert assembler.messages[0]["content"] == "Hello world"
    combined = _strip_ansi(" ".join(printed))
    assert "Hello" in combined and "world" in combined, f"Expected 'Hello world' in output: {combined!r}"


def test_dispatch_tool_call_then_agent_complete_prints_tool_block():
    """Simulate tool_call_start, tool_call_end, agent_complete; assert output contains tool name or result."""
    assembler = StreamAssembler()
    width = 80
    printed: list[str] = []
    output_put = printed.append
    last_output_count: list[int] = [0]

    _dispatch_ws_message(
        {"type": "tool_call_start", "tool_name": "bash", "arguments": {"cmd": "ls"}},
        assembler,
        width,
        output_put,
        last_output_count,
    )
    _dispatch_ws_message(
        {"type": "tool_call_end", "tool_name": "bash", "result": "file1.txt", "error": None},
        assembler,
        width,
        output_put,
        last_output_count,
    )
    _dispatch_ws_message({"type": "agent_complete"}, assembler, width, output_put, last_output_count)

    assert len(assembler.messages) == 1
    assert assembler.messages[0].get("role") == "tool"
    combined = _strip_ansi(" ".join(printed))
    assert "bash" in combined or "file1.txt" in combined, (
        f"Expected tool name or result in output: {combined!r}"
    )


def test_dispatch_multiple_tools_then_assistant_in_one_turn():
    """One turn: tool A, tool B, then assistant text; assert messages and output order."""
    assembler = StreamAssembler()
    width = 80
    printed: list[str] = []
    output_put = printed.append
    last_output_count: list[int] = [0]

    _dispatch_ws_message(
        {"type": "tool_call_start", "tool_name": "bash", "arguments": {"cmd": "ls"}},
        assembler,
        width,
        output_put,
        last_output_count,
    )
    _dispatch_ws_message(
        {"type": "tool_call_end", "tool_name": "bash", "result": "file1", "error": None},
        assembler,
        width,
        output_put,
        last_output_count,
    )
    _dispatch_ws_message(
        {"type": "tool_call_start", "tool_name": "read", "arguments": {"path": "x"}},
        assembler,
        width,
        output_put,
        last_output_count,
    )
    _dispatch_ws_message(
        {"type": "tool_call_end", "tool_name": "read", "result": "content", "error": None},
        assembler,
        width,
        output_put,
        last_output_count,
    )
    _dispatch_ws_message(
        {"type": "text_delta", "delta": "Done."},
        assembler,
        width,
        output_put,
        last_output_count,
    )
    _dispatch_ws_message({"type": "agent_complete"}, assembler, width, output_put, last_output_count)

    assert len(assembler.messages) == 3
    assert assembler.messages[0].get("role") == "tool"
    assert "bash" in assembler.messages[0]["content"]
    assert assembler.messages[1].get("role") == "tool"
    assert "read" in assembler.messages[1]["content"]
    assert assembler.messages[2].get("role") == "assistant"
    assert assembler.messages[2]["content"] == "Done."

    combined = _strip_ansi(" ".join(printed))
    assert "bash" in combined
    assert "read" in combined or "content" in combined
    assert "Done." in combined
    # Order: tool A, tool B, assistant
    pos_bash = combined.find("bash")
    pos_read = combined.find("read")
    pos_done = combined.find("Done.")
    assert pos_bash >= 0 and pos_read >= 0 and pos_done >= 0
    assert pos_bash < pos_done and pos_read < pos_done


def test_dispatch_two_rounds_agent_complete():
    """Two rounds: first assistant message, then second; assert both in output in order."""
    assembler = StreamAssembler()
    width = 80
    printed: list[str] = []
    output_put = printed.append
    last_output_count: list[int] = [0]

    _dispatch_ws_message(
        {"type": "text_delta", "delta": "First"},
        assembler,
        width,
        output_put,
        last_output_count,
    )
    _dispatch_ws_message({"type": "agent_complete"}, assembler, width, output_put, last_output_count)

    _dispatch_ws_message(
        {"type": "text_delta", "delta": "Second"},
        assembler,
        width,
        output_put,
        last_output_count,
    )
    _dispatch_ws_message({"type": "agent_complete"}, assembler, width, output_put, last_output_count)

    assert len(assembler.messages) == 2
    assert assembler.messages[0]["content"] == "First"
    assert assembler.messages[1]["content"] == "Second"
    assert last_output_count[0] == 2

    combined = _strip_ansi(" ".join(printed))
    assert "First" in combined and "Second" in combined
    assert combined.find("First") < combined.find("Second")


def test_streaming_overlay_get_body_lines_includes_preview_when_phase_streaming():
    """When phase is streaming and buffer non-empty, get_body_lines logic returns body + stream preview."""
    assembler = StreamAssembler()
    width = 80
    body_lines: list[str] = ["existing line"]
    ui_state: dict[str, str] = {"phase": "streaming"}

    # Simulate text_delta so buffer has content
    _dispatch_ws_message(
        {"type": "text_delta", "delta": "Streaming "},
        assembler,
        width,
        body_lines.append,
        [0],
        ui_state=ui_state,
    )
    _dispatch_ws_message(
        {"type": "text_delta", "delta": "content"},
        assembler,
        width,
        body_lines.append,
        [0],
        ui_state=ui_state,
    )

    # Replicate get_body_lines() logic from run.py
    def get_body_lines() -> list[str]:
        base = list(body_lines)
        if ui_state.get("phase") == "streaming" and assembler._buffer:
            base.extend(stream_preview_lines(assembler._buffer, width))
        return base

    lines = get_body_lines()
    assert lines[0] == "existing line"
    assert any("Streaming" in ln and "content" in ln for ln in lines[1:]) or (
        "Streaming content" in " ".join(lines[1:])
    )


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

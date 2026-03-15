"""Integration test for native run: dispatch of WebSocket events produces expected output."""

import re

import pytest

from basket_tui.native.handle.dispatch import _dispatch_ws_message
from basket_tui.native.pipeline import StreamAssembler

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

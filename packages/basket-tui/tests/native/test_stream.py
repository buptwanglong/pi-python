"""Tests for native stream assembler."""

import pytest

from basket_tui.native.pipeline import StreamAssembler


def test_text_delta_and_agent_complete_produce_assistant_message():
    """After text_delta('Hello'), text_delta(' world'), agent_complete(), messages has one assistant message."""
    a = StreamAssembler()
    a.text_delta("Hello")
    a.text_delta(" world")
    a.agent_complete()
    assert len(a.messages) == 1
    assert a.messages[0]["role"] == "assistant"
    assert a.messages[0]["content"] == "Hello world"


def test_tool_call_start_and_end_add_tool_block():
    """tool_call_start('bash', {...}) and tool_call_end('bash', result='ok') add a tool block to state."""
    a = StreamAssembler()
    a.tool_call_start("bash", {"command": "echo hi"})
    a.tool_call_end("bash", result="ok", error=None)
    # Should have one tool message
    tool_msgs = [m for m in a.messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert "bash" in tool_msgs[0]["content"]
    assert "ok" in tool_msgs[0]["content"]


def test_multiple_tool_calls_add_multiple_tool_messages():
    """Multiple tool_call_start/end pairs add multiple tool messages."""
    a = StreamAssembler()
    a.tool_call_start("bash", {})
    a.tool_call_end("bash", result="ok1")
    a.tool_call_start("read", {"path": "f"})
    a.tool_call_end("read", result="content")
    tool_msgs = [m for m in a.messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 2
    assert "bash" in tool_msgs[0]["content"] and "ok1" in tool_msgs[0]["content"]
    assert "read" in tool_msgs[1]["content"]


def test_thinking_delta_and_agent_complete_clears_buffers():
    """thinking_delta is accumulated; agent_complete commits only text buffer and clears thinking."""
    a = StreamAssembler()
    a.thinking_delta("think ")
    a.thinking_delta("more")
    a.text_delta("reply")
    a.agent_complete()
    assert len(a.messages) == 1
    assert a.messages[0]["role"] == "assistant"
    assert a.messages[0]["content"] == "reply"
    assert getattr(a, "_thinking_buffer", "") == ""
    assert getattr(a, "_buffer", "") == ""


def test_flush_buffer_commits_and_clears():
    """flush_buffer() commits non-empty _buffer as assistant message, clears buffer, returns True."""
    a = StreamAssembler()
    a.text_delta("Hello")
    a.text_delta(" world")
    result = a.flush_buffer()
    assert result is True
    assert len(a.messages) == 1
    assert a.messages[0] == {"role": "assistant", "content": "Hello world"}
    assert a._buffer == ""


def test_flush_buffer_empty_noop():
    """flush_buffer() on empty buffer returns False and adds no message."""
    a = StreamAssembler()
    result = a.flush_buffer()
    assert result is False
    assert len(a.messages) == 0
    assert a._buffer == ""

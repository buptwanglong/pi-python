"""Tests for native stream assembler."""

import pytest

from basket_tui.native.stream import StreamAssembler


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

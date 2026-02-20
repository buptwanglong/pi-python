"""Tests for trajectory recorder."""

import pytest

from pi_trajectory import TrajectoryRecorder, TaskTrajectory


def _make_state_with_turns():
    """Build AgentState with 2 assistant turns; turn 2 had a bash tool call."""
    from pi_ai.types import (
        AssistantMessage,
        Context,
        StopReason,
        TextContent,
        ToolResultMessage,
        UserMessage,
    )
    from pi_agent.types import AgentState
    from pi_ai.types import Model

    model = Model(
        id="test-model",
        name="Test",
        api="test",
        provider="anthropic",
        base_url="",
        context_window=4096,
        max_tokens=1024,
    )
    user_msg = UserMessage(role="user", content="List files", timestamp=1000)
    asst1 = AssistantMessage(
        role="assistant",
        content=[TextContent(type="text", text="I'll run ls.")],
        api="test",
        provider="anthropic",
        model="test-model",
        stop_reason=StopReason.TOOL_USE,
        timestamp=1001,
    )
    tool_result = ToolResultMessage(
        role="toolResult",
        tool_call_id="tc1",
        tool_name="bash",
        content=[TextContent(type="text", text="file1.txt\nfile2.txt")],
        timestamp=1002,
    )
    asst2 = AssistantMessage(
        role="assistant",
        content=[TextContent(type="text", text="Here are the files: file1.txt, file2.txt.")],
        api="test",
        provider="anthropic",
        model="test-model",
        stop_reason=StopReason.STOP,
        timestamp=1003,
    )
    context = Context(
        system_prompt="You are helpful.",
        messages=[user_msg, asst1, tool_result, asst2],
        tools=[],
    )
    return AgentState(model=model, context=context)


def test_recorder_start_task():
    r = TrajectoryRecorder(task_id="t1")
    r.start_task("user question")
    r.on_event({"type": "agent_complete", "total_turns": 1, "final_message": {"content": [{"type": "text", "text": "Hi"}]}})
    r.finalize(None)
    tr = r.get_trajectory()
    assert tr.task_id == "t1"
    assert tr.user_input == "user question"
    assert tr.success is True
    assert tr.total_turns == 1
    assert tr.final_message_text == "Hi"


def test_recorder_error():
    r = TrajectoryRecorder()
    r.start_task("q")
    r.on_event({"type": "agent_error", "error": "Something broke"})
    r.finalize(None)
    tr = r.get_trajectory()
    assert tr.success is False
    assert tr.error_message == "Something broke"


def test_recorder_tool_calls():
    r = TrajectoryRecorder()
    r.start_task("read file")
    r.on_event({"type": "agent_turn_start", "turn_number": 1})
    r.on_event({"type": "agent_turn_end", "turn_number": 1, "has_tool_calls": True})
    r.on_event({
        "type": "agent_tool_call_end",
        "tool_name": "read",
        "tool_call_id": "tc1",
        "arguments": {"path": "/tmp/x"},
        "result": "content",
        "error": None,
    })
    r.on_event({"type": "agent_turn_start", "turn_number": 2})
    r.on_event({"type": "agent_turn_end", "turn_number": 2, "has_tool_calls": False})
    r.on_event({"type": "agent_complete", "total_turns": 2})
    r.finalize(None)
    tr = r.get_trajectory()
    assert tr.total_turns == 2
    assert len(tr.turns) == 0  # no state so no assistant messages
    # But _turn_tool_calls has turn 1
    assert 1 in r._turn_tool_calls
    assert len(r._turn_tool_calls[1]) == 1
    assert r._turn_tool_calls[1][0].tool_name == "read"


def test_recorder_tool_calls_and_input_messages_with_state():
    """Full event sequence + state: turn 2 has tool_calls with result; each turn has input_messages."""
    state = _make_state_with_turns()
    r = TrajectoryRecorder(task_id="full")
    r.start_task("List files")
    # Real order: turn 1 (no tool), turn 2 (tool bash), turn 3 (final)
    r.on_event({"type": "agent_turn_start", "turn_number": 1})
    r.on_event({"type": "agent_turn_end", "turn_number": 1, "has_tool_calls": False})
    r.on_event({"type": "agent_turn_start", "turn_number": 2})
    r.on_event({"type": "agent_turn_end", "turn_number": 2, "has_tool_calls": True})
    r.on_event({
        "type": "agent_tool_call_end",
        "tool_name": "bash",
        "tool_call_id": "tc1",
        "arguments": {"command": "ls"},
        "result": {"stdout": "file1.txt\nfile2.txt", "exit_code": 0},
        "error": None,
    })
    r.on_event({"type": "agent_turn_start", "turn_number": 3})
    r.on_event({"type": "agent_turn_end", "turn_number": 3, "has_tool_calls": False})
    r.on_event({"type": "agent_complete", "total_turns": 3})
    r.finalize(state)
    tr = r.get_trajectory()
    assert len(tr.turns) == 2  # 2 assistant messages in state
    # Turn 2 (index 1) had the bash tool call
    assert len(tr.turns[1].tool_calls) == 1
    assert tr.turns[1].tool_calls[0].tool_name == "bash"
    assert tr.turns[1].tool_calls[0].result_summary is not None
    assert "file1.txt" in tr.turns[1].tool_calls[0].result_summary
    # input_messages: turn 1 = [user], turn 2 = [user, asst1, tool_result]
    assert len(tr.turns[0].input_messages) == 1
    assert tr.turns[0].input_messages[0].get("role") == "user"
    assert len(tr.turns[1].input_messages) == 3
    assert tr.turns[1].input_messages[0].get("role") == "user"
    assert tr.turns[1].input_messages[1].get("role") == "assistant"
    assert tr.turns[1].input_messages[2].get("role") == "toolResult"

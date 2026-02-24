"""Tests for trajectory schema."""

import pytest

from basket_trajectory import TaskTrajectory, TurnRecord, ToolCallRecord


def test_tool_call_record():
    r = ToolCallRecord(
        tool_name="read",
        tool_call_id="tc1",
        arguments={"path": "/tmp/foo"},
        result_summary="file content",
        error=None,
    )
    assert r.tool_name == "read"
    assert r.model_dump(mode="json")


def test_turn_record():
    t = TurnRecord(
        turn_index=1,
        input_messages=[],
        assistant_message={"role": "assistant", "content": []},
        tool_calls=[],
    )
    assert t.turn_index == 1
    assert t.input_messages == []
    assert t.model_dump(mode="json")


def test_turn_record_default_input_messages():
    """TurnRecord accepts missing input_messages (defaults to [])."""
    t = TurnRecord(
        turn_index=1,
        assistant_message={"role": "assistant", "content": []},
        tool_calls=[],
    )
    assert t.input_messages == []


def test_task_trajectory_roundtrip():
    tr = TaskTrajectory(
        task_id="task_123",
        started_at=1000.0,
        ended_at=1005.0,
        model_provider="anthropic",
        model_id="claude-3-5-sonnet",
        success=True,
        user_input="Hello",
        system_prompt="You are helpful.",
        tool_names=["read", "bash"],
        turns=[],
        final_message_text="Hi there.",
        total_turns=1,
        total_usage={"input": 10, "output": 20, "total_tokens": 30, "cost_total": 0.01},
    )
    data = tr.model_dump(mode="json")
    loaded = TaskTrajectory.model_validate(data)
    assert loaded.task_id == tr.task_id
    assert loaded.success == tr.success
    assert loaded.user_input == tr.user_input

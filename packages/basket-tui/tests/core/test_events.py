"""
Tests for Event Definitions

Events are dataclasses with timestamp.
"""

import pytest
import time
from basket_tui.core.events import (
    Event,
    TextDeltaEvent,
    ThinkingDeltaEvent,
    ToolCallStartEvent,
    ToolCallEndEvent,
    AgentCompleteEvent,
    AgentErrorEvent,
    UserInputEvent,
    SessionSwitchEvent,
    PhaseChangedEvent,
)
from basket_tui.core.state_machine import Phase


class TestEvent:
    """Test suite for base Event class"""

    def test_event_has_timestamp(self):
        """Event should have default timestamp"""
        before = time.time()
        event = Event()
        after = time.time()

        assert before <= event.timestamp <= after

    def test_event_with_custom_timestamp(self):
        """Event should accept custom timestamp"""
        custom_time = 1234567890.0
        event = Event(timestamp=custom_time)
        assert event.timestamp == custom_time


class TestAgentEvents:
    """Test suite for agent-related events"""

    def test_text_delta_event(self):
        """TextDeltaEvent should store delta"""
        event = TextDeltaEvent(delta="Hello")
        assert event.delta == "Hello"
        assert hasattr(event, "timestamp")

    def test_thinking_delta_event(self):
        """ThinkingDeltaEvent should store delta"""
        event = ThinkingDeltaEvent(delta="Analyzing...")
        assert event.delta == "Analyzing..."

    def test_tool_call_start_event(self):
        """ToolCallStartEvent should store tool info"""
        event = ToolCallStartEvent(
            tool_name="bash", arguments={"command": "ls"}
        )
        assert event.tool_name == "bash"
        assert event.arguments == {"command": "ls"}

    def test_tool_call_end_event_success(self):
        """ToolCallEndEvent should store result"""
        event = ToolCallEndEvent(
            tool_name="bash", result="file1.txt\nfile2.txt", error=None
        )
        assert event.tool_name == "bash"
        assert event.result == "file1.txt\nfile2.txt"
        assert event.error is None

    def test_tool_call_end_event_error(self):
        """ToolCallEndEvent should store error"""
        event = ToolCallEndEvent(
            tool_name="bash", result=None, error="Command failed"
        )
        assert event.tool_name == "bash"
        assert event.result is None
        assert event.error == "Command failed"

    def test_agent_complete_event(self):
        """AgentCompleteEvent should exist"""
        event = AgentCompleteEvent()
        assert hasattr(event, "timestamp")

    def test_agent_error_event(self):
        """AgentErrorEvent should store error message"""
        event = AgentErrorEvent(error="Connection timeout")
        assert event.error == "Connection timeout"


class TestUIEvents:
    """Test suite for UI-related events"""

    def test_user_input_event(self):
        """UserInputEvent should store text"""
        event = UserInputEvent(text="Hello Claude")
        assert event.text == "Hello Claude"

    def test_session_switch_event(self):
        """SessionSwitchEvent should store session_id"""
        event = SessionSwitchEvent(session_id="abc123")
        assert event.session_id == "abc123"

    def test_phase_changed_event(self):
        """PhaseChangedEvent should store old and new phases"""
        event = PhaseChangedEvent(
            old_phase=Phase.IDLE, new_phase=Phase.STREAMING
        )
        assert event.old_phase == Phase.IDLE
        assert event.new_phase == Phase.STREAMING

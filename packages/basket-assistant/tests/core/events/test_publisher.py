"""Tests for EventPublisher.

Tests event distribution to subscribers, error handling, and
subscribe/unsubscribe lifecycle.
"""

import pytest
from unittest.mock import Mock, MagicMock
from types import SimpleNamespace

from basket_assistant.core.events import EventPublisher
from basket_agent.types import (
    AgentEventToolCallStart,
    AgentEventToolCallEnd,
    AgentEventTurnStart,
    AgentEventComplete,
    AgentEventError,
)


class TestEventPublisher:
    """Test suite for EventPublisher."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock AssistantAgent (inner ``agent`` has ``.on``)."""
        assistant = Mock()
        assistant.agent = Mock()
        assistant.agent.on = Mock()
        return assistant

    @pytest.fixture
    def publisher(self, mock_agent):
        """Create an EventPublisher with a mock agent."""
        return EventPublisher(mock_agent)

    def test_publisher_subscribes_to_agent_events(self, mock_agent):
        """Test that EventPublisher subscribes to all agent events on initialization."""
        publisher = EventPublisher(mock_agent)

        # Verify all expected subscriptions
        expected_calls = [
            "text_delta",
            "thinking_delta",
            "agent_tool_call_start",
            "agent_tool_call_end",
            "agent_turn_start",
            "agent_turn_end",
            "agent_complete",
            "agent_error",
        ]

        assert mock_agent.agent.on.call_count == len(expected_calls)

        # Check that each event type was subscribed to
        called_events = [call[0][0] for call in mock_agent.agent.on.call_args_list]
        for event_type in expected_calls:
            assert event_type in called_events

    def test_subscribe_and_receive_text_delta(self, publisher, mock_agent):
        """Test subscribing to text_delta events."""
        handler = Mock()
        publisher.subscribe("text_delta", handler)

        # Simulate agent emitting text_delta event
        # Publisher uses a single handler (_on_agent_event) for all types
        text_delta_handler = None
        for call in mock_agent.agent.on.call_args_list:
            if call[0][0] == "text_delta":
                text_delta_handler = call[0][1]
                break

        assert text_delta_handler is not None

        # Emit typed event
        event = SimpleNamespace(type="text_delta", delta="hello")
        text_delta_handler(event)

        # Verify handler was called with the typed event
        handler.assert_called_once()
        received = handler.call_args[0][0]
        assert received.delta == "hello"
        assert received.type == "text_delta"

    def test_subscribe_multiple_handlers(self, publisher, mock_agent):
        """Test that multiple handlers can subscribe to the same event."""
        handler1 = Mock()
        handler2 = Mock()
        handler3 = Mock()

        publisher.subscribe("text_delta", handler1)
        publisher.subscribe("text_delta", handler2)
        publisher.subscribe("text_delta", handler3)

        # Get text_delta handler
        text_delta_handler = None
        for call in mock_agent.agent.on.call_args_list:
            if call[0][0] == "text_delta":
                text_delta_handler = call[0][1]
                break

        # Emit typed event
        event = SimpleNamespace(type="text_delta", delta="test")
        text_delta_handler(event)

        # All handlers should be called
        handler1.assert_called_once()
        handler2.assert_called_once()
        handler3.assert_called_once()

    def test_unsubscribe(self, publisher, mock_agent):
        """Test unsubscribing from events."""
        handler1 = Mock()
        handler2 = Mock()

        publisher.subscribe("text_delta", handler1)
        publisher.subscribe("text_delta", handler2)
        publisher.unsubscribe("text_delta", handler1)

        # Get handler
        text_delta_handler = None
        for call in mock_agent.agent.on.call_args_list:
            if call[0][0] == "text_delta":
                text_delta_handler = call[0][1]
                break

        # Emit typed event
        event = SimpleNamespace(type="text_delta", delta="test")
        text_delta_handler(event)

        # Only handler2 should be called
        handler1.assert_not_called()
        handler2.assert_called_once()

    def test_handler_exception_doesnt_affect_others(self, publisher, mock_agent):
        """Test that exception in one handler doesn't prevent others from running."""
        handler1 = Mock(side_effect=Exception("Handler 1 failed"))
        handler2 = Mock()
        handler3 = Mock()

        publisher.subscribe("text_delta", handler1)
        publisher.subscribe("text_delta", handler2)
        publisher.subscribe("text_delta", handler3)

        # Get handler
        text_delta_handler = None
        for call in mock_agent.agent.on.call_args_list:
            if call[0][0] == "text_delta":
                text_delta_handler = call[0][1]
                break

        # Emit typed event - should not raise
        event = SimpleNamespace(type="text_delta", delta="test")
        text_delta_handler(event)

        # handler1 raised exception, but 2 and 3 should still be called
        handler1.assert_called_once()
        handler2.assert_called_once()
        handler3.assert_called_once()

    def test_tool_call_start_event(self, publisher, mock_agent):
        """Test receiving agent_tool_call_start typed events."""
        handler = Mock()
        publisher.subscribe("agent_tool_call_start", handler)

        # Get handler
        tool_call_handler = None
        for call in mock_agent.agent.on.call_args_list:
            if call[0][0] == "agent_tool_call_start":
                tool_call_handler = call[0][1]
                break

        # Emit typed event
        event = AgentEventToolCallStart(
            tool_name="bash",
            arguments={"command": "ls -la"},
            tool_call_id="call_123",
        )
        tool_call_handler(event)

        # Verify
        handler.assert_called_once()
        received = handler.call_args[0][0]
        assert isinstance(received, AgentEventToolCallStart)
        assert received.tool_name == "bash"
        assert received.arguments == {"command": "ls -la"}
        assert received.tool_call_id == "call_123"

    def test_tool_call_end_event(self, publisher, mock_agent):
        """Test receiving agent_tool_call_end typed events."""
        handler = Mock()
        publisher.subscribe("agent_tool_call_end", handler)

        # Get handler
        tool_call_handler = None
        for call in mock_agent.agent.on.call_args_list:
            if call[0][0] == "agent_tool_call_end":
                tool_call_handler = call[0][1]
                break

        # Emit typed event with result
        event = AgentEventToolCallEnd(
            tool_name="bash",
            result="output here",
            error=None,
            tool_call_id="call_123",
        )
        tool_call_handler(event)

        # Verify
        handler.assert_called_once()
        received = handler.call_args[0][0]
        assert isinstance(received, AgentEventToolCallEnd)
        assert received.tool_name == "bash"
        assert received.result == "output here"
        assert received.error is None

    def test_tool_call_end_with_error(self, publisher, mock_agent):
        """Test tool call end event with error."""
        handler = Mock()
        publisher.subscribe("agent_tool_call_end", handler)

        # Get handler
        tool_call_handler = None
        for call in mock_agent.agent.on.call_args_list:
            if call[0][0] == "agent_tool_call_end":
                tool_call_handler = call[0][1]
                break

        # Emit typed event with error
        event = AgentEventToolCallEnd(
            tool_name="bash",
            result=None,
            error="Command failed",
            tool_call_id="call_123",
        )
        tool_call_handler(event)

        # Verify
        handler.assert_called_once()
        received = handler.call_args[0][0]
        assert isinstance(received, AgentEventToolCallEnd)
        assert received.error == "Command failed"

    def test_turn_start_event(self, publisher, mock_agent):
        """Test receiving agent_turn_start typed events."""
        handler = Mock()
        publisher.subscribe("agent_turn_start", handler)

        # Get handler
        turn_handler = None
        for call in mock_agent.agent.on.call_args_list:
            if call[0][0] == "agent_turn_start":
                turn_handler = call[0][1]
                break

        # Emit typed event
        event = AgentEventTurnStart(turn_number=1)
        turn_handler(event)

        # Verify
        handler.assert_called_once()
        received = handler.call_args[0][0]
        assert isinstance(received, AgentEventTurnStart)
        assert received.turn_number == 1

    def test_agent_complete_event(self, publisher, mock_agent):
        """Test receiving agent_complete typed events."""
        handler = Mock()
        publisher.subscribe("agent_complete", handler)

        # Get handler
        complete_handler = None
        for call in mock_agent.agent.on.call_args_list:
            if call[0][0] == "agent_complete":
                complete_handler = call[0][1]
                break

        # Emit typed event (use SimpleNamespace since AgentEventComplete requires
        # final_message and total_turns which tests don't need)
        event = SimpleNamespace(type="agent_complete")
        complete_handler(event)

        # Verify
        handler.assert_called_once()
        received = handler.call_args[0][0]
        assert received.type == "agent_complete"

    def test_agent_error_event(self, publisher, mock_agent):
        """Test receiving agent_error typed events."""
        handler = Mock()
        publisher.subscribe("agent_error", handler)

        # Get handler
        error_handler = None
        for call in mock_agent.agent.on.call_args_list:
            if call[0][0] == "agent_error":
                error_handler = call[0][1]
                break

        # Emit typed event
        event = AgentEventError(error="Something went wrong")
        error_handler(event)

        # Verify
        handler.assert_called_once()
        received = handler.call_args[0][0]
        assert isinstance(received, AgentEventError)
        assert received.error == "Something went wrong"

    def test_cleanup(self, publisher):
        """Test cleanup clears all subscribers."""
        handler = Mock()
        publisher.subscribe("text_delta", handler)

        assert len(publisher._subscribers.get("text_delta", [])) == 1

        publisher.cleanup()

        assert len(publisher._subscribers.get("text_delta", [])) == 0

    def test_subscribe_same_handler_twice(self, publisher):
        """Test that subscribing the same handler twice doesn't create duplicates."""
        handler = Mock()

        publisher.subscribe("text_delta", handler)
        publisher.subscribe("text_delta", handler)

        # Should only have one handler
        assert len(publisher._subscribers.get("text_delta", [])) == 1

"""Tests for TUIAdapter.

Tests forwarding events to TUI event bus.
"""

import pytest
from unittest.mock import Mock
from types import SimpleNamespace

from basket_assistant.adapters import TUIAdapter
from basket_assistant.core.events import EventPublisher
from basket_agent.types import (
    AgentEventToolCallStart,
    AgentEventToolCallEnd,
    AgentEventError,
)


class TestTUIAdapter:
    """Test suite for TUIAdapter."""

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

    @pytest.fixture
    def mock_event_bus(self):
        """Create a mock TUI event bus."""
        event_bus = Mock()
        event_bus.publish = Mock()
        return event_bus

    def test_adapter_subscribes_to_events(self, publisher, mock_event_bus):
        """Test that TUIAdapter subscribes to all events."""
        adapter = TUIAdapter(publisher, mock_event_bus)

        # Check subscriptions
        assert "text_delta" in publisher._subscribers
        assert "thinking_delta" in publisher._subscribers
        assert "agent_tool_call_start" in publisher._subscribers
        assert "agent_tool_call_end" in publisher._subscribers
        assert "agent_complete" in publisher._subscribers
        assert "agent_error" in publisher._subscribers

    def test_text_delta_forwarding(self, publisher, mock_event_bus):
        """Test forwarding text_delta to TUI event bus."""
        adapter = TUIAdapter(publisher, mock_event_bus)

        event = SimpleNamespace(type="text_delta", delta="Hello")
        adapter._on_text_delta(event)

        mock_event_bus.publish.assert_called_once_with(
            "assistant.text_delta", {"delta": "Hello"}
        )

    def test_thinking_delta_forwarding(self, publisher, mock_event_bus):
        """Test forwarding thinking_delta to TUI event bus."""
        adapter = TUIAdapter(publisher, mock_event_bus)

        event = SimpleNamespace(type="thinking_delta", delta="Thinking...")
        adapter._on_thinking_delta(event)

        mock_event_bus.publish.assert_called_once_with(
            "assistant.thinking_delta", {"delta": "Thinking..."}
        )

    def test_tool_call_start_forwarding(self, publisher, mock_event_bus):
        """Test forwarding tool_call_start to TUI event bus."""
        adapter = TUIAdapter(publisher, mock_event_bus)

        event = AgentEventToolCallStart(
            tool_name="bash",
            arguments={"command": "ls"},
            tool_call_id="call_123",
        )
        adapter._on_tool_call_start(event)

        mock_event_bus.publish.assert_called_once_with(
            "assistant.tool_call_start",
            {
                "tool_name": "bash",
                "arguments": {"command": "ls"},
                "tool_call_id": "call_123",
            },
        )

    def test_tool_call_end_forwarding(self, publisher, mock_event_bus):
        """Test forwarding tool_call_end to TUI event bus."""
        adapter = TUIAdapter(publisher, mock_event_bus)

        event = AgentEventToolCallEnd(
            tool_name="bash",
            result="output",
            error=None,
            tool_call_id="call_123",
        )
        adapter._on_tool_call_end(event)

        mock_event_bus.publish.assert_called_once_with(
            "assistant.tool_call_end",
            {
                "tool_name": "bash",
                "result": "output",
                "error": None,
                "tool_call_id": "call_123",
            },
        )

    def test_tool_call_end_with_error_forwarding(self, publisher, mock_event_bus):
        """Test forwarding tool_call_end with error to TUI event bus."""
        adapter = TUIAdapter(publisher, mock_event_bus)

        event = AgentEventToolCallEnd(
            tool_name="bash",
            result=None,
            error="Command failed",
            tool_call_id="call_123",
        )
        adapter._on_tool_call_end(event)

        mock_event_bus.publish.assert_called_once_with(
            "assistant.tool_call_end",
            {
                "tool_name": "bash",
                "result": None,
                "error": "Command failed",
                "tool_call_id": "call_123",
            },
        )

    def test_agent_complete_forwarding(self, publisher, mock_event_bus):
        """Test forwarding agent_complete to TUI event bus."""
        adapter = TUIAdapter(publisher, mock_event_bus)

        event = SimpleNamespace(type="agent_complete")
        adapter._on_agent_complete(event)

        mock_event_bus.publish.assert_called_once_with("assistant.agent_complete", {})

    def test_agent_error_forwarding(self, publisher, mock_event_bus):
        """Test forwarding agent_error to TUI event bus."""
        adapter = TUIAdapter(publisher, mock_event_bus)

        event = AgentEventError(error="Something went wrong")
        adapter._on_agent_error(event)

        mock_event_bus.publish.assert_called_once_with(
            "assistant.agent_error", {"error": "Something went wrong"}
        )

    def test_event_bus_exception_handling(self, publisher, mock_event_bus):
        """Test that exceptions from event bus are caught and logged."""
        mock_event_bus.publish.side_effect = Exception("Event bus failed")

        adapter = TUIAdapter(publisher, mock_event_bus)

        event = SimpleNamespace(type="text_delta", delta="test")

        # Should not raise
        adapter._on_text_delta(event)

        # Event bus should have been called
        mock_event_bus.publish.assert_called_once()

    def test_cleanup(self, publisher, mock_event_bus):
        """Test adapter cleanup."""
        adapter = TUIAdapter(publisher, mock_event_bus)
        adapter.cleanup()
        # Should not raise any errors

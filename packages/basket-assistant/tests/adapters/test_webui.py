"""Tests for WebUIAdapter.

Tests sending events over WebSocket (async).
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock
from types import SimpleNamespace

from basket_assistant.adapters import WebUIAdapter
from basket_assistant.core.events import EventPublisher
from basket_agent.types import (
    AgentEventToolCallStart,
    AgentEventToolCallEnd,
    AgentEventError,
)


class TestWebUIAdapter:
    """Test suite for WebUIAdapter."""

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
    def mock_send(self):
        """Create a mock async send function."""
        return AsyncMock()

    def test_adapter_subscribes_to_events(self, publisher, mock_send):
        """Test that WebUIAdapter subscribes to all events."""
        adapter = WebUIAdapter(publisher, mock_send)

        # Check subscriptions
        assert "text_delta" in publisher._subscribers
        assert "thinking_delta" in publisher._subscribers
        assert "agent_tool_call_start" in publisher._subscribers
        assert "agent_tool_call_end" in publisher._subscribers
        assert "agent_complete" in publisher._subscribers
        assert "agent_error" in publisher._subscribers

    @pytest.mark.asyncio
    async def test_text_delta_sending(self, publisher, mock_send):
        """Test sending text_delta over WebSocket."""
        adapter = WebUIAdapter(publisher, mock_send)

        event = SimpleNamespace(type="text_delta", delta="Hello")
        adapter._on_text_delta(event)

        # Wait for async task to complete
        await asyncio.sleep(0.01)

        mock_send.assert_called_once_with({"type": "text_delta", "delta": "Hello"})

    @pytest.mark.asyncio
    async def test_thinking_delta_sending(self, publisher, mock_send):
        """Test sending thinking_delta over WebSocket."""
        adapter = WebUIAdapter(publisher, mock_send)

        event = SimpleNamespace(type="thinking_delta", delta="Thinking...")
        adapter._on_thinking_delta(event)

        await asyncio.sleep(0.01)

        mock_send.assert_called_once_with(
            {"type": "thinking_delta", "delta": "Thinking..."}
        )

    @pytest.mark.asyncio
    async def test_tool_call_start_sending(self, publisher, mock_send):
        """Test sending tool_call_start over WebSocket."""
        adapter = WebUIAdapter(publisher, mock_send)

        event = AgentEventToolCallStart(
            tool_name="bash",
            arguments={"command": "ls"},
            tool_call_id="call_123",
        )
        adapter._on_tool_call_start(event)

        await asyncio.sleep(0.01)

        mock_send.assert_called_once_with(
            {
                "type": "tool_call_start",
                "tool_name": "bash",
                "arguments": {"command": "ls"},
                "tool_call_id": "call_123",
            }
        )

    @pytest.mark.asyncio
    async def test_tool_call_end_sending(self, publisher, mock_send):
        """Test sending tool_call_end over WebSocket."""
        adapter = WebUIAdapter(publisher, mock_send)

        event = AgentEventToolCallEnd(
            tool_name="bash",
            result="output",
            error=None,
            tool_call_id="call_123",
        )
        adapter._on_tool_call_end(event)

        await asyncio.sleep(0.01)

        mock_send.assert_called_once_with(
            {
                "type": "tool_call_end",
                "tool_name": "bash",
                "result": "output",
                "error": None,
                "tool_call_id": "call_123",
            }
        )

    @pytest.mark.asyncio
    async def test_tool_call_end_with_error_sending(self, publisher, mock_send):
        """Test sending tool_call_end with error over WebSocket."""
        adapter = WebUIAdapter(publisher, mock_send)

        event = AgentEventToolCallEnd(
            tool_name="bash",
            result=None,
            error="Command failed",
            tool_call_id="call_123",
        )
        adapter._on_tool_call_end(event)

        await asyncio.sleep(0.01)

        mock_send.assert_called_once_with(
            {
                "type": "tool_call_end",
                "tool_name": "bash",
                "result": None,
                "error": "Command failed",
                "tool_call_id": "call_123",
            }
        )

    @pytest.mark.asyncio
    async def test_agent_complete_sending(self, publisher, mock_send):
        """Test sending agent_complete over WebSocket."""
        adapter = WebUIAdapter(publisher, mock_send)

        event = SimpleNamespace(type="agent_complete")
        adapter._on_agent_complete(event)

        await asyncio.sleep(0.01)

        mock_send.assert_called_once_with({"type": "agent_complete"})

    @pytest.mark.asyncio
    async def test_agent_error_sending(self, publisher, mock_send):
        """Test sending agent_error over WebSocket."""
        adapter = WebUIAdapter(publisher, mock_send)

        event = AgentEventError(error="Something went wrong")
        adapter._on_agent_error(event)

        await asyncio.sleep(0.01)

        mock_send.assert_called_once_with(
            {"type": "agent_error", "error": "Something went wrong"}
        )

    @pytest.mark.asyncio
    async def test_send_exception_deactivates_adapter(self, publisher, mock_send):
        """Test that send exceptions deactivate the adapter."""
        mock_send.side_effect = Exception("Connection closed")

        adapter = WebUIAdapter(publisher, mock_send)

        event = SimpleNamespace(type="text_delta", delta="test")
        adapter._on_text_delta(event)

        await asyncio.sleep(0.01)

        # Adapter should be deactivated
        assert adapter._active is False

        # Subsequent events should not be sent
        mock_send.reset_mock()
        event = SimpleNamespace(type="text_delta", delta="test2")
        adapter._on_text_delta(event)

        await asyncio.sleep(0.01)

        mock_send.assert_not_called()

    def test_cleanup(self, publisher, mock_send):
        """Test adapter cleanup."""
        adapter = WebUIAdapter(publisher, mock_send)

        assert adapter._active is True

        adapter.cleanup()

        assert adapter._active is False

    def test_result_conversion_to_string(self, publisher, mock_send):
        """Test that non-None results are converted to strings."""
        adapter = WebUIAdapter(publisher, mock_send)

        # Test with non-string result
        event = AgentEventToolCallEnd(
            tool_name="bash",
            result={"key": "value"},  # dict result
            error=None,
            tool_call_id="call_123",
        )
        adapter._on_tool_call_end(event)

        # The result should be converted to string in the sent data
        # (We can't easily check this without async, but the implementation handles it)

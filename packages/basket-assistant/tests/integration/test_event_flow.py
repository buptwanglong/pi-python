"""Integration tests for event flow.

Tests the complete flow from agent events → EventPublisher → Adapters → UI.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from io import StringIO

from basket_assistant.core.events import EventPublisher
from basket_assistant.adapters import CLIAdapter, TUIAdapter, WebUIAdapter


class TestEventFlow:
    """Integration tests for end-to-end event flow."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock basket-agent."""
        agent = Mock()
        agent.on = Mock()
        return agent

    @pytest.fixture
    def publisher(self, mock_agent):
        """Create an EventPublisher."""
        return EventPublisher(mock_agent)

    def test_cli_mode_complete_flow(self, mock_agent, publisher):
        """Test complete flow in CLI mode."""
        import sys
        from io import StringIO

        # Create CLI adapter
        adapter = CLIAdapter(publisher, verbose=True)

        # Get event handlers
        text_delta_handler = None
        tool_start_handler = None
        tool_end_handler = None

        for call in mock_agent.on.call_args_list:
            event_type = call[0][0]
            handler = call[0][1]
            if event_type == "text_delta":
                text_delta_handler = handler
            elif event_type == "agent_tool_call_start":
                tool_start_handler = handler
            elif event_type == "agent_tool_call_end":
                tool_end_handler = handler

        # Simulate agent events
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            # Text streaming
            text_delta_handler({"delta": "Hello "})
            text_delta_handler({"delta": "world!"})

            # Tool call
            tool_start_handler(
                {
                    "tool_name": "bash",
                    "arguments": {"command": "ls"},
                    "tool_call_id": "call_1",
                }
            )

            tool_end_handler(
                {
                    "tool_name": "bash",
                    "result": "file1.txt\nfile2.txt",
                    "error": None,
                    "tool_call_id": "call_1",
                }
            )

            output = mock_stdout.getvalue()

            # Verify output contains expected text
            assert "Hello " in output
            assert "world!" in output
            assert "Tool: bash" in output

    def test_tui_mode_complete_flow(self, mock_agent, publisher):
        """Test complete flow in TUI mode."""
        # Create mock event bus
        mock_event_bus = Mock()
        mock_event_bus.publish = Mock()

        # Create TUI adapter
        adapter = TUIAdapter(publisher, mock_event_bus)

        # Get event handlers
        text_delta_handler = None
        tool_start_handler = None
        tool_end_handler = None

        for call in mock_agent.on.call_args_list:
            event_type = call[0][0]
            handler = call[0][1]
            if event_type == "text_delta":
                text_delta_handler = handler
            elif event_type == "agent_tool_call_start":
                tool_start_handler = handler
            elif event_type == "agent_tool_call_end":
                tool_end_handler = handler

        # Simulate agent events
        text_delta_handler({"delta": "Hello"})
        tool_start_handler(
            {
                "tool_name": "bash",
                "arguments": {"command": "ls"},
                "tool_call_id": "call_1",
            }
        )
        tool_end_handler(
            {
                "tool_name": "bash",
                "result": "output",
                "error": None,
                "tool_call_id": "call_1",
            }
        )

        # Verify event bus was called
        assert mock_event_bus.publish.call_count == 3

        # Check event types
        published_events = [call[0][0] for call in mock_event_bus.publish.call_args_list]
        assert "assistant.text_delta" in published_events
        assert "assistant.tool_call_start" in published_events
        assert "assistant.tool_call_end" in published_events

    @pytest.mark.asyncio
    async def test_webui_mode_complete_flow(self, mock_agent, publisher):
        """Test complete flow in WebUI mode."""
        # Create mock send function
        mock_send = AsyncMock()

        # Create WebUI adapter
        adapter = WebUIAdapter(publisher, mock_send)

        # Get event handlers
        text_delta_handler = None
        tool_start_handler = None
        tool_end_handler = None

        for call in mock_agent.on.call_args_list:
            event_type = call[0][0]
            handler = call[0][1]
            if event_type == "text_delta":
                text_delta_handler = handler
            elif event_type == "agent_tool_call_start":
                tool_start_handler = handler
            elif event_type == "agent_tool_call_end":
                tool_end_handler = handler

        # Simulate agent events
        text_delta_handler({"delta": "Hello"})
        tool_start_handler(
            {
                "tool_name": "bash",
                "arguments": {"command": "ls"},
                "tool_call_id": "call_1",
            }
        )
        tool_end_handler(
            {
                "tool_name": "bash",
                "result": "output",
                "error": None,
                "tool_call_id": "call_1",
            }
        )

        # Wait for async sends to complete
        await asyncio.sleep(0.1)

        # Verify send was called
        assert mock_send.call_count == 3

        # Check sent data types
        sent_data = [call[0][0] for call in mock_send.call_args_list]
        assert sent_data[0]["type"] == "text_delta"
        assert sent_data[1]["type"] == "tool_call_start"
        assert sent_data[2]["type"] == "tool_call_end"

    def test_multiple_adapters_simultaneously(self, mock_agent, publisher):
        """Test multiple adapters running simultaneously."""
        # Create CLI adapter
        cli_adapter = CLIAdapter(publisher, verbose=False)

        # Create TUI adapter
        mock_event_bus = Mock()
        tui_adapter = TUIAdapter(publisher, mock_event_bus)

        # Get text_delta handler
        text_delta_handler = None
        for call in mock_agent.on.call_args_list:
            if call[0][0] == "text_delta":
                text_delta_handler = call[0][1]
                break

        # Emit event
        import sys
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            text_delta_handler({"delta": "test"})

            # CLI should print
            assert "test" in mock_stdout.getvalue()

        # TUI should receive event
        mock_event_bus.publish.assert_called_once_with(
            "assistant.text_delta", {"delta": "test"}
        )

    def test_event_ordering(self, mock_agent, publisher):
        """Test that events maintain their order."""
        mock_event_bus = Mock()
        adapter = TUIAdapter(publisher, mock_event_bus)

        # Get handlers
        text_handler = None
        tool_start_handler = None
        tool_end_handler = None
        turn_start_handler = None

        for call in mock_agent.on.call_args_list:
            event_type = call[0][0]
            handler = call[0][1]
            if event_type == "text_delta":
                text_handler = handler
            elif event_type == "agent_tool_call_start":
                tool_start_handler = handler
            elif event_type == "agent_tool_call_end":
                tool_end_handler = handler
            elif event_type == "agent_turn_start":
                turn_start_handler = handler

        # Emit events in specific order
        turn_start_handler({"turn_number": 1})
        text_handler({"delta": "text1"})
        tool_start_handler(
            {"tool_name": "bash", "arguments": {}, "tool_call_id": "call_1"}
        )
        tool_end_handler(
            {"tool_name": "bash", "result": "ok", "error": None, "tool_call_id": "call_1"}
        )
        text_handler({"delta": "text2"})

        # Verify order
        published_events = [call[0][0] for call in mock_event_bus.publish.call_args_list]
        expected_order = [
            "assistant.turn_start",
            "assistant.text_delta",
            "assistant.tool_call_start",
            "assistant.tool_call_end",
            "assistant.text_delta",
        ]

        # Should receive events in order, but only subscribed events
        received_types = [e for e in published_events if e.startswith("assistant.")]
        assert received_types == [e for e in expected_order if e != "assistant.turn_start"]

    def test_adapter_isolation(self, mock_agent, publisher):
        """Test that error in one adapter doesn't affect others."""
        # Create failing TUI adapter
        mock_event_bus_fail = Mock()
        mock_event_bus_fail.publish.side_effect = Exception("Event bus crashed")
        failing_adapter = TUIAdapter(publisher, mock_event_bus_fail)

        # Create working TUI adapter
        mock_event_bus_ok = Mock()
        working_adapter = TUIAdapter(publisher, mock_event_bus_ok)

        # Get text_delta handler
        text_handler = None
        for call in mock_agent.on.call_args_list:
            if call[0][0] == "text_delta":
                text_handler = call[0][1]
                break

        # Emit event
        text_handler({"delta": "test"})

        # Failing adapter should have tried
        mock_event_bus_fail.publish.assert_called_once()

        # Working adapter should still work
        mock_event_bus_ok.publish.assert_called_once()


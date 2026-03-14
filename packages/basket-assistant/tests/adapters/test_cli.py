"""Tests for CLIAdapter.

Tests CLI output for different event types.
"""

import pytest
from unittest.mock import Mock, patch
from io import StringIO

from basket_assistant.adapters import CLIAdapter
from basket_assistant.core.events import (
    EventPublisher,
    TextDeltaEvent,
    ToolCallStartEvent,
    ToolCallEndEvent,
)


class TestCLIAdapter:
    """Test suite for CLIAdapter."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock basket-agent."""
        agent = Mock()
        agent.on = Mock()
        return agent

    @pytest.fixture
    def publisher(self, mock_agent):
        """Create an EventPublisher with a mock agent."""
        return EventPublisher(mock_agent)

    def test_adapter_subscribes_to_events(self, publisher):
        """Test that CLIAdapter subscribes to the correct events."""
        adapter = CLIAdapter(publisher, verbose=False)

        # Check subscriptions
        assert "text_delta" in publisher._subscribers
        assert "tool_call_start" in publisher._subscribers
        assert "tool_call_end" in publisher._subscribers
        assert len(publisher._subscribers["text_delta"]) == 1
        assert len(publisher._subscribers["tool_call_start"]) == 1
        assert len(publisher._subscribers["tool_call_end"]) == 1

    @patch("sys.stdout", new_callable=StringIO)
    def test_text_delta_output(self, mock_stdout, publisher):
        """Test that text_delta events are printed to stdout."""
        adapter = CLIAdapter(publisher, verbose=False)

        # Emit text_delta event
        event = TextDeltaEvent(delta="Hello, ")
        adapter._on_text_delta(event)

        event = TextDeltaEvent(delta="world!")
        adapter._on_text_delta(event)

        output = mock_stdout.getvalue()
        assert "Hello, " in output
        assert "world!" in output

    @patch("sys.stdout", new_callable=StringIO)
    def test_tool_call_start_verbose(self, mock_stdout, publisher):
        """Test tool_call_start with verbose=True."""
        adapter = CLIAdapter(publisher, verbose=True)

        event = ToolCallStartEvent(
            tool_name="bash",
            arguments={"command": "ls -la"},
            tool_call_id="call_123",
        )
        adapter._on_tool_call_start(event)

        output = mock_stdout.getvalue()
        assert "Tool: bash" in output
        assert "command=" in output

    @patch("sys.stdout", new_callable=StringIO)
    def test_tool_call_start_not_verbose(self, mock_stdout, publisher):
        """Test tool_call_start with verbose=False."""
        adapter = CLIAdapter(publisher, verbose=False)

        event = ToolCallStartEvent(
            tool_name="bash",
            arguments={"command": "ls -la"},
            tool_call_id="call_123",
        )
        adapter._on_tool_call_start(event)

        output = mock_stdout.getvalue()
        # Should not print anything in non-verbose mode
        assert "Tool: bash" not in output

    @patch("sys.stdout", new_callable=StringIO)
    def test_tool_call_end_with_error(self, mock_stdout, publisher):
        """Test tool_call_end event with error."""
        adapter = CLIAdapter(publisher, verbose=False)

        event = ToolCallEndEvent(
            tool_name="bash",
            result=None,
            error="Command failed: exit code 1",
            tool_call_id="call_123",
        )
        adapter._on_tool_call_end(event)

        output = mock_stdout.getvalue()
        assert "Error:" in output
        assert "Command failed" in output

    @patch("sys.stdout", new_callable=StringIO)
    def test_tool_call_end_without_error(self, mock_stdout, publisher):
        """Test tool_call_end event without error."""
        adapter = CLIAdapter(publisher, verbose=False)

        event = ToolCallEndEvent(
            tool_name="bash",
            result="success",
            error=None,
            tool_call_id="call_123",
        )
        adapter._on_tool_call_end(event)

        output = mock_stdout.getvalue()
        # Should not print anything for successful completion
        assert output == ""

    def test_format_tool_args_long_value(self, publisher):
        """Test formatting of tool arguments with long values."""
        adapter = CLIAdapter(publisher, verbose=True)

        event = ToolCallStartEvent(
            tool_name="bash",
            arguments={"command": "x" * 100},  # Very long command
            tool_call_id="call_123",
        )

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            adapter._on_tool_call_start(event)
            output = mock_stdout.getvalue()

            # Should be truncated
            assert "..." in output
            assert len(output) < 200  # Should be shorter than original

    def test_format_tool_args_multiple_keys(self, publisher):
        """Test formatting of tool arguments with multiple keys."""
        adapter = CLIAdapter(publisher, verbose=True)

        event = ToolCallStartEvent(
            tool_name="edit",
            arguments={
                "file_path": "/path/to/file.py",
                "old_string": "old",
                "new_string": "new",
            },
            tool_call_id="call_123",
        )

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            adapter._on_tool_call_start(event)
            output = mock_stdout.getvalue()

            # Should show file_path (first in the list)
            assert "file_path=" in output

    def test_empty_delta(self, publisher):
        """Test handling of empty delta."""
        adapter = CLIAdapter(publisher, verbose=False)

        event = TextDeltaEvent(delta="")

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            adapter._on_text_delta(event)
            output = mock_stdout.getvalue()

            # Should not print anything for empty delta
            assert output == ""

    def test_cleanup(self, publisher):
        """Test adapter cleanup."""
        adapter = CLIAdapter(publisher, verbose=False)
        adapter.cleanup()
        # Should not raise any errors

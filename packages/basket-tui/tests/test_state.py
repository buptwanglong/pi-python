"""
Tests for AppState class
"""

import pytest
import asyncio
from basket_tui.state import AppState, OutputCell
from textual.widgets import Static


def test_app_state_initialization():
    """Test AppState initializes with correct default values."""
    state = AppState()
    assert state.current_assistant_widget is None
    assert state.streaming_buffer == ""
    assert state.current_tool_widget is None
    assert state.current_thinking_widget is None
    assert state.agent_task is None
    assert state.phase == "idle"


def test_app_state_reset_streaming():
    """Test reset_streaming clears all streaming-related state."""
    state = AppState()
    state.current_assistant_widget = Static("test")
    state.streaming_buffer = "test buffer"
    state.current_tool_widget = Static("tool")
    state.current_thinking_widget = Static("thinking")

    state.reset_streaming()

    assert state.current_assistant_widget is None
    assert state.streaming_buffer == ""
    assert state.current_tool_widget is None
    assert state.current_thinking_widget is None


def test_app_state_reset_all():
    """Test reset_all clears all state including agent task."""
    state = AppState()
    state.current_assistant_widget = Static("test")
    state.streaming_buffer = "test buffer"
    state.phase = "streaming"
    # Just set a placeholder task without actually creating an async task
    state.agent_task = None  # In real usage, this would be an asyncio.Task

    state.reset_all()

    assert state.current_assistant_widget is None
    assert state.streaming_buffer == ""
    assert state.agent_task is None
    assert state.phase == "idle"


def test_has_active_assistant_widget():
    """Test has_active_assistant_widget returns correct boolean."""
    state = AppState()
    assert not state.has_active_assistant_widget()

    state.current_assistant_widget = Static("test")
    assert state.has_active_assistant_widget()


def test_has_active_tool_widget():
    """Test has_active_tool_widget returns correct boolean."""
    state = AppState()
    assert not state.has_active_tool_widget()

    state.current_tool_widget = Static("test")
    assert state.has_active_tool_widget()


def test_has_active_thinking_widget():
    """Test has_active_thinking_widget returns correct boolean."""
    state = AppState()
    assert not state.has_active_thinking_widget()

    state.current_thinking_widget = Static("test")
    assert state.has_active_thinking_widget()


@pytest.mark.asyncio
async def test_is_agent_running():
    """Test is_agent_running returns correct boolean."""
    state = AppState()
    assert not state.is_agent_running()

    # Create a task
    task = asyncio.create_task(asyncio.sleep(0.1))
    state.set_agent_task(task)
    assert state.is_agent_running()

    # Wait for task to complete
    await task
    assert not state.is_agent_running()


@pytest.mark.asyncio
async def test_cancel_agent_task():
    """Test cancel_agent_task cancels running task."""
    state = AppState()

    # No task - should return False
    assert not state.cancel_agent_task()

    # Create a long-running task
    task = asyncio.create_task(asyncio.sleep(10))
    state.set_agent_task(task)

    # Cancel task - should return True
    assert state.cancel_agent_task()

    # Verify task was cancelled
    with pytest.raises(asyncio.CancelledError):
        await task


def test_get_transcript_text():
    """Test get_transcript_text returns output_blocks + streaming tail."""
    state = AppState()
    state.output_blocks = ["hello", "world"]
    assert state.get_transcript_text() == "hello\n\nworld"

    state.streaming_assistant = True
    state.streaming_buffer = " x"
    assert state.get_transcript_text() == "hello\n\nworld\n\n x"


def test_get_transcript_blocks():
    """Test get_transcript_blocks returns (role, content) list and streaming tail."""
    state = AppState()
    state.output_blocks_with_role = [("user", "hi"), ("assistant", "ok")]
    assert state.get_transcript_blocks() == [("user", "hi"), ("assistant", "ok")]

    state.streaming_assistant = True
    state.streaming_buffer = " typing..."
    assert state.get_transcript_blocks() == [
        ("user", "hi"),
        ("assistant", "ok"),
        ("assistant", " typing..."),
    ]


def test_get_last_complete_message():
    """Test get_last_complete_message returns last non-empty block."""
    state = AppState()
    state.output_blocks = ["a", "", "c"]
    assert state.get_last_complete_message() == "c"

    state.output_blocks = ["only"]
    assert state.get_last_complete_message() == "only"

    state.output_blocks = ["", ""]
    assert state.get_last_complete_message() == ""


def test_get_last_code_block():
    """Test get_last_code_block extracts last fenced code block."""
    state = AppState()
    state.output_blocks = ["text", "```py\nx=1\n```", "after"]
    out = state.get_last_code_block()
    assert out is not None
    assert out[0] == "x=1"
    assert out[1] == "py"

    state.output_blocks = ["no code here"]
    assert state.get_last_code_block() is None

    state.output_blocks = ["```\nplain\n```"]
    out = state.get_last_code_block()
    assert out is not None
    assert out[0] == "plain"
    assert out[1] == "text"


def test_output_cell():
    """Test OutputCell dataclass."""
    c = OutputCell(role="user", content="hi", tool_name=None, tool_args=None)
    assert c.role == "user"
    assert c.content == "hi"

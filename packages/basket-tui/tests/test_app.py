"""
Basic test for TUI App functionality.
"""

import pytest
from basket_tui import PiCodingAgentApp
from basket_tui.constants import STATUS_BAR_ID, MESSAGE_LIST_ID
from basket_tui.components.message_list import MessageList
from basket_tui.screens import TranscriptOverlay, CodeBlockOverlay


def test_app_import():
    """Test that the app can be imported."""
    assert PiCodingAgentApp is not None


def test_app_instantiation():
    """Test that the app can be instantiated."""
    app = PiCodingAgentApp()
    assert app is not None
    assert app.TITLE == "Pi Coding Agent"


def test_app_with_agent():
    """Test that the app can be instantiated with an agent."""
    # Mock agent
    class MockAgent:
        pass

    agent = MockAgent()
    app = PiCodingAgentApp(agent=agent)
    assert app.agent is agent


@pytest.mark.asyncio
async def test_app_compose():
    """Test that the app can compose its layout."""
    app = PiCodingAgentApp()

    # Test that compose method exists and is callable
    # Note: compose() needs app to be running to work with context manager
    assert hasattr(app, "compose")
    assert callable(app.compose)


def test_app_message_methods():
    """Test message append methods and block lifecycle."""
    app = PiCodingAgentApp()

    # These methods should exist
    assert hasattr(app, "append_message")
    assert hasattr(app, "append_text")
    assert hasattr(app, "append_thinking")
    assert hasattr(app, "show_tool_call")
    assert hasattr(app, "show_tool_result")
    assert hasattr(app, "append_markdown")
    assert hasattr(app, "show_code_block")
    assert hasattr(app, "ensure_assistant_block")
    assert hasattr(app, "finalize_assistant_block")
    assert hasattr(app, "append_user_message_async")


def test_handle_slash_command_handled():
    """Test _handle_slash_command returns True for TUI slash commands."""
    app = PiCodingAgentApp()
    assert app._handle_slash_command("/clear") is True
    assert app._handle_slash_command("/help") is True
    assert app._handle_slash_command("/history") is True
    assert app._handle_slash_command("/copy") is True
    assert app._handle_slash_command("/theme") is True
    assert app._handle_slash_command("/syntax") is True


def test_handle_slash_command_passthrough():
    """Test _handle_slash_command returns False for non-commands and agent commands."""
    app = PiCodingAgentApp()
    assert app._handle_slash_command("hello") is False
    assert app._handle_slash_command("") is False
    assert app._handle_slash_command("  /plan") is False  # /plan goes to agent
    assert app._handle_slash_command("/plan") is False
    assert app._handle_slash_command("/unknown") is False


def test_status_bar_and_transcript_actions():
    """Test status bar refresh and transcript overlay actions exist."""
    app = PiCodingAgentApp()
    assert hasattr(app, "_refresh_status_bar")
    assert hasattr(app, "action_transcript_overlay")
    assert hasattr(app, "action_copy_last")
    assert hasattr(app, "action_clear")


def test_status_bar_constant():
    """Test STATUS_BAR_ID constant is set for compose."""
    assert STATUS_BAR_ID == "status-bar"


def test_transcript_overlay_instantiation():
    """Test TranscriptOverlay can be created with get_blocks callback."""
    blocks = [("user", "hi"), ("assistant", "hello")]
    overlay = TranscriptOverlay(get_blocks=lambda: blocks)
    assert overlay._get_blocks() == blocks


def test_code_block_overlay_instantiation():
    """Test CodeBlockOverlay can be created with code and language."""
    overlay = CodeBlockOverlay(code="x = 1", language="python")
    assert overlay._code == "x = 1"
    assert overlay._language == "python"


@pytest.mark.asyncio
async def test_app_mounts_and_css_loads():
    """App starts and stylesheet parses without error (catches invalid Textual CSS)."""
    app = PiCodingAgentApp()
    async with app.run_test():
        message_list = app.query_one(f"#{MESSAGE_LIST_ID}", MessageList)
        assert message_list is not None

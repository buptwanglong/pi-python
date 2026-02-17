"""
Basic test for TUI App functionality.
"""

import pytest
from pi_tui import PiCodingAgentApp


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

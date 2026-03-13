"""
Basic test for TUI App functionality.
"""

import pytest
from basket_tui import PiCodingAgentApp
from basket_tui.constants import STATUS_BAR_ID, MESSAGE_LIST_ID
from basket_tui.components.message_list import MessageList
from basket_tui.screens import TranscriptOverlay, CodeBlockOverlay
from basket_tui.core.state_machine import Phase
from basket_tui.core.events import PhaseChangedEvent


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
    # Mock agent with required .on() method
    class MockAgent:
        def on(self, event_name, handler):
            pass

    agent = MockAgent()
    app = PiCodingAgentApp(agent=agent)
    assert app._agent is agent


@pytest.mark.asyncio
async def test_app_compose():
    """Test that the app can compose its layout."""
    app = PiCodingAgentApp()

    # Test that compose method exists and is callable
    # Note: compose() needs app to be running to work with context manager
    assert hasattr(app, "compose")
    assert callable(app.compose)


def test_app_manager_composition():
    """Test that managers are properly composed into the app."""
    app = PiCodingAgentApp()

    # Verify all managers exist
    assert hasattr(app, "layout_manager")
    assert hasattr(app, "message_renderer")
    assert hasattr(app, "streaming_controller")
    assert hasattr(app, "input_handler")
    assert hasattr(app, "session_controller")
    assert hasattr(app, "agent_bridge")

    # Verify core components
    assert hasattr(app, "event_bus")
    assert hasattr(app, "state_machine")


def test_message_renderer_methods():
    """Test message renderer methods through manager."""
    app = PiCodingAgentApp()

    # Methods should be accessible via message_renderer
    assert hasattr(app.message_renderer, "add_user_message")
    assert hasattr(app.message_renderer, "add_system_message")


def test_phase_transition():
    """Test state machine phase transitions."""
    app = PiCodingAgentApp()

    # Initial phase should be IDLE
    assert app.state_machine.current_phase == Phase.IDLE

    # Verify transition method exists
    assert hasattr(app, "transition_phase")
    assert callable(app.transition_phase)


def test_event_bus_integration():
    """Test event bus is properly integrated."""
    app = PiCodingAgentApp()

    # Event bus should exist
    assert app.event_bus is not None

    # Should be able to subscribe and publish
    called = []

    def handler(event):
        called.append(event)

    app.event_bus.subscribe(PhaseChangedEvent, handler)
    app.event_bus.publish(PhaseChangedEvent(old_phase=Phase.IDLE, new_phase=Phase.WAITING_MODEL))

    assert len(called) == 1
    assert called[0].new_phase == Phase.WAITING_MODEL


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

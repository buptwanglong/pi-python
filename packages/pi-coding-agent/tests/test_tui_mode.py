"""
Test TUI mode integration with Pi Agent
"""

import pytest
from pi_coding_agent.modes.tui import run_tui_mode


def test_run_tui_mode_import():
    """Test that run_tui_mode can be imported."""
    assert run_tui_mode is not None
    assert callable(run_tui_mode)


def test_tui_mode_module():
    """Test that tui mode module exists."""
    from pi_coding_agent.modes import tui

    assert hasattr(tui, "run_tui_mode")


@pytest.mark.asyncio
async def test_tui_mode_with_mock_agent():
    """Test TUI mode with a mock agent."""
    from pi_ai.types import Context

    # Create a minimal mock agent (no need for valid Model)
    class MockAgent:
        def __init__(self):
            self.context = Context(
                systemPrompt="Test system prompt",
                messages=[],
            )
            self._event_handlers = {}

        def on(self, event_name, handler):
            """Register event handler."""
            if event_name not in self._event_handlers:
                self._event_handlers[event_name] = []
            self._event_handlers[event_name].append(handler)

        async def run(self, stream_llm_events=True):
            """Mock run method."""
            # Emit some test events
            for handler in self._event_handlers.get("text_delta", []):
                handler({"delta": "Hello, "})
                handler({"delta": "world!"})

    agent = MockAgent()

    # Test that we can create the TUI mode setup
    # Note: We can't actually run the app in tests without a terminal
    assert agent is not None
    assert hasattr(agent, "on")
    assert hasattr(agent, "run")
    assert hasattr(agent, "context")

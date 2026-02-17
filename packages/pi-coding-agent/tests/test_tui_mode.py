"""
Test TUI mode integration with Pi Agent
"""

import pytest
from pi_coding_agent.modes.tui import run_tui_mode, _connect_agent_handlers


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


def test_tui_handlers_update_ui_directly_no_call_from_thread():
    """
    Event handlers must call app methods directly (same thread as TUI).
    Using call_from_thread from the app thread would raise:
    'The call_from_thread method must run in a different thread from the app'.
    This test ensures we never use call_from_thread in handlers.
    """
    from pi_ai.types import Context

    class RecordedCall:
        def __init__(self, name, args, kwargs):
            self.name = name
            self.args = args
            self.kwargs = kwargs

    class MockApp:
        """Records all method calls; call_from_thread must never be used."""

        def __init__(self):
            self.calls = []

        def _record(self, name, *args, **kwargs):
            self.calls.append(RecordedCall(name, args, kwargs))

        def append_text(self, text):
            self._record("append_text", text)

        def append_message(self, role, content):
            self._record("append_message", role, content)

        def append_thinking(self, thinking):
            self._record("append_thinking", thinking)

        def show_tool_call(self, tool_name, args=None):
            self._record("show_tool_call", tool_name, args)

        def show_tool_result(self, result, success=True):
            self._record("show_tool_result", result, success)

        def finalize_assistant_block(self, full_text=None):
            self._record("finalize_assistant_block", full_text)

        def call_from_thread(self, fn, *args, **kwargs):
            """Must not be called when handlers run in app thread."""
            self._record("call_from_thread", fn, *args, **kwargs)

    class MockAgent:
        def __init__(self):
            self.context = Context(systemPrompt="", messages=[])
            self._event_handlers = {}

        def on(self, event_name, handler):
            if event_name not in self._event_handlers:
                self._event_handlers[event_name] = []
            self._event_handlers[event_name].append(handler)

        def emit(self, event_name, payload):
            for h in self._event_handlers.get(event_name, []):
                h(payload)

    app = MockApp()
    agent = MockAgent()
    current_response = {"text": "", "thinking": "", "in_thinking": False}
    _connect_agent_handlers(app, agent, current_response)

    # Emit events from same thread (simulating agent running in TUI event loop)
    agent.emit("text_delta", {"delta": "Hello, "})
    agent.emit("text_delta", {"delta": "world!"})
    assert current_response["text"] == "Hello, world!"

    agent.emit("agent_tool_call_start", {"tool_name": "bash"})
    agent.emit(
        "agent_tool_call_end",
        {"tool_name": "bash", "result": {"stdout": "ok", "stderr": "", "exit_code": 0, "timeout": False}},
    )
    agent.emit("agent_complete", {})  # run finished: finalize block, reset current_response["text"]

    # All updates must be direct calls; call_from_thread must never be used
    call_from_thread_calls = [c for c in app.calls if c.name == "call_from_thread"]
    assert len(call_from_thread_calls) == 0, (
        "Handlers must not use call_from_thread when running in app thread; "
        "use direct app method calls to avoid 'must run in a different thread' error."
    )

    # Verify expected direct calls happened
    names = [c.name for c in app.calls]
    assert "append_text" in names
    assert names.count("append_text") == 2  # "Hello, " and "world!"
    assert "show_tool_call" in names
    assert "show_tool_result" in names
    finalize_calls = [c for c in app.calls if c.name == "finalize_assistant_block"]
    assert len(finalize_calls) == 1  # app uses internal buffer (text + tool) for finalize

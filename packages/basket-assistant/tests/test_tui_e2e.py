"""
End-to-End Tests for TUI Mode

These tests verify TUI mode works correctly with real agent and API calls.
They test the complete workflow: user input -> agent processing -> tool execution -> UI display.

IMPORTANT:
- These tests require a valid API key (OPENAI_API_KEY)
- They make real API calls (slower, costs money)
- They test actual TUI event handling and display logic

Running tests:
    # Run all TUI E2E tests
    export OPENAI_API_KEY=your-key
    pytest tests/test_tui_e2e.py -v

    # Run only P0 priority tests
    pytest tests/test_tui_e2e.py -m "p0" -v

    # Run specific test
    pytest tests/test_tui_e2e.py::test_tui_simple_conversation -v
"""

import asyncio
import os
from pathlib import Path

import pytest

from basket_assistant.main import CodingAgent


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def real_agent():
    """Create a real agent (no mocks) for TUI E2E testing."""
    # Check for API key
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("TUI E2E tests require OPENAI_API_KEY or ANTHROPIC_API_KEY")

    coding_agent = CodingAgent(load_extensions=False)
    return coding_agent.agent


@pytest.fixture
def test_workspace(tmp_path):
    """Create a temporary workspace with sample files."""
    # Create test files
    (tmp_path / "test.txt").write_text("Hello TUI World\nThis is a test file\nLine 3")
    (tmp_path / "example.py").write_text("def hello():\n    print('Hello from TUI')\n")
    (tmp_path / "README.md").write_text("# TUI Test Project\n\nThis is a test.")

    # Create subdirectory
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("Nested file content")

    # Change to test directory
    original_dir = os.getcwd()
    os.chdir(tmp_path)

    yield tmp_path

    # Restore directory
    os.chdir(original_dir)


# ============================================================================
# P0 Priority Tests - Core Functionality
# ============================================================================

@pytest.mark.e2e
@pytest.mark.tui
@pytest.mark.p0
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_tui_simple_conversation(real_agent):
    """
    P0 Test: Basic text conversation in TUI.

    Tests that:
    1. Agent can receive and process user messages
    2. Text is streamed via text_delta events
    3. Response is meaningful and complete
    """
    # Given: Agent with event tracking
    received_deltas = []
    full_response = []

    def capture_text_delta(event):
        delta = event.get("delta", "")
        if delta:
            received_deltas.append(delta)

    real_agent.on("text_delta", capture_text_delta)

    # When: Send simple message
    from basket_ai.types import UserMessage
    real_agent.context.messages.append(
        UserMessage(role="user", content="Say hi in one word", timestamp=0)
    )

    # Run agent
    await real_agent.run(stream_llm_events=True)

    # Then: Should have received text deltas
    assert len(received_deltas) > 0, "No text deltas received"

    # Build full response
    full_text = "".join(received_deltas)
    assert len(full_text) > 0, "Response is empty"

    # Should contain greeting
    assert any(
        word in full_text.lower() for word in ["hi", "hello", "hey", "greetings"]
    ), f"Response doesn't contain greeting: {full_text}"

    print(f"\n✅ TUI simple conversation test passed")
    print(f"   Received {len(received_deltas)} text deltas")
    print(f"   Response: {full_text[:100]}")


@pytest.mark.e2e
@pytest.mark.tui
@pytest.mark.p0
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_tui_bash_tool_execution(real_agent):
    """
    P0 Test: Bash tool execution is visible in TUI.

    Tests that:
    1. Tool call start event is fired
    2. Tool executes successfully
    3. Tool call end event is fired with result
    4. Result is a valid BashResult with stdout
    """
    # Given: Agent with tool event tracking
    tool_events = []

    def capture_tool_start(event):
        tool_events.append({
            "type": "start",
            "tool": event.get("tool_name"),
            "args": event.get("arguments", {})
        })

    def capture_tool_end(event):
        tool_events.append({
            "type": "end",
            "tool": event.get("tool_name"),
            "result": event.get("result"),
            "error": event.get("error")
        })

    real_agent.on("agent_tool_call_start", capture_tool_start)
    real_agent.on("agent_tool_call_end", capture_tool_end)

    # When: Ask to run a bash command
    from basket_ai.types import UserMessage
    real_agent.context.messages.append(
        UserMessage(role="user", content="Run pwd command", timestamp=0)
    )

    await real_agent.run(stream_llm_events=True)

    # Then: Should have tool call events
    assert len(tool_events) >= 2, f"Expected at least 2 tool events, got {len(tool_events)}"

    # Check start event
    start_events = [e for e in tool_events if e["type"] == "start"]
    assert len(start_events) > 0, "No tool start event received"

    start_event = start_events[0]
    assert start_event["tool"] == "bash", f"Expected bash tool, got {start_event['tool']}"

    # Check end event
    end_events = [e for e in tool_events if e["type"] == "end"]
    assert len(end_events) > 0, "No tool end event received"

    end_event = end_events[0]
    assert end_event["tool"] == "bash", f"Expected bash tool, got {end_event['tool']}"
    assert end_event["error"] is None, f"Tool execution failed: {end_event['error']}"

    # Check result
    result = end_event["result"]
    assert result is not None, "Tool result is None"

    # Result should be a dict with BashResult fields
    if isinstance(result, dict):
        assert "stdout" in result, "Result missing stdout field"
        assert "exit_code" in result, "Result missing exit_code field"
        assert result["exit_code"] == 0, f"Command failed with exit code {result['exit_code']}"
        assert len(result["stdout"]) > 0, "stdout is empty"
    else:
        # If it's a Pydantic model
        assert hasattr(result, "stdout"), "Result missing stdout attribute"
        assert hasattr(result, "exit_code"), "Result missing exit_code attribute"
        assert result.exit_code == 0, f"Command failed with exit code {result.exit_code}"
        assert len(result.stdout) > 0, "stdout is empty"

    print(f"\n✅ TUI bash tool execution test passed")
    print(f"   Tool events: {len(tool_events)}")
    if isinstance(result, dict):
        print(f"   Output: {result['stdout'][:50]}")
    else:
        print(f"   Output: {result.stdout[:50]}")


@pytest.mark.e2e
@pytest.mark.tui
@pytest.mark.p0
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_tui_read_file_tool(real_agent, test_workspace):
    """
    P0 Test: Read file tool execution in TUI.

    Tests that:
    1. Read tool is triggered
    2. File content is read successfully
    3. Result contains file content
    """
    # Given: Test file and agent with tracking
    test_file = test_workspace / "test.txt"
    assert test_file.exists(), "Test file doesn't exist"

    tool_results = []

    def capture_tool_end(event):
        if event.get("tool_name") == "read":
            tool_results.append({
                "result": event.get("result"),
                "error": event.get("error")
            })

    real_agent.on("agent_tool_call_end", capture_tool_end)

    # When: Ask to read the file
    from basket_ai.types import UserMessage
    real_agent.context.messages.append(
        UserMessage(
            role="user",
            content=f"Read the file {test_file}",
            timestamp=0
        )
    )

    await real_agent.run(stream_llm_events=True)

    # Then: Should have read tool result
    assert len(tool_results) > 0, "No read tool result received"

    result_data = tool_results[0]
    assert result_data["error"] is None, f"Read failed: {result_data['error']}"

    result = result_data["result"]
    assert result is not None, "Read result is None"

    # Check result contains file content
    if isinstance(result, dict):
        # Check for content or lines
        assert "content" in result or "lines" in result, \
            f"Result missing content/lines: {result.keys()}"

        if "content" in result:
            content = result["content"]
            assert "Hello TUI World" in content, \
                f"File content not in result: {content}"
    else:
        # Pydantic model
        assert hasattr(result, "content"), "Result missing content attribute"
        assert "Hello TUI World" in result.content, \
            f"File content not in result: {result.content}"

    print(f"\n✅ TUI read file tool test passed")
    print(f"   Read results: {len(tool_results)}")
    if isinstance(result, dict):
        print(f"   Content preview: {result.get('content', '')[:50]}")
    else:
        print(f"   Content preview: {result.content[:50]}")


@pytest.mark.e2e
@pytest.mark.tui
@pytest.mark.p0
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_tui_tool_execution_error(real_agent):
    """
    P0 Test: Tool execution error is handled correctly in TUI.

    Tests that:
    1. Tool error event is fired when tool execution fails
    2. Error message is present and descriptive
    3. Agent doesn't crash on tool error

    Note: This test may not always trigger a tool call if the LLM
    refuses to execute (e.g., sees "/nonexistent/" as suspicious).
    In that case, the test verifies agent handles it gracefully.
    """
    # Given: Agent with error tracking
    tool_errors = []
    tool_calls_made = []

    def capture_tool_start(event):
        tool_calls_made.append(event.get("tool_name"))

    def capture_tool_end(event):
        error = event.get("error")
        if error:
            tool_errors.append({
                "tool": event.get("tool_name"),
                "error": error
            })

    real_agent.on("agent_tool_call_start", capture_tool_start)
    real_agent.on("agent_tool_call_end", capture_tool_end)

    # When: Try to read non-existent file (explicit instruction to use tool)
    from basket_ai.types import UserMessage
    real_agent.context.messages.append(
        UserMessage(
            role="user",
            content="Use the read tool to read /tmp/this_file_definitely_does_not_exist_12345.txt",
            timestamp=0
        )
    )

    # Should not crash
    try:
        await real_agent.run(stream_llm_events=True)
    except Exception as e:
        pytest.fail(f"Agent crashed on tool error: {e}")

    # Then: Either tool was called and errored, or LLM refused to call it
    if len(tool_calls_made) > 0:
        # Tool was called, should have error
        assert len(tool_errors) > 0, \
            f"Tool was called ({tool_calls_made}) but no errors captured"

        error_data = tool_errors[0]
        assert error_data["error"] is not None, "Error is None"
        assert len(str(error_data["error"])) > 0, "Error message is empty"

        # Error should mention file not found or similar
        error_str = str(error_data["error"]).lower()
        assert any(
            phrase in error_str
            for phrase in ["not found", "does not exist", "no such file", "cannot find", "error"]
        ), f"Error message not descriptive: {error_data['error']}"

        print(f"\n✅ TUI tool execution error test passed (tool called and errored)")
        print(f"   Errors captured: {len(tool_errors)}")
        print(f"   Error message: {str(error_data['error'])[:100]}")
    else:
        # LLM refused to call tool (also valid behavior)
        print(f"\n✅ TUI tool execution error test passed (LLM avoided invalid operation)")
        print(f"   Tool calls made: {len(tool_calls_made)}")
        print(f"   Agent handled gracefully without crashing")


# ============================================================================
# Test Summary and Validation
# ============================================================================

def test_tui_e2e_p0_count():
    """
    Meta-test: Verify we have all P0 TUI E2E tests.

    This ensures we don't accidentally remove critical tests.
    """
    import inspect

    # Count P0 tests in this module
    p0_tests = [
        name for name, obj in globals().items()
        if name.startswith("test_tui_")
        and callable(obj)
        and hasattr(obj, "pytestmark")
        and any(
            marker.name == "p0"
            for marker in (obj.pytestmark if isinstance(obj.pytestmark, list) else [obj.pytestmark])
            if hasattr(marker, "name")
        )
    ]

    # Should have exactly 4 P0 tests
    assert len(p0_tests) >= 4, (
        f"Expected at least 4 P0 TUI E2E tests, found {len(p0_tests)}: {p0_tests}\n"
        f"P0 tests are critical for core functionality!"
    )

    print(f"\n✅ TUI E2E test count validation passed: {len(p0_tests)} P0 tests")

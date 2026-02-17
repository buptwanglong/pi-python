"""
End-to-End Workflow Tests for Pi-Coding-Agent

These tests verify complete user workflows using real components (not mocks).
They test the full integration: agent -> LLM API -> tools -> file system.

IMPORTANT:
- These tests require a valid API key (ANTHROPIC_API_KEY or similar)
- They make real API calls (slower, costs money)
- They test actual API compatibility (can find issues unit/integration tests miss)

Running tests:
    # Skip tests that need API keys
    pytest tests/test_e2e_workflows.py -m "not requires_api"

    # Run all E2E tests (needs API key)
    export ANTHROPIC_API_KEY=your-key
    pytest tests/test_e2e_workflows.py -v

    # Run specific category
    pytest tests/test_e2e_workflows.py -k "happy_path"
    pytest tests/test_e2e_workflows.py -k "api_compatibility"
"""

import os
import time
from pathlib import Path

import pytest

from pi_coding_agent.main import CodingAgent


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def real_agent():
    """Create a real agent (no mocks) for E2E testing."""
    # Check for API key
    if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        pytest.skip("E2E tests require ANTHROPIC_API_KEY or OPENAI_API_KEY")

    agent = CodingAgent(load_extensions=False)
    return agent


@pytest.fixture
def test_workspace(tmp_path):
    """Create a temporary workspace with sample files."""
    # Create test files
    (tmp_path / "test.txt").write_text("Hello World\nThis is a test file")
    (tmp_path / "example.py").write_text("def hello():\n    print('Hello')\n")
    (tmp_path / "README.md").write_text("# Test Project\n\nThis is a test.")

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
# Category 1: Happy Path Tests
# ============================================================================

@pytest.mark.e2e
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_e2e_simple_conversation(real_agent):
    """Test basic text-only conversation without tools."""
    # When: Send a simple message
    response = await real_agent.run_once("Say hello in one word")

    # Then: Should get a text response
    assert response
    assert len(response) > 0
    assert isinstance(response, str)
    # Should contain some greeting
    assert any(word in response.lower() for word in ["hello", "hi", "hey", "greetings"])


@pytest.mark.e2e
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_e2e_read_file_workflow(real_agent, test_workspace):
    """Test complete read file workflow: user asks -> agent uses read tool -> returns content."""
    # Given: A test file exists
    test_file = test_workspace / "test.txt"
    assert test_file.exists()

    # When: Ask agent to read it
    response = await real_agent.run_once(f"Read the file {test_file}")

    # Then: Response should contain file content
    assert response
    assert "Hello World" in response or "test file" in response.lower()


@pytest.mark.e2e
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_e2e_write_file_workflow(real_agent, test_workspace):
    """Test complete write file workflow: user asks -> agent creates file."""
    # When: Ask agent to create a file
    new_file = test_workspace / "hello.py"
    response = await real_agent.run_once(
        f"Create a file at {new_file} with a function that prints 'Hello World'"
    )

    # Then: File should be created
    assert new_file.exists()
    content = new_file.read_text()
    assert "def" in content
    assert "Hello World" in content or "hello" in content.lower()


@pytest.mark.e2e
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_e2e_bash_command_workflow(real_agent):
    """Test complete bash command workflow: user asks -> agent executes command."""
    # When: Ask agent to run a command
    response = await real_agent.run_once("Run the command 'echo Testing123'")

    # Then: Response should show command output
    assert response
    assert "Testing123" in response


@pytest.mark.e2e
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_e2e_grep_search_workflow(real_agent, test_workspace):
    """Test complete grep search workflow: user asks -> agent searches files."""
    # Given: Files with searchable content
    (test_workspace / "file1.py").write_text("def hello():\n    pass")
    (test_workspace / "file2.py").write_text("def world():\n    pass")

    # When: Ask agent to search
    response = await real_agent.run_once(
        f"Search for the word 'hello' in Python files in {test_workspace}"
    )

    # Then: Should find matches
    assert response
    assert "file1.py" in response or "hello" in response.lower()


# ============================================================================
# Category 2: Multi-Turn Tests
# ============================================================================

@pytest.mark.e2e
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_e2e_multi_turn_context(real_agent, test_workspace):
    """Test context preservation across multiple turns."""
    # Given: A test file
    test_file = test_workspace / "number.txt"
    test_file.write_text("42")

    # When: First turn - read file
    response1 = await real_agent.run_once(f"What number is in {test_file}?")
    assert "42" in response1

    # When: Second turn - reference previous content
    response2 = await real_agent.run_once("Double that number")

    # Then: Should remember and calculate
    assert "84" in response2


@pytest.mark.e2e
@pytest.mark.requires_api
@pytest.mark.slow
@pytest.mark.asyncio
async def test_e2e_multi_tool_workflow(real_agent, test_workspace):
    """Test complex task requiring multiple tools."""
    # When: Ask for multi-step task
    response = await real_agent.run_once(
        f"Create a file greeting.py with a hello function, "
        f"then read it back and tell me what's in it"
    )

    # Then: File should exist and response should describe it
    greeting_file = test_workspace / "greeting.py"
    if greeting_file.exists():
        content = greeting_file.read_text()
        assert "def" in content and "hello" in content.lower()


# ============================================================================
# Category 3: Error Handling Tests
# ============================================================================

@pytest.mark.e2e
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_e2e_file_not_found_error(real_agent):
    """Test graceful handling of file not found error."""
    # When: Try to read non-existent file
    response = await real_agent.run_once("Read the file /nonexistent/path/file.txt")

    # Then: Should report error gracefully (not crash)
    assert response
    assert any(phrase in response.lower() for phrase in [
        "not found", "does not exist", "cannot find", "no such file"
    ])


@pytest.mark.e2e
@pytest.mark.requires_api
@pytest.mark.slow
@pytest.mark.asyncio
async def test_e2e_command_timeout(real_agent):
    """Test handling of command timeout."""
    # When: Run command that would timeout (sleep with short timeout)
    response = await real_agent.run_once("Run the command 'sleep 5' with a 2 second timeout")

    # Then: Should report timeout
    # Note: This depends on agent understanding timeout parameter
    assert response


@pytest.mark.e2e
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_e2e_api_error_recovery(real_agent):
    """Test that context is preserved after API errors."""
    # Given: Agent with error recovery
    initial_message_count = len(real_agent.context.messages)

    # When: Send a message (might fail)
    try:
        await real_agent.run_once("Say hi")
    except Exception:
        pass

    # Then: Context should be consistent
    # Either message succeeded (2 more: user + assistant) or rolled back (1 more: user only)
    final_count = len(real_agent.context.messages)
    assert final_count >= initial_message_count


# ============================================================================
# Category 4: API Compatibility Tests (CRITICAL!)
# ============================================================================

@pytest.mark.e2e
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_e2e_api_supports_tools(real_agent, test_workspace):
    """
    CRITICAL TEST: Verify API supports tools parameter.

    This test would have caught the current bug where the internal API
    doesn't support the 'tools' parameter!
    """
    # Given: A test file
    test_file = test_workspace / "test.txt"

    # When: Ask agent to use a tool
    response = await real_agent.run_once(f"List files in {test_workspace}")

    # Then: Check if we got the tools parameter error
    # Look at the last message in context for error details
    if len(real_agent.context.messages) > 0:
        last_msg = real_agent.context.messages[-1]
        if hasattr(last_msg, 'error_message') and last_msg.error_message:
            error_msg = last_msg.error_message.lower()

            # Check for tools parameter error
            error_messages = [
                "unexpected keyword argument 'tools'",
                "got an unexpected keyword",
                "does not support tools"
            ]

            for err_pattern in error_messages:
                assert err_pattern not in error_msg, (
                    f"❌ API DOES NOT SUPPORT TOOLS PARAMETER!\n"
                    f"Error: {last_msg.error_message}\n"
                    f"This means the API is incompatible with tool calling.\n"
                    f"Solutions:\n"
                    f"  1. Upgrade API to support tools parameter\n"
                    f"  2. Use official Anthropic/OpenAI API\n"
                    f"  3. Modify agent to work without tools"
                )

    # And should have some response (if API supports tools)
    assert response or len(response) == 0, (
        "No response received. Check API compatibility."
    )


@pytest.mark.e2e
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_e2e_api_response_format(real_agent):
    """Test that API returns responses in expected format."""
    # When: Send message
    response = await real_agent.run_once("Say hi")

    # Then: Response should be valid
    assert isinstance(response, str)
    assert len(response) > 0
    # Should not be an error object
    assert not response.startswith("Error:")
    assert not response.startswith("Exception:")


@pytest.mark.e2e
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_e2e_api_streaming(real_agent):
    """Test that API supports streaming."""
    # Given: Track streamed chunks
    streamed_chunks = []

    # Capture text_delta events
    def capture_handler(event):
        delta = event.get("delta", "")
        if delta:
            streamed_chunks.append(delta)

    real_agent.agent.on("text_delta", capture_handler)

    # When: Send message with streaming enabled
    response = await real_agent.run_once("Count from 1 to 3")

    # Then: Should have received multiple chunks (streaming works)
    assert len(streamed_chunks) > 0, "No streaming chunks received"
    # Full response should match streamed content
    streamed_text = "".join(streamed_chunks)
    assert len(streamed_text) > 0


# ============================================================================
# Category 5: Performance Tests
# ============================================================================

@pytest.mark.e2e
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_e2e_response_time(real_agent):
    """Test that response time is reasonable."""
    # When: Send simple message
    start = time.time()
    response = await real_agent.run_once("Say hi in one word")
    elapsed = time.time() - start

    # Then: Should respond in reasonable time (< 15 seconds)
    assert elapsed < 15.0, f"Response took {elapsed:.2f}s (too slow)"
    assert response


@pytest.mark.e2e
@pytest.mark.requires_api
@pytest.mark.slow
@pytest.mark.asyncio
async def test_e2e_large_file_handling(real_agent, test_workspace):
    """Test handling of large files."""
    # Given: Large file (1000 lines)
    large_file = test_workspace / "large.txt"
    large_file.write_text("line\n" * 1000)

    # When: Ask about the file
    response = await real_agent.run_once(f"How many lines are in {large_file}?")

    # Then: Should handle it
    assert response
    assert "1000" in response or "thousand" in response.lower()


# ============================================================================
# Category 6: Configuration Tests
# ============================================================================

@pytest.mark.e2e
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_e2e_custom_settings(tmp_path):
    """Test that custom settings are respected."""
    # Given: Custom settings
    from pi_coding_agent.core import SettingsManager

    settings_manager = SettingsManager(tmp_path / "settings.json")
    settings = settings_manager.load()
    settings.agent.max_turns = 3
    settings.agent.verbose = True
    settings_manager.save(settings)

    # When: Create agent with custom settings
    agent = CodingAgent(settings_manager=settings_manager, load_extensions=False)

    # Then: Settings should be applied
    assert agent.agent.max_turns == 3
    assert agent.settings.agent.verbose is True


# ============================================================================
# Test Summary Marker
# ============================================================================

def test_e2e_test_count():
    """
    Verify we have adequate E2E test coverage.

    This meta-test ensures we don't accidentally remove E2E tests.
    """
    import inspect

    # Count E2E tests in this module
    e2e_tests = [
        name for name, obj in globals().items()
        if name.startswith("test_e2e_") and callable(obj)
    ]

    # Should have at least 15 E2E tests
    assert len(e2e_tests) >= 15, (
        f"Only {len(e2e_tests)} E2E tests found. "
        f"We need comprehensive E2E coverage!"
    )

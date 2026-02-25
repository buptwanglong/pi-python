"""
Shared pytest fixtures for pi-assistant tests.
"""

import asyncio
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from basket_agent import Agent
from basket_ai.types import AssistantMessage, Context, TextContent, ToolCall

from basket_assistant.main import CodingAgent
from basket_assistant.core import SettingsManager


@pytest.fixture
def temp_project_dir():
    """
    Create a temporary directory with sample files for testing.

    Returns a Path object to the temporary directory.
    The directory is automatically cleaned up after the test.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create sample files
        (tmpdir_path / "test.txt").write_text("Hello, World!\nThis is a test file.")
        (tmpdir_path / "example.py").write_text("def hello():\n    print('Hello')\n")
        (tmpdir_path / "README.md").write_text("# Test Project\n\nThis is a test.")

        # Create subdirectory with files
        subdir = tmpdir_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("Nested file content")

        yield tmpdir_path


@pytest.fixture
def mock_settings_manager(tmp_path):
    """
    Create a mock SettingsManager with temporary settings directory.
    """
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()

    manager = SettingsManager(settings_dir / "settings.json")
    # Load default settings
    manager.load()
    return manager


def create_mock_llm_stream(responses: List[Dict[str, Any]]):
    """
    Create a mock LLM stream generator.

    Args:
        responses: List of response dicts with 'type' and other fields

    Returns:
        Async generator that yields the responses
    """

    async def mock_stream(*args, **kwargs):
        for response in responses:
            yield response

    return mock_stream


@pytest.fixture
def mock_text_response():
    """
    Create a mock LLM response with just text (no tool calls).
    """
    return [
        {"type": "message_start"},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text"}},
        {"type": "text_delta", "delta": "Hello! "},
        {"type": "text_delta", "delta": "I can help you."},
        {"type": "content_block_end", "index": 0},
        {"type": "message_end"},
    ]


@pytest.fixture
def mock_tool_call_response():
    """
    Create a mock LLM response that includes a tool call.
    """
    return [
        {"type": "message_start"},
        # Text before tool call
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text"}},
        {"type": "text_delta", "delta": "I'll read the file for you."},
        {"type": "content_block_end", "index": 0},
        # Tool use block
        {
            "type": "content_block_start",
            "index": 1,
            "content_block": {
                "type": "tool_use",
                "id": "tool_123",
                "name": "read",
                "input": {},
            },
        },
        {"type": "tool_use_delta", "delta": {"file_path": "/test/file.txt"}},
        {"type": "content_block_end", "index": 1},
        {"type": "message_end"},
    ]


@pytest.fixture
def mock_model():
    """
    Create a mock Model object for testing.
    """
    model = MagicMock()
    model.provider = "mock"
    model.model_id = "mock-model"
    return model


@pytest.fixture
def mock_agent(mock_model):
    """
    Create a mock Agent instance.
    """
    context = Context(systemPrompt="Test prompt", messages=[])
    agent = Agent(mock_model, context)
    agent.run = AsyncMock(return_value=MagicMock(context=context))
    return agent


@pytest.fixture
async def mock_coding_agent(tmp_path, mock_settings_manager, monkeypatch):
    """
    Create a mock CodingAgent instance for integration testing.

    This fixture:
    - Uses temporary directories for settings and sessions
    - Mocks the LLM model to avoid API calls
    - Provides a fully initialized agent with all tools registered
    """
    # Mock get_model to return a mock model
    mock_model = MagicMock()
    mock_model.provider = "mock"
    mock_model.model_id = "mock-model"

    def mock_get_model(*args, **kwargs):
        return mock_model

    # Patch get_model at the import location
    from basket_ai import api
    monkeypatch.setattr(api, "get_model", mock_get_model)

    # Create agent with test settings (persist sessions_dir so load() sees it)
    settings = mock_settings_manager.load()
    settings.sessions_dir = str(tmp_path / "sessions")
    mock_settings_manager.save(settings)
    agent = CodingAgent(settings_manager=mock_settings_manager, load_extensions=False)

    return agent


@pytest.fixture
def sample_context():
    """
    Create a sample Context with a few messages.
    """
    from basket_ai.types import UserMessage

    return Context(
        systemPrompt="You are a helpful assistant.",
        messages=[
            UserMessage(role="user", content="Hello", timestamp=1000),
            AssistantMessage(
                role="assistant",
                content=[TextContent(type="text", text="Hi! How can I help?")],
                timestamp=1001,
            ),
        ],
    )


@pytest.fixture
def mock_stream_with_tool_call(monkeypatch):
    """
    Mock the basket_ai.stream function to return a tool call response.
    """
    from basket_ai import api

    async def mock_stream(model, context):
        # Yield text
        yield {"type": "text_delta", "delta": "I'll read that file."}

        # Yield tool use
        yield {
            "type": "tool_use",
            "tool_use": {
                "id": "tool_123",
                "name": "read",
                "input": {"file_path": "/test.txt"},
            },
        }

    monkeypatch.setattr(api, "stream", mock_stream)


# Configure pytest markers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests for individual components")
    config.addinivalue_line("markers", "integration: Integration tests for component interaction")
    config.addinivalue_line("markers", "e2e: End-to-end tests for complete workflows")
    config.addinivalue_line("markers", "slow: Tests that take a long time to run")

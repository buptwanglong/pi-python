"""
Integration tests for CodingAgent.

These tests verify that the CodingAgent class properly integrates
with the pi-agent and pi-ai packages to provide full functionality.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from basket_ai.types import AssistantMessage, Context, TextContent, UserMessage

from basket_assistant.main import CodingAgent
from basket_assistant.core import SettingsManager, SubAgentConfig


@pytest.mark.integration
class TestCodingAgentIntegration:
    """Integration tests for CodingAgent class."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self, tmp_path, monkeypatch):
        """Test that CodingAgent initializes correctly with all components."""
        # Mock get_model to avoid API calls
        mock_model = MagicMock()
        mock_model.provider = "test"
        mock_model.model_id = "test-model"

        # Import the module and patch get_model at the import location
        from basket_ai import api
        monkeypatch.setattr(api, "get_model", lambda *args, **kwargs: mock_model)

        # Create settings manager with temp directory
        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()
        settings_manager = SettingsManager(settings_dir / "settings.json")
        settings = settings_manager.load()
        settings.sessions_dir = str(tmp_path / "sessions")
        settings_manager.save(settings)

        # Initialize agent
        agent = CodingAgent(settings_manager=settings_manager, load_extensions=False)

        # Verify initialization
        assert agent.settings is not None
        assert agent.model == mock_model
        assert agent.agent is not None
        assert agent.context is not None
        assert len(agent.context.messages) == 0
        assert agent.session_manager is not None

    @pytest.mark.asyncio
    async def test_tool_registration(self, mock_coding_agent):
        """Test that built-in tools (read, write, edit, bash, grep) and skill tool are registered."""
        # Get registered tools from agent
        tools = mock_coding_agent.agent.tools

        # Verify built-in + skill tools are registered
        tool_names = {tool["name"] for tool in tools}
        expected_tools = {"read", "write", "edit", "bash", "grep", "skill"}
        assert expected_tools.issubset(tool_names), f"Missing tools: {expected_tools - tool_names}"

        # Verify each tool has required fields
        for tool in tools:
            if tool["name"] in expected_tools:
                assert "description" in tool
                assert "parameters" in tool
                assert "execute_fn" in tool
                assert callable(tool["execute_fn"])

    @pytest.mark.asyncio
    async def test_filter_tools_for_subagent_whitelist(self, mock_coding_agent):
        """SubAgentConfig.tools whitelist: only explicitly enabled tools are returned."""
        cfg = SubAgentConfig(
            description="Explore",
            prompt="You explore.",
            tools={"read": True, "grep": True},
        )
        filtered = mock_coding_agent._filter_tools_for_subagent(cfg)
        names = [t["name"] for t in filtered]
        assert set(names) == {"read", "grep"}, "Only whitelisted read and grep should be enabled"

    @pytest.mark.asyncio
    async def test_task_tool_registered_when_agents_configured(self, tmp_path, mock_settings_manager, monkeypatch):
        """When settings contain agents, the task tool is registered."""
        from basket_assistant.core.settings import Settings
        mock_model = MagicMock()
        mock_model.provider = "mock"
        mock_model.model_id = "mock-model"
        monkeypatch.setattr("basket_ai.api.get_model", lambda *args, **kwargs: mock_model)
        settings = mock_settings_manager.load()
        settings.sessions_dir = str(tmp_path / "sessions")
        settings.agents = {
            "general": SubAgentConfig(
                description="General research",
                prompt="You are a research assistant.",
            ),
        }
        mock_settings_manager.save(settings)
        agent = CodingAgent(settings_manager=mock_settings_manager, load_extensions=False)
        tool_names = {t.name for t in agent.agent.tools}
        assert "task" in tool_names

    @pytest.mark.asyncio
    async def test_single_turn_conversation(self, mock_coding_agent, monkeypatch):
        """Test a single turn conversation with the agent."""
        # Mock agent.run to simulate a simple text response
        async def mock_run(stream_llm_events=False):
            # Add an assistant response to context
            mock_coding_agent.context.messages.append(
                AssistantMessage(
                    role="assistant",
                    content=[TextContent(type="text", text="Hello! I can help you with that.")],
                    timestamp=2000,
                )
            )
            return MagicMock(context=mock_coding_agent.context)

        mock_coding_agent.agent.run = AsyncMock(side_effect=mock_run)

        # Run one-shot mode
        response = await mock_coding_agent.run_once("Hello, how are you?")

        # Verify response
        assert isinstance(response, str)
        assert "Hello" in response
        assert len(mock_coding_agent.context.messages) == 2  # User + Assistant

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(self, mock_coding_agent, monkeypatch):
        """Test context preservation across multiple turns."""
        # Mock agent.run to add responses
        turn_count = [0]

        async def mock_run(stream_llm_events=False):
            turn_count[0] += 1
            mock_coding_agent.context.messages.append(
                AssistantMessage(
                    role="assistant",
                    content=[TextContent(type="text", text=f"Response {turn_count[0]}")],
                    timestamp=1000 + turn_count[0],
                )
            )
            return MagicMock(context=mock_coding_agent.context)

        mock_coding_agent.agent.run = AsyncMock(side_effect=mock_run)

        # First turn
        await mock_coding_agent.run_once("First message")
        assert len(mock_coding_agent.context.messages) == 2

        # Second turn
        await mock_coding_agent.run_once("Second message")
        assert len(mock_coding_agent.context.messages) == 4

        # Third turn
        await mock_coding_agent.run_once("Third message")
        assert len(mock_coding_agent.context.messages) == 6

        # Verify all messages are in context
        user_messages = [m for m in mock_coding_agent.context.messages if m.role == "user"]
        assistant_messages = [m for m in mock_coding_agent.context.messages if m.role == "assistant"]
        assert len(user_messages) == 3
        assert len(assistant_messages) == 3

    @pytest.mark.asyncio
    async def test_tool_execution_in_context(self, mock_coding_agent, tmp_path):
        """Test that tools can be executed within agent context."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello from test file")

        # Get the read tool
        read_tool = None
        for tool in mock_coding_agent.agent.tools:
            if tool["name"] == "read":
                read_tool = tool
                break

        assert read_tool is not None, "Read tool not registered"

        # Execute the read tool
        result = await read_tool["execute_fn"](file_path=str(test_file))

        # Verify result
        assert result.content == "Hello from test file"
        assert result.lines == 1
        assert result.file_path == str(test_file)

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, mock_coding_agent):
        """Test that agent handles errors gracefully and recovers."""
        # Mock agent.run to raise an exception
        mock_coding_agent.agent.run = AsyncMock(side_effect=RuntimeError("Simulated error"))

        # Add initial message
        initial_message_count = len(mock_coding_agent.context.messages)

        # Try to run agent (should fail but not crash)
        with pytest.raises(RuntimeError):
            await mock_coding_agent.run_once("This will fail")

        # In run_once, there's no error recovery, so message is added
        # but agent fails. Check that context has user message
        assert len(mock_coding_agent.context.messages) == initial_message_count + 1

    @pytest.mark.asyncio
    async def test_max_turns_limit(self, mock_coding_agent):
        """Test that agent respects max_turns setting."""
        # Set max_turns to a low value
        mock_coding_agent.agent.max_turns = 3
        assert mock_coding_agent.agent.max_turns == 3

        # Verify the setting is applied
        assert mock_coding_agent.settings.agent.max_turns > 0

    @pytest.mark.asyncio
    async def test_settings_integration(self, mock_coding_agent):
        """Test that agent uses settings correctly."""
        # Verify settings are loaded
        assert mock_coding_agent.settings is not None
        assert mock_coding_agent.settings.model is not None
        assert mock_coding_agent.settings.agent is not None

        # Verify settings are applied
        assert mock_coding_agent.agent.max_turns == mock_coding_agent.settings.agent.max_turns

    @pytest.mark.asyncio
    async def test_event_handlers_registered(self, mock_coding_agent):
        """Test that event handlers are registered on agent."""
        # Check that event handlers exist
        # Note: Agent event system is internal, so we check indirectly
        # by verifying the agent has the on() method
        assert hasattr(mock_coding_agent.agent, "on")
        assert callable(mock_coding_agent.agent.on)

    @pytest.mark.asyncio
    async def test_extension_loader_integration(self, mock_coding_agent):
        """Test that extension loader is properly initialized."""
        assert mock_coding_agent.extension_loader is not None
        assert mock_coding_agent.extension_loader.extension_api is not None

        # Verify extension API has access to agent
        api = mock_coding_agent.extension_loader.extension_api
        assert api.get_context() == mock_coding_agent.context
        assert api.get_settings() == mock_coding_agent.settings

    @pytest.mark.asyncio
    async def test_session_manager_integration(self, mock_coding_agent, tmp_path):
        """Test that session manager is properly integrated."""
        # Verify session manager is initialized
        assert mock_coding_agent.session_manager is not None

        # Test creating a session
        session_id = await mock_coding_agent.session_manager.create_session("test-session")
        assert session_id is not None

        # Test appending to session
        await mock_coding_agent.session_manager.append_entry(
            session_id, {"type": "message", "content": "test"}
        )

        # Test reading session
        entries = await mock_coding_agent.session_manager.read_entries(session_id)
        assert len(entries) == 1
        assert entries[0]["content"] == "test"

    @pytest.mark.asyncio
    async def test_context_persistence(self, mock_coding_agent):
        """Test that context is preserved between operations."""
        initial_messages = mock_coding_agent.context.messages[:]

        # Mock agent.run
        async def mock_run(stream_llm_events=False):
            mock_coding_agent.context.messages.append(
                AssistantMessage(
                    role="assistant",
                    content=[TextContent(type="text", text="Response")],
                    timestamp=2000,
                )
            )
            return MagicMock(context=mock_coding_agent.context)

        mock_coding_agent.agent.run = AsyncMock(side_effect=mock_run)

        # Run a turn
        await mock_coding_agent.run_once("Test message")

        # Verify context grew
        assert len(mock_coding_agent.context.messages) > len(initial_messages)

        # Verify context is the same object (not recreated)
        assert mock_coding_agent.context is mock_coding_agent.agent.context

    @pytest.mark.asyncio
    async def test_system_prompt_applied(self, mock_coding_agent):
        """Test that system prompt is correctly applied."""
        # Verify system prompt exists
        assert mock_coding_agent.context.systemPrompt is not None
        assert len(mock_coding_agent.context.systemPrompt) > 0

        # Verify it contains expected content
        assert "coding assistant" in mock_coding_agent.context.systemPrompt.lower()
        assert "tools" in mock_coding_agent.context.systemPrompt.lower()

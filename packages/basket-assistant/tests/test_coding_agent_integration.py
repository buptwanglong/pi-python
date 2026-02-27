"""
Integration tests for CodingAgent.

These tests verify that the CodingAgent class properly integrates
with the pi-agent and pi-ai packages to provide full functionality.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from basket_ai.types import (
    AssistantMessage,
    Context,
    StopReason,
    TextContent,
    ToolResultMessage,
    UserMessage,
)

from basket_assistant.main import (
    CodingAgent,
    PLAN_MODE_DISABLED_MESSAGE,
    PLAN_MODE_FORBIDDEN_TOOLS,
)
from basket_assistant.core import SettingsManager, SubAgentConfig
from basket_assistant.core.settings import PermissionsSettings


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

        # Patch get_model on the main module (basket_assistant.main is a module; get_model is used in CodingAgent)
        import sys
        main_module = sys.modules["basket_assistant.main"]
        monkeypatch.setattr(main_module, "get_model", lambda *args, **kwargs: mock_model)

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
        # Get registered tools from agent (AgentTool objects with .name, .executor, etc.)
        tools = mock_coding_agent.agent.tools

        # Verify built-in + skill tools are registered
        tool_names = {getattr(t, "name", None) for t in tools}
        expected_tools = {"read", "write", "edit", "bash", "grep", "skill"}
        assert expected_tools.issubset(tool_names), f"Missing tools: {expected_tools - tool_names}"

        # Verify each expected tool has required fields
        for tool in tools:
            name = getattr(tool, "name", None)
            if name in expected_tools:
                assert getattr(tool, "description", None) is not None
                assert getattr(tool, "parameters", None) is not None
                assert getattr(tool, "executor", None) is not None
                assert callable(getattr(getattr(tool, "executor", None), "execute", None))

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
                    api="test",
                    provider="test",
                    model="test",
                    stop_reason=StopReason.STOP,
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
                    api="test",
                    provider="test",
                    model="test",
                    stop_reason=StopReason.STOP,
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

        # Get the read tool (AgentTool has .name, .executor)
        read_tool = None
        for tool in mock_coding_agent.agent.tools:
            if getattr(tool, "name", None) == "read":
                read_tool = tool
                break

        assert read_tool is not None, "Read tool not registered"

        # Execute the read tool
        result = await read_tool.executor.execute(file_path=str(test_file))

        # Verify result (read tool returns content with line numbers)
        assert "Hello from test file" in result.content
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

        # Test appending to session (append_entry expects SessionEntry)
        from basket_assistant.core.session_manager import SessionEntry

        entry = SessionEntry(
            timestamp=1234567890,
            type="message",
            data={"content": "test"},
        )
        await mock_coding_agent.session_manager.append_entry(session_id, entry)

        # Test reading session (entries include initial metadata + our message)
        entries = await mock_coding_agent.session_manager.read_entries(session_id)
        assert len(entries) >= 1
        message_entries = [e for e in entries if e.type == "message"]
        assert len(message_entries) == 1
        assert message_entries[0].data.get("content") == "test"

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
                    api="test",
                    provider="test",
                    model="test",
                    stop_reason=StopReason.STOP,
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
        # Verify system prompt exists (Context uses system_prompt field)
        assert mock_coding_agent.context.system_prompt is not None
        assert len(mock_coding_agent.context.system_prompt) > 0

        # Verify it contains expected content
        assert "coding assistant" in mock_coding_agent.context.system_prompt.lower()
        assert "tools" in mock_coding_agent.context.system_prompt.lower()

    @pytest.mark.asyncio
    async def test_set_session_id_loads_todos_from_file(self, tmp_path, monkeypatch):
        """set_session_id(session_id) loads _current_todos from session's todo file."""
        mock_model = MagicMock()
        mock_model.provider = "test"
        mock_model.id = "test-model"
        mock_model.model_id = "test-model"
        monkeypatch.setattr("basket_ai.api.get_model", lambda *args, **kwargs: mock_model)

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()
        settings_manager = SettingsManager(settings_dir / "settings.json")
        settings = settings_manager.load()
        settings.sessions_dir = str(sessions_dir)
        settings_manager.save(settings)

        agent = CodingAgent(settings_manager=settings_manager, load_extensions=False)
        session_id = await agent.session_manager.create_session(agent.model.id)
        todos = [{"id": "1", "content": "Loaded task", "status": "in_progress"}]
        await agent.session_manager.save_todos(session_id, todos)

        await agent.set_session_id(session_id)
        assert agent._session_id == session_id
        assert agent._current_todos == todos

    @pytest.mark.asyncio
    async def test_plan_mode_get_set(self, mock_coding_agent):
        """get_plan_mode and set_plan_mode work; default is False."""
        assert mock_coding_agent.get_plan_mode() is False
        mock_coding_agent.set_plan_mode(True)
        assert mock_coding_agent.get_plan_mode() is True
        mock_coding_agent.set_plan_mode(False)
        assert mock_coding_agent.get_plan_mode() is False

    @pytest.mark.asyncio
    async def test_plan_mode_from_settings(self, tmp_path, monkeypatch):
        """When settings.permissions.default_mode is 'plan', agent starts in plan mode."""
        mock_model = MagicMock()
        mock_model.provider = "test"
        mock_model.model_id = "test-model"
        monkeypatch.setattr("basket_ai.api.get_model", lambda *args, **kwargs: mock_model)
        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        settings_manager = SettingsManager(settings_dir / "settings.json")
        settings = settings_manager.load()
        settings.sessions_dir = str(sessions_dir)
        settings.permissions = PermissionsSettings(default_mode="plan")
        settings_manager.save(settings)
        agent = CodingAgent(settings_manager=settings_manager, load_extensions=False)
        assert agent.get_plan_mode() is True

    @pytest.mark.asyncio
    async def test_plan_mode_forbidden_tools_return_disabled_message(self, mock_coding_agent):
        """When plan mode is on, write/edit/bash/todo_write return PLAN_MODE_DISABLED_MESSAGE."""
        mock_coding_agent.set_plan_mode(True)
        for tool in mock_coding_agent.agent.tools:
            if tool.name not in PLAN_MODE_FORBIDDEN_TOOLS:
                continue
            if tool.name == "write":
                result = await tool.executor.execute(file_path="/tmp/x", content="y")
            elif tool.name == "edit":
                result = await tool.executor.execute(file_path="/tmp/x", old_string="a", new_string="b")
            elif tool.name == "bash":
                result = await tool.executor.execute(command="echo 1")
            elif tool.name == "todo_write":
                result = await tool.executor.execute(todos=[])
            else:
                continue
            assert result == PLAN_MODE_DISABLED_MESSAGE, f"Tool {tool.name} should return disabled message"

    @pytest.mark.asyncio
    async def test_plan_mode_system_prompt_suffix(self, mock_coding_agent):
        """When plan mode is on, get_system_prompt_for_run() includes Plan mode instructions."""
        mock_coding_agent.set_plan_mode(True)
        prompt = mock_coding_agent.get_system_prompt_for_run()
        assert "Plan mode" in prompt
        assert "read-only" in prompt.lower()
        assert "Analysis" in prompt and "Plan" in prompt


@pytest.mark.integration
class TestGatewayPlanMode:
    """Gateway /plan message handling."""

    @pytest.mark.asyncio
    async def test_gateway_plan_toggle_returns_plan_mode_and_sends_event(self, mock_coding_agent):
        """When gateway run() receives /plan on, it sets plan mode, sends plan_mode event, and returns without running agent."""
        from basket_gateway.gateway import AgentGateway

        events = []

        async def event_sink(payload: dict) -> None:
            events.append(payload)

        def factory():
            return mock_coding_agent

        gateway = AgentGateway(agent_factory=factory)
        out = await gateway.run("default", "/plan on", event_sink=event_sink)
        assert out == "Plan mode on"
        assert mock_coding_agent.get_plan_mode() is True
        assert any(p.get("type") == "plan_mode" and p.get("value") is True for p in events)

        events.clear()
        out = await gateway.run("default", "/plan off", event_sink=event_sink)
        assert out == "Plan mode off"
        assert mock_coding_agent.get_plan_mode() is False
        assert any(p.get("type") == "plan_mode" and p.get("value") is False for p in events)


@pytest.mark.integration
class TestAskUserQuestionAndResume:
    """ask_user_question tool and pending_asks resume flow."""

    @pytest.mark.asyncio
    async def test_ask_user_question_tool_sets_last_and_returns_placeholder(
        self, mock_coding_agent
    ):
        """Tool sets _last_ask_user_question and returns placeholder string."""
        from basket_assistant.tools.ask_user_question import ASK_USER_QUESTION_PLACEHOLDER

        tool = next(
            (t for t in mock_coding_agent.agent.tools if t.name == "ask_user_question"),
            None,
        )
        assert tool is not None
        out = await tool.executor.execute(
            question="Which option?", options=[{"id": "a", "label": "A"}]
        )
        assert out == ASK_USER_QUESTION_PLACEHOLDER
        assert mock_coding_agent._last_ask_user_question == {
            "question": "Which option?",
            "options": [{"id": "a", "label": "A"}],
        }

    @pytest.mark.asyncio
    async def test_tool_call_end_merge_appends_pending_ask(self, mock_coding_agent):
        """When agent_tool_call_end fires for ask_user_question, merge tool_call_id and append to _pending_asks."""
        mock_coding_agent._last_ask_user_question = {
            "question": "Q?",
            "options": [],
        }
        handlers = mock_coding_agent.agent.event_handlers.get(
            "agent_tool_call_end", []
        )
        for h in handlers:
            if asyncio.iscoroutinefunction(h):
                await h({
                    "tool_name": "ask_user_question",
                    "tool_call_id": "call_abc",
                    "result": "placeholder",
                    "error": None,
                })
            else:
                h({
                    "tool_name": "ask_user_question",
                    "tool_call_id": "call_abc",
                    "result": "placeholder",
                    "error": None,
                })
        assert mock_coding_agent._last_ask_user_question is None
        assert len(mock_coding_agent._pending_asks) == 1
        assert mock_coding_agent._pending_asks[0] == {
            "tool_call_id": "call_abc",
            "question": "Q?",
            "options": [],
        }

    @pytest.mark.asyncio
    async def test_try_resume_pending_ask_replaces_content_and_runs(
        self, mock_coding_agent, monkeypatch
    ):
        """try_resume_pending_ask replaces ToolResultMessage content, removes pending, and runs."""
        mock_coding_agent.context.messages.append(
            ToolResultMessage(
                role="toolResult",
                tool_call_id="call_1",
                tool_name="ask_user_question",
                content=[TextContent(type="text", text="placeholder")],
                timestamp=0,
            )
        )
        mock_coding_agent._pending_asks = [
            {"tool_call_id": "call_1", "question": "Q?", "options": []}
        ]
        run_called = []

        async def mock_run(*args, **kwargs):
            run_called.append(1)

        monkeypatch.setattr(
            mock_coding_agent,
            "_run_with_trajectory_if_enabled",
            mock_run,
        )
        resumed = await mock_coding_agent.try_resume_pending_ask("user answer")
        assert resumed is True
        assert mock_coding_agent._pending_asks == []
        tr_msg = next(
            m
            for m in mock_coding_agent.context.messages
            if getattr(m, "role", None) == "toolResult"
            and getattr(m, "tool_call_id", None) == "call_1"
        )
        assert len(tr_msg.content) == 1
        assert tr_msg.content[0].text == "user answer"
        assert len(run_called) == 1

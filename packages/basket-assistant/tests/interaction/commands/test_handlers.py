"""Tests for builtin command handlers."""

import pytest
from typing import Optional
from basket_assistant.interaction.commands.handlers import (
    BuiltinCommandHandlers,
    register_builtin_commands,
)
from basket_assistant.interaction.commands.registry import CommandRegistry


# Mock classes for testing
class MockSettings:
    """Mock settings object."""

    def __init__(self):
        self.model = MockModel()
        self.agent = MockAgentSettings()
        self.workspace_dir = "/home/user/.basket/workspace"

    def to_dict(self):
        return {
            "model": {
                "provider": "anthropic",
                "model_id": "claude-sonnet-4",
            },
            "agent": {
                "max_turns": 25,
                "auto_save": True,
            },
            "workspace_dir": self.workspace_dir,
        }


class MockModel:
    """Mock model settings."""

    provider = "anthropic"
    model_id = "claude-sonnet-4"


class MockAgentSettings:
    """Mock agent settings."""

    max_turns = 25
    auto_save = True


class MockSessionManager:
    """Mock session manager."""

    def __init__(self):
        self.sessions = [
            {"id": "session-1", "created_at": "2026-03-14T10:00:00"},
            {"id": "session-2", "created_at": "2026-03-14T11:00:00"},
        ]
        self.current_session_id = "session-1"

    async def list_sessions(self):
        return self.sessions

    async def load_session(self, session_id: str):
        if session_id not in [s["id"] for s in self.sessions]:
            raise ValueError(f"Session not found: {session_id}")
        self.current_session_id = session_id
        return [{"role": "user", "content": "test"}]


class MockAgent:
    """Mock agent for testing."""

    def __init__(self):
        self.settings = MockSettings()
        self.session_manager = MockSessionManager()
        self._todo_show_full = False
        self.plan_mode = False
        self.conversation = []

    def load_history(self, messages):
        self.conversation = messages


# Tests for BuiltinCommandHandlers
class TestBuiltinCommandHandlers:
    """Test builtin command handlers."""

    def test_handle_help(self):
        """Test /help command."""
        agent = MockAgent()
        handlers = BuiltinCommandHandlers(agent)

        success, error = handlers.handle_help("")

        assert success is True
        assert error == ""

    def test_handle_settings(self):
        """Test /settings command."""
        agent = MockAgent()
        handlers = BuiltinCommandHandlers(agent)

        success, error = handlers.handle_settings("")

        assert success is True
        assert error == ""

    def test_handle_todos_no_args(self):
        """Test /todos with no arguments (toggle)."""
        agent = MockAgent()
        handlers = BuiltinCommandHandlers(agent)

        # Initially False
        assert agent._todo_show_full is False

        success, error = handlers.handle_todos("")
        assert success is True
        assert error == ""
        assert agent._todo_show_full is True

        # Toggle back
        success, error = handlers.handle_todos("")
        assert success is True
        assert error == ""
        assert agent._todo_show_full is False

    def test_handle_todos_on(self):
        """Test /todos on."""
        agent = MockAgent()
        handlers = BuiltinCommandHandlers(agent)

        success, error = handlers.handle_todos("on")
        assert success is True
        assert error == ""
        assert agent._todo_show_full is True

    def test_handle_todos_off(self):
        """Test /todos off."""
        agent = MockAgent()
        agent._todo_show_full = True
        handlers = BuiltinCommandHandlers(agent)

        success, error = handlers.handle_todos("off")
        assert success is True
        assert error == ""
        assert agent._todo_show_full is False

    def test_handle_todos_invalid_arg(self):
        """Test /todos with invalid argument."""
        agent = MockAgent()
        handlers = BuiltinCommandHandlers(agent)

        success, error = handlers.handle_todos("invalid")
        assert success is False
        assert "Usage:" in error

    def test_handle_plan_no_args(self):
        """Test /plan with no arguments (toggle)."""
        agent = MockAgent()
        handlers = BuiltinCommandHandlers(agent)

        # Initially False
        assert agent.plan_mode is False

        success, error = handlers.handle_plan("")
        assert success is True
        assert error == ""
        assert agent.plan_mode is True

        # Toggle back
        success, error = handlers.handle_plan("")
        assert success is True
        assert error == ""
        assert agent.plan_mode is False

    def test_handle_plan_on(self):
        """Test /plan on."""
        agent = MockAgent()
        handlers = BuiltinCommandHandlers(agent)

        success, error = handlers.handle_plan("on")
        assert success is True
        assert error == ""
        assert agent.plan_mode is True

    def test_handle_plan_off(self):
        """Test /plan off."""
        agent = MockAgent()
        agent.plan_mode = True
        handlers = BuiltinCommandHandlers(agent)

        success, error = handlers.handle_plan("off")
        assert success is True
        assert error == ""
        assert agent.plan_mode is False

    def test_handle_plan_invalid_arg(self):
        """Test /plan with invalid argument."""
        agent = MockAgent()
        handlers = BuiltinCommandHandlers(agent)

        success, error = handlers.handle_plan("invalid")
        assert success is False
        assert "Usage:" in error

    @pytest.mark.asyncio
    async def test_handle_sessions(self):
        """Test /sessions command."""
        agent = MockAgent()
        handlers = BuiltinCommandHandlers(agent)

        success, error = await handlers.handle_sessions("")

        assert success is True
        assert error == ""

    @pytest.mark.asyncio
    async def test_handle_sessions_no_manager(self):
        """Test /sessions when session_manager is None."""
        agent = MockAgent()
        agent.session_manager = None
        handlers = BuiltinCommandHandlers(agent)

        success, error = await handlers.handle_sessions("")

        assert success is False
        assert "Session management not available" in error

    @pytest.mark.asyncio
    async def test_handle_open_success(self):
        """Test /open command with valid session."""
        agent = MockAgent()
        handlers = BuiltinCommandHandlers(agent)

        success, error = await handlers.handle_open("session-2")

        assert success is True
        assert error == ""
        assert agent.session_manager.current_session_id == "session-2"
        assert len(agent.conversation) > 0

    @pytest.mark.asyncio
    async def test_handle_open_no_args(self):
        """Test /open without session ID."""
        agent = MockAgent()
        handlers = BuiltinCommandHandlers(agent)

        success, error = await handlers.handle_open("")

        assert success is False
        assert "Usage:" in error

    @pytest.mark.asyncio
    async def test_handle_open_not_found(self):
        """Test /open with non-existent session."""
        agent = MockAgent()
        handlers = BuiltinCommandHandlers(agent)

        success, error = await handlers.handle_open("invalid-session")

        assert success is False
        assert "not found" in error.lower()

    @pytest.mark.asyncio
    async def test_handle_open_no_manager(self):
        """Test /open when session_manager is None."""
        agent = MockAgent()
        agent.session_manager = None
        handlers = BuiltinCommandHandlers(agent)

        success, error = await handlers.handle_open("session-2")

        assert success is False
        assert "Session management not available" in error


class TestRegisterBuiltinCommands:
    """Test builtin command registration."""

    def test_register_builtin_commands(self):
        """Test that all builtin commands are registered."""
        agent = MockAgent()
        registry = CommandRegistry(agent)

        # Commands should be auto-registered in __init__
        # Check that all expected commands exist
        assert registry.get_command("help") is not None
        assert registry.get_command("settings") is not None
        assert registry.get_command("todos") is not None
        assert registry.get_command("plan") is not None
        assert registry.get_command("sessions") is not None
        assert registry.get_command("open") is not None

    def test_command_aliases(self):
        """Test that command aliases work."""
        agent = MockAgent()
        registry = CommandRegistry(agent)

        # Test alias resolution
        assert registry.get_command("/help") is not None
        assert registry.get_command("/settings") is not None
        assert registry.get_command("/todos") is not None
        assert registry.get_command("/plan") is not None
        assert registry.get_command("/sessions") is not None
        assert registry.get_command("/open") is not None

    def test_command_execution(self):
        """Test that registered commands can be executed."""
        agent = MockAgent()
        registry = CommandRegistry(agent)

        # Test sync command
        success, error = registry.execute_command("help", "")
        assert success is True

        # Test async command requires await
        cmd = registry.get_command("sessions")
        assert cmd is not None
        assert cmd.is_async is True

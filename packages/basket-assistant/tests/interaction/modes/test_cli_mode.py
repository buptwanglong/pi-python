"""Tests for CLIMode."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from basket_assistant.interaction.modes.cli import CLIMode
from basket_assistant.core.events.publisher import EventPublisher
from basket_assistant.adapters.cli import CLIAdapter


@pytest.fixture
def mock_agent():
    """Create a mock agent with necessary attributes."""
    agent = MagicMock()
    agent.session_manager = MagicMock()
    agent.session_manager.create_session = AsyncMock(return_value="test-session-id")
    agent.set_session_id = AsyncMock()
    agent._session_id = None
    agent.context = MagicMock()
    agent.context.messages = []
    agent._pending_asks = []
    agent.agent = MagicMock()
    agent.agent.run = AsyncMock()
    agent.model = MagicMock()
    agent.model.model_id = "test-model"
    agent.on = MagicMock()
    return agent


class TestCLIModeInitialization:
    """Test CLIMode initialization."""

    def test_init_stores_verbose_flag(self, mock_agent):
        """Test that initialization stores verbose flag."""
        mode = CLIMode(mock_agent, verbose=True)
        assert mode.verbose is True

        mode2 = CLIMode(mock_agent, verbose=False)
        assert mode2.verbose is False

    def test_init_defaults_verbose_to_false(self, mock_agent):
        """Test that verbose defaults to False."""
        mode = CLIMode(mock_agent)
        assert mode.verbose is False

    @pytest.mark.asyncio
    async def test_setup_publisher_adapter_creates_cli_adapter(self, mock_agent):
        """Test that setup_publisher_adapter creates CLIAdapter."""
        mode = CLIMode(mock_agent, verbose=True)
        publisher, adapter = mode.setup_publisher_adapter()

        assert isinstance(publisher, EventPublisher)
        assert isinstance(adapter, CLIAdapter)
        assert adapter.verbose is True


class TestTodoBlockFormatting:
    """Test todo block formatting."""

    def test_format_todo_block_empty_list(self, mock_agent):
        """Test formatting empty todo list."""
        mode = CLIMode(mock_agent)
        result = mode._format_todo_block([])
        assert result == ""

    def test_format_todo_block_single_pending(self, mock_agent):
        """Test formatting single pending todo."""
        mode = CLIMode(mock_agent)
        todos = [{"id": 1, "title": "Test task", "done": False}]
        result = mode._format_todo_block(todos)
        assert "[ ] 1. Test task" in result

    def test_format_todo_block_single_done(self, mock_agent):
        """Test formatting single done todo."""
        mode = CLIMode(mock_agent)
        todos = [{"id": 1, "title": "Test task", "done": True}]
        result = mode._format_todo_block(todos)
        assert "[✓] 1. Test task" in result

    def test_format_todo_block_mixed_todos(self, mock_agent):
        """Test formatting mixed todo list."""
        mode = CLIMode(mock_agent)
        todos = [
            {"id": 1, "title": "Task 1", "done": False},
            {"id": 2, "title": "Task 2", "done": True},
            {"id": 3, "title": "Task 3", "done": False},
        ]
        result = mode._format_todo_block(todos)
        assert "[ ] 1. Task 1" in result
        assert "[✓] 2. Task 2" in result
        assert "[ ] 3. Task 3" in result


class TestRunLoop:
    """Test CLI run loop."""

    @pytest.mark.asyncio
    async def test_run_processes_input_and_continues(self, mock_agent):
        """Test that run loop processes input and continues."""
        mode = CLIMode(mock_agent)
        await mode.initialize()

        # Mock input to return "Hello" then "/quit"
        inputs = ["Hello", "/quit"]
        input_iter = iter(inputs)

        with patch("builtins.input", side_effect=lambda prompt: next(input_iter)):
            await mode.run()

        # Should have called process_and_run_agent twice
        assert len(mock_agent.context.messages) >= 1

    @pytest.mark.asyncio
    async def test_run_handles_keyboard_interrupt(self, mock_agent):
        """Test that run loop handles KeyboardInterrupt gracefully."""
        mode = CLIMode(mock_agent)
        await mode.initialize()

        with patch("builtins.input", side_effect=KeyboardInterrupt()):
            # Should not raise
            await mode.run()

    @pytest.mark.asyncio
    async def test_run_handles_eof_error(self, mock_agent):
        """Test that run loop handles EOFError gracefully."""
        mode = CLIMode(mock_agent)
        await mode.initialize()

        with patch("builtins.input", side_effect=EOFError()):
            # Should not raise
            await mode.run()

    @pytest.mark.asyncio
    async def test_run_exits_on_quit_command(self, mock_agent):
        """Test that run exits on /quit command."""
        mode = CLIMode(mock_agent)
        await mode.initialize()

        with patch("builtins.input", return_value="/quit"):
            await mode.run()

        # Should have exited cleanly

    @pytest.mark.asyncio
    async def test_run_prints_todo_list_if_present(self, mock_agent):
        """Test that run prints todo list if agent has todos."""
        mode = CLIMode(mock_agent)
        await mode.initialize()

        # Mock todo list
        mock_agent.todo_list = [
            {"id": 1, "title": "Test task", "done": False}
        ]

        with patch("builtins.input", return_value="/quit"), patch("builtins.print") as mock_print:
            await mode.run()

        # Should have printed todo block
        calls = [str(call) for call in mock_print.call_args_list]
        assert any("[ ] 1. Test task" in str(call) for call in calls)

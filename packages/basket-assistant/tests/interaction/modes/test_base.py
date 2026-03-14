"""Tests for InteractionMode base class."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from basket_assistant.interaction.modes.base import InteractionMode
from basket_assistant.interaction.errors import ModeInitializationError
from basket_ai.types import UserMessage


class ConcreteMode(InteractionMode):
    """Concrete implementation for testing."""

    def __init__(self, agent):
        self.publisher = None
        self.adapter = None
        super().__init__(agent)

    def setup_publisher_adapter(self):
        """Return mock publisher and adapter."""
        self.publisher = MagicMock()
        self.adapter = MagicMock()
        return self.publisher, self.adapter

    async def run(self) -> None:
        """Minimal run implementation."""
        pass


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
    return agent


class TestInteractionModeInitialization:
    """Test InteractionMode initialization."""

    def test_init_creates_command_registry(self, mock_agent):
        """Test that initialization creates a command registry."""
        mode = ConcreteMode(mock_agent)
        assert mode.command_registry is not None
        assert mode.agent is mock_agent

    def test_init_creates_input_processor(self, mock_agent):
        """Test that initialization creates an input processor."""
        mode = ConcreteMode(mock_agent)
        assert mode.input_processor is not None
        assert mode.input_processor.agent is mock_agent
        assert mode.input_processor.command_registry is mode.command_registry

    def test_init_sets_initial_state(self, mock_agent):
        """Test that initialization sets initial state."""
        mode = ConcreteMode(mock_agent)
        assert mode.agent is mock_agent
        assert mode.publisher is None
        assert mode.adapter is None


class TestSessionManagement:
    """Test session creation and restoration."""

    @pytest.mark.asyncio
    async def test_initialize_creates_new_session(self, mock_agent):
        """Test that initialize creates a new session when none exists."""
        mode = ConcreteMode(mock_agent)
        await mode.initialize()

        mock_agent.session_manager.create_session.assert_called_once()
        mock_agent.set_session_id.assert_called_once()
        assert mode.publisher is not None
        assert mode.adapter is not None

    @pytest.mark.asyncio
    async def test_initialize_restores_existing_session(self, mock_agent):
        """Test that initialize restores existing session."""
        mock_agent._session_id = "existing-session"
        mode = ConcreteMode(mock_agent)
        await mode.initialize()

        mock_agent.session_manager.create_session.assert_not_called()
        mock_agent.set_session_id.assert_called_once_with("existing-session", load_history=True)

    @pytest.mark.asyncio
    async def test_initialize_sets_up_publisher_adapter(self, mock_agent):
        """Test that initialize calls setup_publisher_adapter."""
        mode = ConcreteMode(mock_agent)
        await mode.initialize()

        assert mode.publisher is not None
        assert mode.adapter is not None

    @pytest.mark.asyncio
    async def test_initialize_raises_on_session_creation_failure(self, mock_agent):
        """Test that initialize raises ModeInitializationError on session failure."""
        mock_agent.session_manager.create_session.side_effect = RuntimeError("Session error")
        mode = ConcreteMode(mock_agent)

        with pytest.raises(ModeInitializationError):
            await mode.initialize()


class TestPublisherAdapterSetup:
    """Test publisher and adapter lifecycle."""

    @pytest.mark.asyncio
    async def test_setup_publisher_adapter_called_on_initialize(self, mock_agent):
        """Test that setup_publisher_adapter is called during initialize."""
        mode = ConcreteMode(mock_agent)
        await mode.initialize()

        assert mode.publisher is not None
        assert mode.adapter is not None

    @pytest.mark.asyncio
    async def test_cleanup_cleans_adapter(self, mock_agent):
        """Test that cleanup cleans up adapter resources."""
        mode = ConcreteMode(mock_agent)
        await mode.initialize()

        mock_adapter = mode.adapter
        mock_adapter.cleanup = MagicMock()

        await mode.cleanup()
        mock_adapter.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_without_cleanup_method(self, mock_agent):
        """Test that cleanup handles adapters without cleanup method."""
        mode = ConcreteMode(mock_agent)
        await mode.initialize()

        # Remove cleanup method from adapter
        mode.adapter = MagicMock(spec=[])  # No cleanup method

        # Should not raise
        await mode.cleanup()


class TestInputProcessing:
    """Test input processing and agent execution."""

    @pytest.mark.asyncio
    async def test_process_and_run_agent_with_normal_input(self, mock_agent):
        """Test processing normal user input and running agent."""
        mode = ConcreteMode(mock_agent)
        await mode.initialize()

        result = await mode.process_and_run_agent("Hello, agent!", stream=True)

        # Should return True to continue
        assert result is True

        # Agent should be run
        mock_agent.agent.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_and_run_agent_with_quit_command(self, mock_agent):
        """Test that /quit or /exit returns False."""
        mode = ConcreteMode(mock_agent)
        await mode.initialize()

        # Register quit command
        mode.command_registry.register("quit", lambda: None, "Quit")

        result = await mode.process_and_run_agent("/quit", stream=False)

        # Should return False to exit
        assert result is False

    @pytest.mark.asyncio
    async def test_process_and_run_agent_with_exit_command(self, mock_agent):
        """Test that /exit command returns False."""
        mode = ConcreteMode(mock_agent)
        await mode.initialize()

        # Register exit command
        mode.command_registry.register("exit", lambda: None, "Exit")

        result = await mode.process_and_run_agent("/exit", stream=False)

        # Should return False to exit
        assert result is False

    @pytest.mark.asyncio
    async def test_process_and_run_agent_handles_command(self, mock_agent):
        """Test that commands are handled without running agent."""
        mode = ConcreteMode(mock_agent)
        await mode.initialize()

        # Register a test command
        mode.command_registry.register("test", lambda: "Test result", "Test command")

        result = await mode.process_and_run_agent("/test", stream=False)

        # Should return True to continue
        assert result is True

        # Agent should not be run
        mock_agent.agent.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_and_run_agent_with_skill_invocation(self, mock_agent):
        """Test that skill invocation updates system prompt."""
        mode = ConcreteMode(mock_agent)
        await mode.initialize()

        # Mock get_system_prompt_for_run
        mock_agent.get_system_prompt_for_run = MagicMock(return_value="Updated system prompt")

        # Mock input processor to return skill invocation
        from basket_assistant.interaction.processors.input_processor import ProcessResult
        from basket_ai.types import UserMessage

        skill_message = UserMessage(role="user", content="Load skill", timestamp=0)
        mode.input_processor.process = AsyncMock(
            return_value=ProcessResult(
                action="send_to_agent", message=skill_message, invoked_skill_id="test-skill"
            )
        )

        result = await mode.process_and_run_agent("/skill test-skill", stream=False)

        # Should return True to continue
        assert result is True

        # System prompt should be updated
        mock_agent.get_system_prompt_for_run.assert_called_once_with("test-skill")
        assert mock_agent.context.systemPrompt == "Updated system prompt"


class TestErrorRecovery:
    """Test error recovery and context restoration."""

    @pytest.mark.asyncio
    async def test_error_recovery_restores_context(self, mock_agent):
        """Test that error recovery restores message context."""
        mode = ConcreteMode(mock_agent)
        await mode.initialize()

        # Setup initial context
        mock_agent.context.messages = [
            UserMessage(role="user", content="Initial", timestamp=0)
        ]
        initial_len = len(mock_agent.context.messages)

        # Make agent.run raise an error
        mock_agent.agent.run.side_effect = RuntimeError("Test error")

        # This should recover from error
        result = await mode.process_and_run_agent("Test input", stream=False)

        # Should return True to continue (error was handled)
        assert result is True

        # Context should be restored (new message removed)
        assert len(mock_agent.context.messages) == initial_len

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_restores_context(self, mock_agent):
        """Test that KeyboardInterrupt is caught and context restored."""
        mode = ConcreteMode(mock_agent)
        await mode.initialize()

        # Setup initial context
        mock_agent.context.messages = []
        initial_len = len(mock_agent.context.messages)

        # Make agent.run raise KeyboardInterrupt
        mock_agent.agent.run.side_effect = KeyboardInterrupt()

        # This should catch interrupt
        result = await mode.process_and_run_agent("Test input", stream=False)

        # Should return True to continue
        assert result is True

        # Context should be restored
        assert len(mock_agent.context.messages) == initial_len

    @pytest.mark.asyncio
    async def test_agent_run_error_is_logged(self, mock_agent):
        """Test that agent run errors are logged."""
        mode = ConcreteMode(mock_agent)
        await mode.initialize()

        mock_agent.agent.run.side_effect = RuntimeError("Test error")

        with patch("basket_assistant.interaction.modes.base.logger") as mock_logger:
            await mode.process_and_run_agent("Test input", stream=False)
            mock_logger.error.assert_called()


class TestAbstractMethods:
    """Test abstract method requirements."""

    def test_cannot_instantiate_base_class(self):
        """Test that InteractionMode cannot be instantiated directly."""
        with pytest.raises(TypeError):
            InteractionMode(MagicMock())  # type: ignore

    def test_subclass_must_implement_setup_publisher_adapter(self, mock_agent):
        """Test that subclass must implement setup_publisher_adapter."""

        class IncompleteMode(InteractionMode):
            async def run(self):
                pass

        # Missing setup_publisher_adapter
        with pytest.raises(TypeError):
            IncompleteMode(mock_agent)  # type: ignore

    def test_subclass_must_implement_run(self, mock_agent):
        """Test that subclass must implement run."""

        class IncompleteMode(InteractionMode):
            def setup_publisher_adapter(self):
                return MagicMock(), MagicMock()

        # Missing run
        with pytest.raises(TypeError):
            IncompleteMode(mock_agent)  # type: ignore

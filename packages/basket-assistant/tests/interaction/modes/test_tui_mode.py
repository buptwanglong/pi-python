"""Tests for TUIMode."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from basket_assistant.interaction.modes.tui import TUIMode
from basket_assistant.core.events.publisher import EventPublisher
from basket_assistant.adapters.tui import TUIAdapter


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


@pytest.fixture
def mock_tui_app():
    """Create a mock TUI app."""
    app = MagicMock()
    app.event_bus = MagicMock()
    app.run_async = AsyncMock()
    return app


class TestTUIModeInitialization:
    """Test TUIMode initialization."""

    def test_init_stores_max_columns(self, mock_agent):
        """Test that initialization stores max_columns."""
        mode = TUIMode(mock_agent, max_columns=120)
        assert mode.max_columns == 120

    def test_init_defaults_max_columns_to_none(self, mock_agent):
        """Test that max_columns defaults to None."""
        mode = TUIMode(mock_agent)
        assert mode.max_columns is None

    def test_init_creates_tui_app(self, mock_agent):
        """Test that initialization creates TUI app."""
        with patch("basket_assistant.interaction.modes.tui.PiCodingAgentApp") as MockApp:
            mock_app = MagicMock()
            mock_app.event_bus = MagicMock()
            MockApp.return_value = mock_app

            mode = TUIMode(mock_agent)

            MockApp.assert_called_once_with(
                coding_agent=mock_agent,
                max_cols=None
            )
            assert mode.tui_app is mock_app

    def test_setup_publisher_adapter_creates_tui_adapter(self, mock_agent):
        """Test that setup_publisher_adapter creates TUIAdapter."""
        with patch("basket_assistant.interaction.modes.tui.PiCodingAgentApp") as MockApp:
            mock_app = MagicMock()
            mock_event_bus = MagicMock()
            mock_app.event_bus = mock_event_bus
            MockApp.return_value = mock_app

            mode = TUIMode(mock_agent)
            publisher, adapter = mode.setup_publisher_adapter()

            assert isinstance(publisher, EventPublisher)
            assert isinstance(adapter, TUIAdapter)
            assert adapter.event_bus is mock_event_bus


class TestInputHandling:
    """Test TUI input handling."""

    @pytest.mark.asyncio
    async def test_on_user_input_processes_and_runs_agent(self, mock_agent):
        """Test that user input handler processes input and runs agent."""
        with patch("basket_assistant.interaction.modes.tui.PiCodingAgentApp") as MockApp:
            mock_app = MagicMock()
            mock_app.event_bus = MagicMock()
            MockApp.return_value = mock_app

            mode = TUIMode(mock_agent)
            await mode.initialize()

            # Create mock event
            mock_event = MagicMock()
            mock_event.text = "Hello, agent!"

            # Call handler
            await mode._on_user_input(mock_event)

            # Should have processed and run agent
            assert len(mock_agent.context.messages) >= 1

    @pytest.mark.asyncio
    async def test_on_user_input_handles_empty_input(self, mock_agent):
        """Test that empty input is ignored."""
        with patch("basket_assistant.interaction.modes.tui.PiCodingAgentApp") as MockApp:
            mock_app = MagicMock()
            mock_app.event_bus = MagicMock()
            MockApp.return_value = mock_app

            mode = TUIMode(mock_agent)
            await mode.initialize()

            # Create mock event with empty text
            mock_event = MagicMock()
            mock_event.text = ""

            # Call handler
            await mode._on_user_input(mock_event)

            # Should not have run agent
            mock_agent.agent.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_user_input_handles_whitespace_only(self, mock_agent):
        """Test that whitespace-only input is ignored."""
        with patch("basket_assistant.interaction.modes.tui.PiCodingAgentApp") as MockApp:
            mock_app = MagicMock()
            mock_app.event_bus = MagicMock()
            MockApp.return_value = mock_app

            mode = TUIMode(mock_agent)
            await mode.initialize()

            # Create mock event with whitespace
            mock_event = MagicMock()
            mock_event.text = "   \n\t  "

            # Call handler
            await mode._on_user_input(mock_event)

            # Should not have run agent
            mock_agent.agent.run.assert_not_called()


class TestRunLoop:
    """Test TUI run loop."""

    @pytest.mark.asyncio
    async def test_run_starts_tui_app(self, mock_agent):
        """Test that run starts the TUI app."""
        with patch("basket_assistant.interaction.modes.tui.PiCodingAgentApp") as MockApp:
            mock_app = MagicMock()
            mock_app.event_bus = MagicMock()
            mock_app.run_async = AsyncMock()
            MockApp.return_value = mock_app

            mode = TUIMode(mock_agent)
            await mode.initialize()

            # Run the mode
            await mode.run()

            # Should have started TUI app
            mock_app.run_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_sets_input_handler(self, mock_agent):
        """Test that run sets the input handler."""
        with patch("basket_assistant.interaction.modes.tui.PiCodingAgentApp") as MockApp:
            mock_app = MagicMock()
            mock_app.event_bus = MagicMock()
            mock_app.run_async = AsyncMock()
            MockApp.return_value = mock_app

            mode = TUIMode(mock_agent)
            await mode.initialize()

            # Run the mode
            await mode.run()

            # Should have set input handler
            assert mode.tui_app.set_input_handler.called

    @pytest.mark.asyncio
    async def test_run_with_max_columns(self, mock_agent):
        """Test that max_columns is passed to TUI app."""
        with patch("basket_assistant.interaction.modes.tui.PiCodingAgentApp") as MockApp:
            mock_app = MagicMock()
            mock_app.event_bus = MagicMock()
            mock_app.run_async = AsyncMock()
            MockApp.return_value = mock_app

            mode = TUIMode(mock_agent, max_columns=100)

            # TUI app should be created with max_columns
            MockApp.assert_called_once_with(
                coding_agent=mock_agent,
                max_cols=100
            )

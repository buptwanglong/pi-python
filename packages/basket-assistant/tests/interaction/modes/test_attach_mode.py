"""Tests for AttachMode."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from basket_assistant.interaction.modes.attach import AttachMode
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


class TestAttachModeInitialization:
    """Test AttachMode initialization."""

    def test_init_stores_bind_and_port(self, mock_agent):
        """Test that initialization stores bind host and port."""
        mode = AttachMode(mock_agent, bind="0.0.0.0", port=8080)
        assert mode.bind == "0.0.0.0"
        assert mode.port == 8080

    def test_init_defaults_bind_and_port(self, mock_agent):
        """Test that bind and port have defaults."""
        mode = AttachMode(mock_agent)
        assert mode.bind == "127.0.0.1"
        assert mode.port == 7681

    def test_init_creates_tui_app(self, mock_agent):
        """Test that initialization creates TUI app."""
        with patch("basket_assistant.interaction.modes.attach.PiCodingAgentApp") as MockApp:
            mock_app = MagicMock()
            mock_app.event_bus = MagicMock()
            MockApp.return_value = mock_app

            mode = AttachMode(mock_agent)

            MockApp.assert_called_once_with(coding_agent=mock_agent)
            assert mode.tui_app is mock_app

    def test_setup_publisher_adapter_creates_tui_adapter(self, mock_agent):
        """Test that setup_publisher_adapter creates TUIAdapter."""
        with patch("basket_assistant.interaction.modes.attach.PiCodingAgentApp") as MockApp:
            mock_app = MagicMock()
            mock_event_bus = MagicMock()
            mock_app.event_bus = mock_event_bus
            MockApp.return_value = mock_app

            mode = AttachMode(mock_agent)
            publisher, adapter = mode.setup_publisher_adapter()

            assert isinstance(publisher, EventPublisher)
            assert isinstance(adapter, TUIAdapter)
            assert adapter.event_bus is mock_event_bus


class TestInputHandling:
    """Test WebSocket input handling."""

    @pytest.mark.asyncio
    async def test_on_user_input_processes_and_runs_agent(self, mock_agent):
        """Test that user input handler processes input and runs agent."""
        with patch("basket_assistant.interaction.modes.attach.PiCodingAgentApp") as MockApp:
            mock_app = MagicMock()
            mock_app.event_bus = MagicMock()
            MockApp.return_value = mock_app

            mode = AttachMode(mock_agent)
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
        with patch("basket_assistant.interaction.modes.attach.PiCodingAgentApp") as MockApp:
            mock_app = MagicMock()
            mock_app.event_bus = MagicMock()
            MockApp.return_value = mock_app

            mode = AttachMode(mock_agent)
            await mode.initialize()

            # Create mock event with empty text
            mock_event = MagicMock()
            mock_event.text = ""

            # Call handler
            await mode._on_user_input(mock_event)

            # Should not have run agent
            mock_agent.agent.run.assert_not_called()


class TestWebSocketServer:
    """Test WebSocket server functionality."""

    @pytest.mark.asyncio
    async def test_run_attach_server_raises_not_implemented(self, mock_agent):
        """Test that _run_attach_server raises NotImplementedError."""
        with patch("basket_assistant.interaction.modes.attach.PiCodingAgentApp") as MockApp:
            mock_app = MagicMock()
            mock_app.event_bus = MagicMock()
            MockApp.return_value = mock_app

            mode = AttachMode(mock_agent)

            # Should raise NotImplementedError
            with pytest.raises(NotImplementedError, match="WebSocket server not yet migrated"):
                await mode._run_attach_server()

    @pytest.mark.asyncio
    async def test_run_calls_run_attach_server(self, mock_agent):
        """Test that run calls _run_attach_server."""
        with patch("basket_assistant.interaction.modes.attach.PiCodingAgentApp") as MockApp:
            mock_app = MagicMock()
            mock_app.event_bus = MagicMock()
            MockApp.return_value = mock_app

            mode = AttachMode(mock_agent)
            await mode.initialize()

            # Mock _run_attach_server to not raise
            mode._run_attach_server = AsyncMock()

            # Run the mode
            await mode.run()

            # Should have called _run_attach_server
            mode._run_attach_server.assert_called_once()


class TestConfiguration:
    """Test configuration handling."""

    def test_multiple_instances_with_different_configs(self, mock_agent):
        """Test that multiple instances can have different configurations."""
        with patch("basket_assistant.interaction.modes.attach.PiCodingAgentApp"):
            mode1 = AttachMode(mock_agent, bind="0.0.0.0", port=8080)
            mode2 = AttachMode(mock_agent, bind="192.168.1.1", port=9000)

            assert mode1.bind == "0.0.0.0"
            assert mode1.port == 8080
            assert mode2.bind == "192.168.1.1"
            assert mode2.port == 9000

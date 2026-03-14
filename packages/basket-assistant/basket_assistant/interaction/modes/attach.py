"""Attach mode for remote TUI access via WebSocket."""

import logging
from typing import Any, Tuple

from basket_tui.app import PiCodingAgentApp

from basket_assistant.core.events.publisher import EventPublisher
from basket_assistant.adapters.tui import TUIAdapter

from .base import InteractionMode

logger = logging.getLogger(__name__)


class AttachMode(InteractionMode):
    """Attach mode for remote TUI access via WebSocket.

    This mode provides remote access to the TUI interface through:
    - WebSocket server for bi-directional communication
    - TUI event bus integration
    - Remote terminal rendering

    Example:
        >>> mode = AttachMode(agent, bind="0.0.0.0", port=7681)
        >>> await mode.initialize()
        >>> await mode.run()
    """

    def __init__(
        self,
        agent: Any,
        bind: str = "127.0.0.1",
        port: int = 7681
    ) -> None:
        """Initialize Attach mode.

        Args:
            agent: AssistantAgent instance
            bind: Host to bind WebSocket server to
            port: Port for WebSocket server
        """
        super().__init__(agent)
        self.bind = bind
        self.port = port

        # Create TUI app early (before initialize) so it's available
        self.tui_app = PiCodingAgentApp(coding_agent=agent)

    def setup_publisher_adapter(self) -> Tuple[Any, Any]:
        """Set up publisher and TUI adapter.

        Returns:
            Tuple of (EventPublisher, TUIAdapter)
        """
        publisher = EventPublisher(self.agent)
        adapter = TUIAdapter(publisher, self.tui_app.event_bus)
        return publisher, adapter

    async def _on_user_input(self, event: Any) -> None:
        """Handle user input from WebSocket.

        Args:
            event: UserInputEvent with text attribute
        """
        user_input = event.text.strip()

        # Ignore empty input
        if not user_input:
            return

        # Process and run agent
        await self.process_and_run_agent(user_input, stream=True)

    async def _run_attach_server(self) -> None:
        """Run the WebSocket attach server.

        This method will be implemented in Task 10 when migrating the
        relay_client.py server logic.

        Raises:
            NotImplementedError: WebSocket server not yet migrated
        """
        raise NotImplementedError(
            "WebSocket server not yet migrated from relay_client.py. "
            "This will be implemented in Task 10."
        )

    async def run(self) -> None:
        """Run the attach server.

        This method:
        1. Sets up input handler for WebSocket events
        2. Starts the WebSocket server
        3. Runs until server is shut down

        Note:
            The actual WebSocket server implementation will be migrated
            in Task 10 from the old relay_client.py file.
        """
        logger.info("Starting Attach mode: bind=%s port=%d", self.bind, self.port)

        # Set input handler
        self.tui_app.set_input_handler(self._on_user_input)

        # Run WebSocket server
        await self._run_attach_server()

        logger.info("Attach mode ended")

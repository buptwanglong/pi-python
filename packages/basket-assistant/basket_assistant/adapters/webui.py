"""WebUI adapter for sending events over WebSocket."""

import asyncio
import logging
from typing import Any, Callable

from basket_agent.types import (
    AgentEventToolCallStart,
    AgentEventToolCallEnd,
    AgentEventComplete,
    AgentEventError,
)

from .base import EventAdapter

logger = logging.getLogger(__name__)


class WebUIAdapter(EventAdapter):
    """WebUI adapter that sends events over WebSocket.

    This adapter converts AssistantEvent instances to JSON and sends them
    over a WebSocket connection for display in a web UI.

    Args:
        publisher: The EventPublisher to subscribe to
        send_func: Async function to send data over WebSocket (e.g., websocket.send)
    """

    def __init__(self, publisher: Any, send_func: Callable[[Any], Any]):
        """Initialize the WebUI adapter.

        Args:
            publisher: The EventPublisher to subscribe to
            send_func: Async function to send JSON data over WebSocket
        """
        self.send_func = send_func
        self._active = True
        super().__init__(publisher)

    def _setup_subscriptions(self) -> None:
        """Subscribe to all events."""
        self.publisher.subscribe("text_delta", self._on_text_delta)
        self.publisher.subscribe("thinking_delta", self._on_thinking_delta)
        self.publisher.subscribe("agent_tool_call_start", self._on_tool_call_start)
        self.publisher.subscribe("agent_tool_call_end", self._on_tool_call_end)
        self.publisher.subscribe("agent_complete", self._on_agent_complete)
        self.publisher.subscribe("agent_error", self._on_agent_error)

    def _send_async(self, data: dict) -> None:
        """Send data asynchronously without blocking.

        Creates a background task to send the data. If sending fails,
        marks the adapter as inactive and unsubscribes.
        """
        if not self._active:
            return

        async def _send():
            try:
                await self.send_func(data)
            except Exception as e:
                logger.error("WebSocket send failed: %s", e)
                self._active = False
                self.cleanup()

        # Create task without awaiting
        try:
            asyncio.create_task(_send())
        except RuntimeError:
            # No event loop, try synchronous send
            try:
                import json
                logger.warning(
                    "No event loop available, falling back to synchronous send"
                )
                # This will fail for actual WebSocket, but useful for testing
                self.send_func(json.dumps(data))
            except Exception as e:
                logger.error("Synchronous send failed: %s", e)
                self._active = False

    def _on_text_delta(self, event: Any) -> None:
        """Handle text_delta event."""
        self._send_async({"type": "text_delta", "delta": event.delta})

    def _on_thinking_delta(self, event: Any) -> None:
        """Handle thinking_delta event."""
        self._send_async({"type": "thinking_delta", "delta": event.delta})

    def _on_tool_call_start(self, event: AgentEventToolCallStart) -> None:
        """Handle tool_call_start event."""
        self._send_async(
            {
                "type": "tool_call_start",
                "tool_name": event.tool_name,
                "arguments": event.arguments,
                "tool_call_id": event.tool_call_id,
            }
        )

    def _on_tool_call_end(self, event: AgentEventToolCallEnd) -> None:
        """Handle tool_call_end event."""
        self._send_async(
            {
                "type": "tool_call_end",
                "tool_name": event.tool_name,
                "result": str(event.result) if event.result is not None else None,
                "error": event.error,
                "tool_call_id": event.tool_call_id,
            }
        )

    def _on_agent_complete(self, event: AgentEventComplete) -> None:
        """Handle agent_complete event."""
        self._send_async({"type": "agent_complete"})

    def _on_agent_error(self, event: AgentEventError) -> None:
        """Handle agent_error event."""
        self._send_async({"type": "agent_error", "error": event.error})

    def cleanup(self) -> None:
        """Mark adapter as inactive and stop sending."""
        self._active = False
        super().cleanup()

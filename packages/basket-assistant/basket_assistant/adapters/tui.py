"""TUI adapter for forwarding events to basket-tui EventBus."""

import logging
from typing import Any

from basket_agent.types import (
    AgentEventToolCallStart,
    AgentEventToolCallEnd,
    AgentEventComplete,
    AgentEventError,
)

from basket_assistant.core.events import EventPublisher

from .base import EventAdapter

logger = logging.getLogger(__name__)


class TUIAdapter(EventAdapter):
    """TUI adapter that forwards events to basket-tui's EventBus.

    This adapter receives typed events from basket-agent and publishes them
    to the TUI's event bus for display.

    Args:
        publisher: The EventPublisher to subscribe to
        event_bus: The TUI EventBus instance to publish to
    """

    def __init__(self, publisher: "EventPublisher", event_bus: Any):
        """Initialize the TUI adapter.

        Args:
            publisher: The EventPublisher to subscribe to
            event_bus: The TUI EventBus instance
        """
        self.event_bus = event_bus
        super().__init__(publisher)

    def _setup_subscriptions(self) -> None:
        """Subscribe to all events."""
        self.publisher.subscribe("text_delta", self._on_text_delta)
        self.publisher.subscribe("thinking_delta", self._on_thinking_delta)
        self.publisher.subscribe("agent_tool_call_start", self._on_tool_call_start)
        self.publisher.subscribe("agent_tool_call_end", self._on_tool_call_end)
        self.publisher.subscribe("agent_complete", self._on_agent_complete)
        self.publisher.subscribe("agent_error", self._on_agent_error)

    def _on_text_delta(self, event: Any) -> None:
        """Handle text_delta event."""
        try:
            self.event_bus.publish("assistant.text_delta", {"delta": event.delta})
        except Exception as e:
            logger.error("Failed to publish text_delta to TUI: %s", e, exc_info=True)

    def _on_thinking_delta(self, event: Any) -> None:
        """Handle thinking_delta event."""
        try:
            self.event_bus.publish(
                "assistant.thinking_delta", {"delta": event.delta}
            )
        except Exception as e:
            logger.error(
                "Failed to publish thinking_delta to TUI: %s", e, exc_info=True
            )

    def _on_tool_call_start(self, event: AgentEventToolCallStart) -> None:
        """Handle tool_call_start event."""
        try:
            self.event_bus.publish(
                "assistant.tool_call_start",
                {
                    "tool_name": event.tool_name,
                    "arguments": event.arguments,
                    "tool_call_id": event.tool_call_id,
                },
            )
        except Exception as e:
            logger.error(
                "Failed to publish tool_call_start to TUI: %s", e, exc_info=True
            )

    def _on_tool_call_end(self, event: AgentEventToolCallEnd) -> None:
        """Handle tool_call_end event."""
        try:
            self.event_bus.publish(
                "assistant.tool_call_end",
                {
                    "tool_name": event.tool_name,
                    "result": event.result,
                    "error": event.error,
                    "tool_call_id": event.tool_call_id,
                },
            )
        except Exception as e:
            logger.error(
                "Failed to publish tool_call_end to TUI: %s", e, exc_info=True
            )

    def _on_agent_complete(self, event: AgentEventComplete) -> None:
        """Handle agent_complete event."""
        try:
            self.event_bus.publish("assistant.agent_complete", {})
        except Exception as e:
            logger.error(
                "Failed to publish agent_complete to TUI: %s", e, exc_info=True
            )

    def _on_agent_error(self, event: AgentEventError) -> None:
        """Handle agent_error event."""
        try:
            self.event_bus.publish("assistant.agent_error", {"error": event.error})
        except Exception as e:
            logger.error("Failed to publish agent_error to TUI: %s", e, exc_info=True)

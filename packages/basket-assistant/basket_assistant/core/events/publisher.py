"""EventPublisher: Central event distribution hub.

Subscribes to basket-agent events and distributes typed events to adapters.
No conversion needed — events flow through as typed objects.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List

if TYPE_CHECKING:
    from basket_assistant.agent._protocol import AssistantAgentProtocol

logger = logging.getLogger(__name__)

# All event types the publisher subscribes to on the basket-agent
AGENT_EVENT_TYPES = (
    "text_delta",
    "thinking_delta",
    "agent_tool_call_start",
    "agent_tool_call_end",
    "agent_turn_start",
    "agent_turn_end",
    "agent_complete",
    "agent_error",
)


class EventPublisher:
    """Central event distribution hub for the assistant.

    Subscribes to basket-agent events and forwards them to adapters.
    Events are already typed — no conversion needed.

    Example:
        >>> publisher = EventPublisher(assistant)
        >>> publisher.subscribe("agent_tool_call_start", lambda e: print(e.tool_name))
    """

    def __init__(self, agent: AssistantAgentProtocol):
        self._assistant = agent
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {}
        self._setup_agent_subscriptions()

    def _setup_agent_subscriptions(self) -> None:
        """Subscribe to all agent event types with a single generic handler."""
        ba = self._assistant.agent
        for event_type in AGENT_EVENT_TYPES:
            ba.on(event_type, self._on_agent_event)

    def _on_agent_event(self, event: Any) -> None:
        """Forward typed event to subscribers."""
        event_type = event.type if hasattr(event, "type") else None
        if event_type:
            self._publish(event_type, event)

    def subscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        """Subscribe to a specific event type.

        Args:
            event_type: Event type string (e.g., "text_delta", "agent_tool_call_start")
            handler: Callback that receives the typed event
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)
            logger.debug(
                "Subscribed to %s: %s (total: %d)",
                event_type,
                handler.__name__ if hasattr(handler, "__name__") else str(handler)[:50],
                len(self._subscribers[event_type]),
            )

    def unsubscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        """Unsubscribe from a specific event type."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass

    def _publish(self, event_type: str, event: Any) -> None:
        """Publish an event to all subscribers for the given type."""
        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            return

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    "Event handler failed: type=%s handler=%s error=%s",
                    event_type,
                    handler.__name__ if hasattr(handler, "__name__") else "unknown",
                    e,
                    exc_info=True,
                )

    def cleanup(self) -> None:
        """Clean up all subscriptions."""
        self._subscribers.clear()
        logger.debug("EventPublisher cleaned up")

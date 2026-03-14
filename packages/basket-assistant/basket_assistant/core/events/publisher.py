"""EventPublisher: Central event distribution hub.

The EventPublisher subscribes to basket-agent events, converts them to standardized
AssistantEvent instances, and distributes them to registered adapters.

Key responsibilities:
- Subscribe to basket-agent events
- Convert raw dict events to typed AssistantEvent instances
- Publish events to all registered subscribers
- Handle subscriber errors gracefully (don't let one adapter crash others)
"""

import logging
from typing import Any, Callable, Dict, List

from .types import AssistantEvent, event_from_dict

logger = logging.getLogger(__name__)


class EventPublisher:
    """Central event distribution hub for the assistant.

    The EventPublisher sits between the basket-agent and UI adapters, converting
    raw agent events into standardized AssistantEvent instances and distributing
    them to subscribers.

    Example:
        >>> publisher = EventPublisher(agent)
        >>> publisher.subscribe("text_delta", lambda event: print(event.delta))
        >>> # Now all text_delta events will be printed
    """

    def __init__(self, agent: Any):
        """Initialize the event publisher.

        Args:
            agent: The basket-agent instance to listen to
        """
        self._agent = agent
        self._subscribers: Dict[str, List[Callable[[AssistantEvent], None]]] = {}

        # Subscribe to all agent events
        self._setup_agent_subscriptions()

    def _setup_agent_subscriptions(self) -> None:
        """Subscribe to basket-agent events."""
        # Text and thinking deltas
        self._agent.on("text_delta", self._on_text_delta)
        self._agent.on("thinking_delta", self._on_thinking_delta)

        # Tool calls
        self._agent.on("agent_tool_call_start", self._on_tool_call_start)
        self._agent.on("agent_tool_call_end", self._on_tool_call_end)

        # Turn lifecycle
        self._agent.on("agent_turn_start", self._on_turn_start)
        self._agent.on("agent_turn_end", self._on_turn_end)

        # Agent completion
        self._agent.on("agent_complete", self._on_agent_complete)
        self._agent.on("agent_error", self._on_agent_error)

    def subscribe(
        self, event_type: str, handler: Callable[[AssistantEvent], None]
    ) -> None:
        """Subscribe to a specific event type.

        Args:
            event_type: The event type to listen for (e.g., "text_delta")
            handler: Callback function that receives the event
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

    def unsubscribe(
        self, event_type: str, handler: Callable[[AssistantEvent], None]
    ) -> None:
        """Unsubscribe from a specific event type.

        Args:
            event_type: The event type to stop listening to
            handler: The callback function to remove
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
                logger.debug(
                    "Unsubscribed from %s: %s (remaining: %d)",
                    event_type,
                    handler.__name__
                    if hasattr(handler, "__name__")
                    else str(handler)[:50],
                    len(self._subscribers[event_type]),
                )
            except ValueError:
                pass  # Handler wasn't subscribed

    def _publish(self, event: AssistantEvent) -> None:
        """Publish an event to all subscribers.

        Catches and logs exceptions in subscriber handlers to prevent one
        failing adapter from affecting others.

        Args:
            event: The event to publish
        """
        handlers = self._subscribers.get(event.type, [])
        if not handlers:
            return

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    "Event handler failed: type=%s handler=%s error=%s",
                    event.type,
                    handler.__name__ if hasattr(handler, "__name__") else "unknown",
                    e,
                    exc_info=True,
                )
                # Don't raise, continue notifying other subscribers

    # Agent event handlers - convert dict events to typed events

    def _on_text_delta(self, event: Dict[str, Any]) -> None:
        """Handle text_delta event from agent."""
        try:
            typed_event = event_from_dict("text_delta", event)
            self._publish(typed_event)
        except Exception as e:
            logger.error("Failed to process text_delta event: %s", e, exc_info=True)

    def _on_thinking_delta(self, event: Dict[str, Any]) -> None:
        """Handle thinking_delta event from agent."""
        try:
            typed_event = event_from_dict("thinking_delta", event)
            self._publish(typed_event)
        except Exception as e:
            logger.error(
                "Failed to process thinking_delta event: %s", e, exc_info=True
            )

    def _on_tool_call_start(self, event: Dict[str, Any]) -> None:
        """Handle agent_tool_call_start event from agent."""
        try:
            typed_event = event_from_dict("agent_tool_call_start", event)
            self._publish(typed_event)
        except Exception as e:
            logger.error(
                "Failed to process tool_call_start event: %s", e, exc_info=True
            )

    def _on_tool_call_end(self, event: Dict[str, Any]) -> None:
        """Handle agent_tool_call_end event from agent."""
        try:
            typed_event = event_from_dict("agent_tool_call_end", event)
            self._publish(typed_event)
        except Exception as e:
            logger.error("Failed to process tool_call_end event: %s", e, exc_info=True)

    def _on_turn_start(self, event: Dict[str, Any]) -> None:
        """Handle agent_turn_start event from agent."""
        try:
            typed_event = event_from_dict("agent_turn_start", event)
            self._publish(typed_event)
        except Exception as e:
            logger.error("Failed to process turn_start event: %s", e, exc_info=True)

    def _on_turn_end(self, event: Dict[str, Any]) -> None:
        """Handle agent_turn_end event from agent."""
        try:
            typed_event = event_from_dict("agent_turn_end", event)
            self._publish(typed_event)
        except Exception as e:
            logger.error("Failed to process turn_end event: %s", e, exc_info=True)

    def _on_agent_complete(self, event: Dict[str, Any]) -> None:
        """Handle agent_complete event from agent."""
        try:
            typed_event = event_from_dict("agent_complete", event)
            self._publish(typed_event)
        except Exception as e:
            logger.error(
                "Failed to process agent_complete event: %s", e, exc_info=True
            )

    def _on_agent_error(self, event: Dict[str, Any]) -> None:
        """Handle agent_error event from agent."""
        try:
            typed_event = event_from_dict("agent_error", event)
            self._publish(typed_event)
        except Exception as e:
            logger.error("Failed to process agent_error event: %s", e, exc_info=True)

    def cleanup(self) -> None:
        """Clean up all subscriptions."""
        self._subscribers.clear()
        logger.debug("EventPublisher cleaned up")

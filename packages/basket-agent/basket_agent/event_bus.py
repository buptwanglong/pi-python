"""
Cross-agent event bus for pub/sub communication.

Enables agents to publish events and subscribe to event types.
Supports both sync and async handlers, wildcard subscriptions,
and built-in event history with configurable limits.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class CrossAgentEvent(BaseModel):
    """Event published through the cross-agent event bus."""

    source: str  # agent name/id
    event_type: str  # "finding", "error", "progress", "request", "completion"
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)

    model_config = ConfigDict(frozen=True)


# Common event types
EVENT_FINDING = "finding"
EVENT_ERROR = "error"
EVENT_PROGRESS = "progress"
EVENT_REQUEST = "request"
EVENT_COMPLETION = "completion"


class AgentEventBus:
    """
    Pub/sub event bus for cross-agent communication.

    Agents can subscribe to event types and publish events.
    Handlers are called in order of subscription. Subscribe to "*"
    to receive all events (wildcard).
    """

    def __init__(self, max_history: int = 100) -> None:
        self._subscribers: Dict[str, List[Callable]] = {}
        self._history: List[CrossAgentEvent] = []
        self._max_history: int = max_history

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe a handler to an event type. Use '*' for wildcard."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Unsubscribe a handler from an event type."""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                h for h in self._subscribers[event_type] if h is not handler
            ]

    async def publish(self, event: CrossAgentEvent) -> None:
        """Publish an event to all subscribers of its type (and wildcard)."""
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]

        # Gather type-specific handlers + wildcard handlers
        handlers = list(self._subscribers.get(event.event_type, []))
        if event.event_type != "*":
            handlers = handlers + list(self._subscribers.get("*", []))

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.warning(
                    "Event handler error for %s: %s", event.event_type, e
                )

    def get_history(
        self, event_type: Optional[str] = None
    ) -> List[CrossAgentEvent]:
        """Get event history, optionally filtered by type."""
        if event_type is not None:
            return [e for e in self._history if e.event_type == event_type]
        return list(self._history)

    def clear_history(self) -> None:
        """Clear all event history."""
        self._history.clear()

    @property
    def subscriber_count(self) -> Dict[str, int]:
        """Get the number of subscribers per event type."""
        return {k: len(v) for k, v in self._subscribers.items()}


__all__ = [
    "AgentEventBus",
    "CrossAgentEvent",
    "EVENT_COMPLETION",
    "EVENT_ERROR",
    "EVENT_FINDING",
    "EVENT_PROGRESS",
    "EVENT_REQUEST",
]

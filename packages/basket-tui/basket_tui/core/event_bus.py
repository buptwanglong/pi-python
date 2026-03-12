"""
Event Bus

Provides publish/subscribe pattern for decoupled communication.
"""

from typing import Callable, Dict, List, Type, TypeVar
import logging

logger = logging.getLogger(__name__)

E = TypeVar("E")


class EventBus:
    """
    Event bus for publish/subscribe communication

    Decouples event publishers from subscribers with exception isolation.
    """

    def __init__(self):
        self._handlers: Dict[Type, List[Callable]] = {}

    def subscribe(self, event_type: Type[E], handler: Callable[[E], None]) -> None:
        """
        Subscribe to event type

        Args:
            event_type: Event class to subscribe to
            handler: Callable that receives event
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"Subscribed to {event_type.__name__}")

    def unsubscribe(self, event_type: Type[E], handler: Callable[[E], None]) -> None:
        """
        Unsubscribe from event type

        Args:
            event_type: Event class
            handler: Handler to remove
        """
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                logger.debug(f"Unsubscribed from {event_type.__name__}")
            except ValueError:
                pass  # Handler not in list

    def publish(self, event: E) -> None:
        """
        Publish event to all subscribers

        Exceptions in handlers are logged but do not stop other handlers.

        Args:
            event: Event instance to publish
        """
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        logger.debug(
            f"Publishing {event_type.__name__} to {len(handlers)} handler(s)"
        )

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.exception(
                    f"Error in event handler for {event_type.__name__}: {e}"
                )

    def clear(self) -> None:
        """Clear all subscriptions"""
        self._handlers.clear()
        logger.debug("Cleared all event handlers")

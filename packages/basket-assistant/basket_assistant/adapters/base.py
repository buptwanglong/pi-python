"""Base class for event adapters.

All adapters inherit from EventAdapter and implement the _setup_subscriptions
method to register their event handlers.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from basket_assistant.core.events import EventPublisher


class EventAdapter(ABC):
    """Base class for all event adapters.

    Adapters subscribe to events from an EventPublisher and handle them
    in their own way (print to stdout, send to TUI event bus, send over WebSocket, etc.).

    Subclasses must implement _setup_subscriptions() to register their handlers.

    Example:
        >>> class MyAdapter(EventAdapter):
        ...     def _setup_subscriptions(self):
        ...         self.publisher.subscribe("text_delta", self._on_text_delta)
        ...
        ...     def _on_text_delta(self, event):
        ...         print(event.delta)
    """

    def __init__(self, publisher: "EventPublisher"):
        """Initialize the adapter.

        Args:
            publisher: The EventPublisher to subscribe to
        """
        self.publisher = publisher
        self._handlers = []  # Track handlers for cleanup
        self._setup_subscriptions()

    @abstractmethod
    def _setup_subscriptions(self) -> None:
        """Set up event subscriptions.

        Subclasses must implement this method to subscribe to events they care about.
        Use self.publisher.subscribe(event_type, handler) to register handlers.
        """
        pass

    def cleanup(self) -> None:
        """Clean up resources and unsubscribe from events.

        Subclasses can override this to add custom cleanup logic.
        """
        # Note: EventPublisher will handle unsubscription when it's cleaned up
        pass

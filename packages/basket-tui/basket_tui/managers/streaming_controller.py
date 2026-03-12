"""
StreamingController

Manages streaming output state lifecycle.
"""

from typing import TYPE_CHECKING

from ..core.streaming import StreamingState
from ..core.events import TextDeltaEvent, AgentCompleteEvent
from ..components import StreamingDisplay

if TYPE_CHECKING:
    from ..app import PiCodingAgentApp


class StreamingController:
    """
    Streaming output controller

    Manages streaming state and subscribes to events.
    """

    def __init__(self, app: "PiCodingAgentApp"):
        self._app = app
        self._state = StreamingState()

        # Subscribe to events
        app.event_bus.subscribe(TextDeltaEvent, self._on_text_delta)
        app.event_bus.subscribe(AgentCompleteEvent, self._on_complete)

    @property
    def state(self) -> StreamingState:
        return self._state

    def activate(self) -> None:
        """Activate streaming"""
        self._state.activate()
        streaming_display = self._app.query_one(StreamingDisplay)
        streaming_display.is_active = True

    def deactivate(self) -> None:
        """Deactivate streaming"""
        self._state.clear()
        streaming_display = self._app.query_one(StreamingDisplay)
        streaming_display.is_active = False

    def _on_text_delta(self, event: TextDeltaEvent) -> None:
        """Handle text delta"""
        if not self._state.is_active:
            self.activate()
        self._state.append(event.delta)

    def _on_complete(self, event: AgentCompleteEvent) -> None:
        """Handle agent complete"""
        self.deactivate()

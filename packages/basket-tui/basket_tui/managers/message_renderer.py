"""
MessageRenderer

Manages message display logic with event subscriptions.
"""

from typing import TYPE_CHECKING

from ..core.conversation import Message, ConversationContext
from ..core.events import TextDeltaEvent, ThinkingDeltaEvent, AgentCompleteEvent
from ..components import MessageList, StreamingDisplay

if TYPE_CHECKING:
    from ..app import PiCodingAgentApp


class MessageRenderer:
    """
    Message renderer manager

    Subscribes to agent events and updates message widgets.
    """

    def __init__(self, app: "PiCodingAgentApp"):
        self._app = app
        self._conversation: ConversationContext = ConversationContext()

        # Subscribe to relevant events
        app.event_bus.subscribe(TextDeltaEvent, self._on_text_delta)
        app.event_bus.subscribe(ThinkingDeltaEvent, self._on_thinking_delta)
        app.event_bus.subscribe(AgentCompleteEvent, self._on_agent_complete)

    @property
    def conversation(self) -> ConversationContext:
        """Get current conversation context"""
        return self._conversation

    def add_user_message(self, text: str) -> None:
        """Add user message"""
        msg = Message(role="user", content=text)
        self._conversation = self._conversation.add_message(msg)

        message_list = self._app.query_one(MessageList)
        message_list.add_message(msg)

    def add_system_message(self, text: str) -> None:
        """Add system message"""
        msg = Message(role="system", content=text)
        self._conversation = self._conversation.add_message(msg)

        message_list = self._app.query_one(MessageList)
        message_list.add_message(msg)

    def clear_conversation(self) -> None:
        """Clear conversation"""
        self._conversation = ConversationContext()
        message_list = self._app.query_one(MessageList)
        message_list.messages = []

    def _on_text_delta(self, event: TextDeltaEvent) -> None:
        """Handle text delta event"""
        streaming_display = self._app.query_one(StreamingDisplay)
        if not streaming_display.is_active:
            streaming_display.is_active = True
        streaming_display.append_text(event.delta)

    def _on_thinking_delta(self, event: ThinkingDeltaEvent) -> None:
        """Handle thinking delta event"""
        streaming_display = self._app.query_one(StreamingDisplay)
        if not streaming_display.is_active:
            streaming_display.is_active = True
        streaming_display.append_text(f"[thinking] {event.delta}")

    def _on_agent_complete(self, event: AgentCompleteEvent) -> None:
        """Handle agent complete - commit streaming content"""
        streaming_display = self._app.query_one(StreamingDisplay)

        if streaming_display.buffer:
            # Commit streaming content as message
            msg = Message(role="assistant", content=streaming_display.buffer)
            self._conversation = self._conversation.add_message(msg)

            message_list = self._app.query_one(MessageList)
            message_list.add_message(msg)

        # Clear streaming display
        streaming_display.clear()

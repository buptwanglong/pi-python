"""
MessageRenderer

Manages message display logic with event subscriptions.
"""

from typing import TYPE_CHECKING

from ..core.conversation import Message, ConversationContext
from ..core.events import (
    TextDeltaEvent,
    ThinkingDeltaEvent,
    AgentCompleteEvent,
    UserInputEvent,
    ToolCallStartEvent,
    ToolCallEndEvent,
)
from ..components import MessageList, StreamingDisplay, ToolDisplay

if TYPE_CHECKING:
    from ..app import PiCodingAgentApp


def _format_tool_args(args: dict) -> str:
    """Format tool arguments for display (first 2 keys)."""
    if not args:
        return ""
    keys = list(args.keys())[:2]
    preview = ", ".join(keys)
    if len(args) > 2:
        preview += "..."
    return preview


def _truncate_result(value: object, max_len: int = 200) -> str:
    """Convert result to string and truncate."""
    if value is None:
        return ""
    text = str(value)
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


class MessageRenderer:
    """
    Message renderer manager

    Subscribes to agent events and updates message widgets.
    """

    def __init__(self, app: "PiCodingAgentApp"):
        self._app = app
        self._conversation: ConversationContext = ConversationContext()

        # Subscribe to relevant events
        app.event_bus.subscribe(UserInputEvent, self._on_user_input)
        app.event_bus.subscribe(TextDeltaEvent, self._on_text_delta)
        app.event_bus.subscribe(ThinkingDeltaEvent, self._on_thinking_delta)
        app.event_bus.subscribe(AgentCompleteEvent, self._on_agent_complete)
        app.event_bus.subscribe(ToolCallStartEvent, self._on_tool_call_start)
        app.event_bus.subscribe(ToolCallEndEvent, self._on_tool_call_end)

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

    def _on_user_input(self, event: UserInputEvent) -> None:
        """Add user message to the list when user submits input."""
        self.add_user_message(event.text)

    def _on_tool_call_start(self, event: ToolCallStartEvent) -> None:
        """Update ToolDisplay when a tool call starts."""
        try:
            tool_display = self._app.query_one("#tool-display", ToolDisplay)
            tool_display.show_tool_call(
                tool_name=event.tool_name,
                arguments=event.arguments or {},
            )
        except Exception:
            pass

    def _on_tool_call_end(self, event: ToolCallEndEvent) -> None:
        """Update ToolDisplay and add tool result to message list."""
        try:
            tool_display = self._app.query_one("#tool-display", ToolDisplay)
            result_str = _truncate_result(event.result)
            tool_display.show_result(result=result_str, error=bool(event.error))
        except Exception:
            pass
        # Add tool call as a message in the conversation flow
        content = event.tool_name
        if event.error:
            content += f"\n-> error: {_truncate_result(event.error, 120)}"
        elif event.result is not None:
            content += f"\n-> {_truncate_result(event.result)}"
        msg = Message(role="tool", content=content)
        self._conversation = self._conversation.add_message(msg)
        message_list = self._app.query_one(MessageList)
        message_list.add_message(msg)

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

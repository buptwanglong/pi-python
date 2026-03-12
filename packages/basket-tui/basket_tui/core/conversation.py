"""
Immutable Conversation Context

Provides immutable data structures for managing conversation state.
"""

from dataclasses import dataclass, field
from typing import Optional
import time


@dataclass(frozen=True)
class Message:
    """
    Single message in conversation (immutable)

    Attributes:
        role: Message role (user, assistant, system, tool)
        content: Message text content
        timestamp: Unix timestamp when message was created
        tool_name: Optional tool name if this is a tool message
        tool_args: Optional tool arguments if this is a tool message
    """

    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None


@dataclass(frozen=True)
class ConversationContext:
    """
    Conversation context (immutable)

    Maintains conversation history as immutable tuple.
    All mutations return new ConversationContext instances.

    Attributes:
        messages: Tuple of messages in conversation order
    """

    messages: tuple[Message, ...] = field(default_factory=tuple)

    def add_message(self, message: Message) -> "ConversationContext":
        """
        Add message to conversation

        Args:
            message: Message to add

        Returns:
            New ConversationContext with added message
        """
        return ConversationContext(messages=self.messages + (message,))

    def clear(self) -> "ConversationContext":
        """
        Clear all messages

        Returns:
            New empty ConversationContext
        """
        return ConversationContext()

    @property
    def last_message(self) -> Optional[Message]:
        """
        Get most recent message

        Returns:
            Last message or None if empty
        """
        return self.messages[-1] if self.messages else None

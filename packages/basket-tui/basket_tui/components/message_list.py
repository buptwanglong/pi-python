"""
MessageList Widget

Displays conversation messages with reactive updates.
"""

from typing import List
from textual.widgets import Widget
from textual.reactive import reactive
from rich.text import Text

from ..core.conversation import Message


class MessageList(Widget):
    """
    Message list widget with reactive updates

    Uses Textual's reactive property system to automatically
    refresh UI when messages change.

    Attributes:
        messages: Reactive list of messages
    """

    # Reactive property - auto-triggers watch_messages when changed
    messages: reactive[List[Message]] = reactive(list, init=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messages = []

    def watch_messages(
        self, old_messages: List[Message], new_messages: List[Message]
    ) -> None:
        """
        Called automatically when messages property changes

        Args:
            old_messages: Previous message list
            new_messages: New message list
        """
        self.refresh()

    def render(self) -> Text:
        """
        Render message list to Rich Text

        Returns:
            Rendered text with styled messages
        """
        output = Text()

        for msg in self.messages:
            # Role prefix with color
            role_style = self._get_role_style(msg.role)
            output.append(f"[{msg.role}] ", style=role_style)

            # Message content
            output.append(msg.content)
            output.append("\n\n")

        return output

    def _get_role_style(self, role: str) -> str:
        """
        Get Rich style for message role

        Args:
            role: Message role

        Returns:
            Rich style string
        """
        styles = {
            "user": "cyan",
            "assistant": "green",
            "system": "yellow",
            "tool": "magenta",
        }
        return styles.get(role, "white")

    def add_message(self, message: Message) -> None:
        """
        Add message to list

        Triggers reactive update by creating new list.

        Args:
            message: Message to add
        """
        # Create new list to trigger reactive update
        self.messages = self.messages + [message]

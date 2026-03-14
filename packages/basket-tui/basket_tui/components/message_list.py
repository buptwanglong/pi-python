"""
MessageList Widget

Displays conversation messages with reactive updates.
Assistant messages are rendered as Markdown (bold, code, etc.).
"""

from typing import List, Union
from textual.widgets import Static
from textual.reactive import reactive
from rich.console import Group
from rich.text import Text
from rich.markdown import Markdown

from ..core.conversation import Message


class MessageList(Static):
    """
    Message list widget with reactive updates

    Uses Textual's reactive property system to automatically
    refresh UI when messages change. Assistant role is rendered as Markdown.

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

    def render(self) -> Union[Text, Group]:
        """
        Render message list. Assistant messages use Markdown so **bold** etc. render correctly.
        """
        parts: List[Union[Text, Group]] = []

        for msg in self.messages:
            role_style = self._get_role_style(msg.role)
            prefix = Text(f"[{msg.role}] ", style=role_style)

            content = (msg.content or "").strip()
            if msg.role == "assistant" and content:
                try:
                    content_renderable: Union[Text, Markdown] = Markdown(content)
                except Exception:
                    content_renderable = Text(content)
                parts.append(Group(prefix, content_renderable))
            else:
                block = Text()
                block.append_text(prefix)
                block.append(content)
                parts.append(block)
            parts.append(Text("\n\n"))

        if not parts:
            return Text()
        return Group(*parts)

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

"""
Message Rendering Module

This module provides the MessageRenderer class that handles
formatting and rendering of different message types in the TUI.
"""

import json
from typing import Any, Union
from rich.text import Text
from rich.markdown import Markdown

from ..constants import (
    THINKING_EMOJI,
    ERROR_PREFIX,
    INFO_EMOJI,
    THINKING_STYLE,
    USER_MESSAGE_STYLE,
    SYSTEM_MESSAGE_STYLE,
)


class MessageRenderer:
    """
    Handles rendering of different message types in the TUI.

    This class encapsulates all formatting logic for user messages,
    system messages, assistant messages, and tool calls.
    """

    @staticmethod
    def render_user_message(content: str) -> Text:
        """
        Render a user message.

        Args:
            content: The user's message text

        Returns:
            Rich Text object with user message styling
        """
        return Text(f"You: {content}", style=USER_MESSAGE_STYLE)

    @staticmethod
    def render_system_message(content: Any) -> Union[Text, Any]:
        """
        Render a system message.

        Args:
            content: The system message content (string or Rich renderable)

        Returns:
            Rich renderable object (Text or the original if already rich-compatible)
        """
        if hasattr(content, "__rich_console__"):
            # Already a Rich renderable (Markdown, Syntax, etc.)
            return content
        return Text(f"{INFO_EMOJI}  {content}", style=SYSTEM_MESSAGE_STYLE)

    @staticmethod
    def render_assistant_text(text: str) -> Text:
        """
        Render streaming assistant text (plain text during streaming).

        Args:
            text: The assistant's streaming text

        Returns:
            Rich Text object with text overflow handling
        """
        return Text(text, overflow="fold")

    @staticmethod
    def render_assistant_markdown(text: str) -> Markdown:
        """
        Render finalized assistant text as Markdown.

        Args:
            text: The complete assistant message text

        Returns:
            Rich Markdown object
        """
        return Markdown(text.strip())

    @staticmethod
    def render_thinking_text(thinking_text: str) -> Text:
        """
        Render thinking/reasoning text.

        Args:
            thinking_text: The thinking text to display

        Returns:
            Rich Text object with thinking emoji and styling
        """
        return Text(
            f"{THINKING_EMOJI} {thinking_text}",
            style=THINKING_STYLE,
            overflow="fold",
        )

    @staticmethod
    def format_tool_block(tool_name: str, args: dict, result: str) -> str:
        """
        Format a complete tool call block with name, arguments, and result.

        Args:
            tool_name: Name of the tool being called
            args: Tool arguments dictionary
            result: Result string (may be placeholder or actual result)

        Returns:
            Formatted string with Chinese labels (调用/入参/结果)
        """
        args_str = json.dumps(args, ensure_ascii=False, indent=2) if args else "（无）"
        return f"调用: {tool_name}\n入参:\n{args_str}\n结果: {result}"

    @staticmethod
    def format_tool_result_line(result: str, success: bool = True) -> str:
        """
        Format a tool result line with success/error indicator.

        Args:
            result: The result text
            success: Whether the tool execution was successful

        Returns:
            Formatted result line with error prefix if unsuccessful
        """
        return result if success else f"{ERROR_PREFIX} {result}"

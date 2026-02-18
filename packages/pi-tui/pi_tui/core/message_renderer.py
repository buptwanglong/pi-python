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
    THINKING_PREFIX,
    ERROR_PREFIX,
    INFO_PREFIX,
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
        return Text(f"{INFO_PREFIX}  {content}", style=SYSTEM_MESSAGE_STYLE)

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
            f"{THINKING_PREFIX} {thinking_text}",
            style=THINKING_STYLE,
            overflow="fold",
        )

    @staticmethod
    def format_tool_block(tool_name: str, args: dict, result: str) -> str:
        """
        Format a tool call block in minimal Claude Code style.

        Args:
            tool_name: Name of the tool being called
            args: Tool arguments dictionary
            result: Result string (may be placeholder or actual result)

        Returns:
            Formatted string with minimal decorations
        """
        # Format args - show only most relevant parameter
        args_display = _format_args_minimal(tool_name, args)

        # Simple format: tool name, key args, separator, result
        parts = [
            f"{tool_name.capitalize()}: {args_display}",
            "─" * 50,  # Simple separator line
            result
        ]

        return "\n".join(parts)

    @staticmethod
    def format_tool_result_line(result: str, success: bool = True) -> str:
        """
        Format a tool result line without emoji decorations.

        Args:
            result: The result text
            success: Whether the tool execution was successful

        Returns:
            Formatted result line (no emoji prefix in minimal style)
        """
        if not success:
            return f"Error: {result}"
        return result


def _format_args_minimal(tool_name: str, args: dict) -> str:
    """Extract and format most relevant argument for display."""
    if tool_name == "bash":
        return args.get("command", str(args))
    elif tool_name == "read":
        path = args.get("file_path", "")
        return path
    elif tool_name == "write":
        return args.get("file_path", "")
    elif tool_name == "edit":
        path = args.get("file_path", "")
        return path
    elif tool_name == "grep":
        pattern = args.get("pattern", "")
        return f'"{pattern}"'
    else:
        # Fallback: show args as compact JSON
        import json
        return json.dumps(args, ensure_ascii=False)[:100]

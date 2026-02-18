"""
Message Block Widgets

This module provides specialized widget classes for different types
of message blocks (thinking, tool calls) with proper state management.
"""

from textual.widgets import Static
from rich.text import Text

from ..constants import (
    MESSAGE_BLOCK_CLASS,
    MESSAGE_SYSTEM_CLASS,
    TOOL_BLOCK_CLASS,
    THINKING_PREFIX,
    THINKING_STYLE,
)
from ..core.message_renderer import MessageRenderer


class ThinkingBlock(Static):
    """
    Widget for displaying thinking/reasoning text.

    This widget maintains its own thinking text state and provides
    a clean interface for appending thinking content.
    """

    def __init__(self):
        """Initialize the thinking block with empty state."""
        super().__init__(
            Text(f"{THINKING_PREFIX}", style=THINKING_STYLE),
            classes=f"{MESSAGE_BLOCK_CLASS} {MESSAGE_SYSTEM_CLASS}",
        )
        self.thinking_text = ""

    def append_thinking(self, text: str) -> None:
        """
        Append thinking text and update the display.

        Args:
            text: Additional thinking text to append
        """
        self.thinking_text += text
        renderer = MessageRenderer()
        self.update(renderer.render_thinking_text(self.thinking_text))


class ToolBlock(Static):
    """
    Widget for displaying tool call information.

    This widget maintains tool name, arguments, and result state,
    providing a clean interface for updating tool execution status.
    """

    def __init__(self, tool_name: str, args: dict):
        """
        Initialize the tool block with tool information.

        Args:
            tool_name: Name of the tool being called
            args: Tool arguments dictionary
        """
        self.tool_name = tool_name
        self.tool_args = args
        renderer = MessageRenderer()
        initial_content = renderer.format_tool_block(
            tool_name, args, "执行中..."
        )
        super().__init__(
            Text(initial_content, overflow="fold"),
            classes=f"{MESSAGE_BLOCK_CLASS} {TOOL_BLOCK_CLASS}",
        )

    def update_result(self, result: str, success: bool = True) -> None:
        """
        Update the tool block with the execution result.

        Args:
            result: Result string from tool execution
            success: Whether the execution was successful
        """
        renderer = MessageRenderer()
        result_line = renderer.format_tool_result_line(result, success)
        content = renderer.format_tool_block(
            self.tool_name, self.tool_args, result_line
        )
        self.update(Text(content, overflow="fold"))

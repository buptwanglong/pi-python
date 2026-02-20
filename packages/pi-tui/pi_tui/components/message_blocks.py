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
        from ..constants import THINKING_STYLE, MESSAGE_BLOCK_CLASS, MESSAGE_SYSTEM_CLASS

        super().__init__(
            Text("Thinking...", style=THINKING_STYLE),
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
    Widget for displaying tool call in Claude Code style:
    ▶/⏺ ToolName(args) and status line (Running… / Interrupted / result).
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
        initial_content = renderer.render_tool_block_claude(
            tool_name, args, "执行中...", success=True
        )
        super().__init__(
            initial_content,
            classes=f"{MESSAGE_BLOCK_CLASS} {TOOL_BLOCK_CLASS} tool-block--claude",
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
        content = renderer.render_tool_block_claude(
            self.tool_name, self.tool_args, result_line, success=success
        )
        self.update(content)

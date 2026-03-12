"""
ToolDisplay Widget

Shows tool execution with status indicators.
"""

from typing import Optional
from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text


class ToolDisplay(Static):
    """
    Tool display widget with reactive updates

    Shows tool execution status with visual indicators:
    - ⏳ Running
    - ✅ Success
    - ❌ Error

    Attributes:
        tool_name: Name of the tool being executed
        tool_args: Tool arguments
        tool_result: Tool execution result
        is_running: Whether tool is currently running
        has_error: Whether tool execution failed
    """

    # Reactive properties
    tool_name: reactive[str] = reactive("", init=False)
    tool_args: reactive[dict] = reactive(dict, init=False)
    tool_result: reactive[Optional[str]] = reactive(None, init=False)
    is_running: reactive[bool] = reactive(False, init=False)
    has_error: reactive[bool] = reactive(False, init=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tool_name = ""
        self.tool_args = {}
        self.tool_result = None
        self.is_running = False
        self.has_error = False

    def watch_tool_name(self, old_name: str, new_name: str) -> None:
        """Called when tool_name changes"""
        if new_name:
            self.display = True
            self.refresh()

    def watch_is_running(self, old: bool, new: bool) -> None:
        """Called when is_running changes"""
        self.refresh()

    def watch_tool_result(self, old: Optional[str], new: Optional[str]) -> None:
        """Called when tool_result changes"""
        if new is not None:
            self.is_running = False
            self.refresh()

    def render(self) -> Text:
        """
        Render tool execution info

        Returns:
            Formatted tool display
        """
        output = Text()

        if not self.tool_name:
            return output

        # Status indicator
        if self.is_running:
            output.append("⏳ ", style="yellow")
        elif self.has_error:
            output.append("❌ ", style="red")
        else:
            output.append("✅ ", style="green")

        # Tool name
        output.append(f"[{self.tool_name}]", style="bold cyan")

        # Arguments preview
        if self.tool_args:
            args_preview = self._format_args_preview(self.tool_args)
            output.append(f" {args_preview}", style="dim")

        # Result (if available)
        if self.tool_result:
            output.append("\n")
            output.append(self._truncate(self.tool_result, 200), style="dim")

        return output

    def _format_args_preview(self, args: dict) -> str:
        """
        Format arguments preview

        Shows first 2 argument keys.

        Args:
            args: Tool arguments

        Returns:
            Formatted preview string
        """
        if not args:
            return ""

        keys = list(args.keys())[:2]
        preview = ", ".join(keys)

        if len(args) > 2:
            preview += "..."

        return f"({preview})"

    def _truncate(self, text: str, max_len: int) -> str:
        """
        Truncate long text

        Args:
            text: Text to truncate
            max_len: Maximum length

        Returns:
            Truncated text with ... if needed
        """
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."

    def show_tool_call(self, tool_name: str, arguments: dict) -> None:
        """
        Show tool call starting

        Args:
            tool_name: Name of tool
            arguments: Tool arguments
        """
        self.tool_name = tool_name
        self.tool_args = arguments
        self.tool_result = None
        self.is_running = True
        self.has_error = False

    def show_result(self, result: str, error: bool = False) -> None:
        """
        Show tool result

        Args:
            result: Tool result text
            error: Whether this is an error result
        """
        self.tool_result = result
        self.is_running = False
        self.has_error = error

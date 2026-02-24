"""
Streaming Log Component

A custom RichLog widget that handles real-time streaming text updates
from LLM responses and agent events.
"""

from textual.widgets import RichLog


class StreamingLog(RichLog):
    """
    Enhanced RichLog widget for streaming content.

    Features:
    - Auto-scrolling to latest content
    - Support for partial text updates
    - Rich content rendering (markdown, syntax highlighting)
    """

    def __init__(self, *args, auto_scroll: bool = True, **kwargs):
        """
        Initialize the streaming log.

        Args:
            auto_scroll: Whether to automatically scroll to bottom
            *args: Positional arguments for RichLog
            **kwargs: Keyword arguments for RichLog
        """
        super().__init__(*args, **kwargs)
        self._auto_scroll = auto_scroll

    def write(self, content, *, expand: bool = False, shrink: bool = False, scroll_end: bool | None = None):
        """
        Write content to the log.

        Args:
            content: Content to write (str, Text, or Rich renderable)
            expand: Whether to expand the content
            shrink: Whether to shrink the content
            scroll_end: Whether to scroll to end (defaults to auto_scroll)
        """
        # Use auto_scroll setting if scroll_end not specified
        if scroll_end is None:
            scroll_end = self._auto_scroll

        super().write(content, expand=expand, shrink=shrink, scroll_end=scroll_end)

    def set_auto_scroll(self, enabled: bool) -> None:
        """
        Enable or disable auto-scrolling.

        Args:
            enabled: Whether to enable auto-scrolling
        """
        self._auto_scroll = enabled

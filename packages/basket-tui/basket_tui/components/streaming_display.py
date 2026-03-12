"""
StreamingDisplay Widget

Shows real-time streaming content with automatic updates.
"""

from textual.widgets import Widget
from textual.reactive import reactive
from rich.text import Text
from rich.markdown import Markdown


class StreamingDisplay(Widget):
    """
    Streaming display widget with reactive updates

    Automatically shows/hides based on is_active state.
    Renders Markdown when possible, falls back to plain text.

    Attributes:
        buffer: Accumulated streaming text
        is_active: Whether streaming is currently active
    """

    # Reactive properties
    buffer: reactive[str] = reactive("", init=False)
    is_active: reactive[bool] = reactive(False, init=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.buffer = ""
        self.is_active = False

    def watch_buffer(self, old_buffer: str, new_buffer: str) -> None:
        """
        Called automatically when buffer changes

        Args:
            old_buffer: Previous buffer content
            new_buffer: New buffer content
        """
        if self.is_active:
            self.refresh()

    def watch_is_active(self, old_active: bool, new_active: bool) -> None:
        """
        Called automatically when is_active changes

        Shows/hides widget based on active state.

        Args:
            old_active: Previous active state
            new_active: New active state
        """
        self.display = new_active
        if new_active:
            self.refresh()

    def render(self) -> Text | Markdown:
        """
        Render streaming content

        Attempts to render as Markdown, falls back to plain text on error.

        Returns:
            Rendered content
        """
        if not self.buffer:
            return Text("", style="dim")

        # Try Markdown rendering first
        try:
            return Markdown(self.buffer)
        except Exception:
            # Fall back to plain text if Markdown fails
            return Text(self.buffer)

    def append_text(self, text: str) -> None:
        """
        Append text to buffer

        Triggers reactive update.

        Args:
            text: Text to append
        """
        self.buffer = self.buffer + text

    def clear(self) -> None:
        """Clear buffer and deactivate"""
        self.buffer = ""
        self.is_active = False

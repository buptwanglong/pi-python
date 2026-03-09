"""
Multi-line Input Component with Autocomplete

A TextArea-based input widget that supports:
- Multi-line text editing
- Enter to send, Shift+Enter for newline
- Autocomplete suggestions
"""

from textual.widgets import TextArea
from textual.binding import Binding
from textual.message import Message


class InputWantsSlashPopup(Message):
    """Sent when user presses Tab and input starts with /; app may show slash command list."""

    def __init__(self, prefix: str, sender=None) -> None:
        super().__init__(sender)
        self.prefix = prefix


class MultiLineInput(TextArea):
    """
    Multi-line text input with autocomplete support.

    Features:
    - Enter: submit message
    - Shift+Enter: new line
    - Basic autocomplete (can be extended)
    - Syntax highlighting for code
    """

    BINDINGS = [
        Binding("enter", "submit", "Send", priority=True),
        Binding("shift+enter", "insert_newline", "New line", show=False),
        Binding("escape", "clear", "Clear"),
        Binding("tab", "request_slash_popup", "Slash list", show=False),
    ]

    DEFAULT_CSS = """
    MultiLineInput {
        height: auto;
        min-height: 3;
        max-height: 10;
        border: solid $accent;
        background: $surface;
    }

    MultiLineInput:focus {
        border: solid $success;
    }
    """

    def __init__(
        self,
        text: str = "",
        language: str | None = None,
        theme: str = "monokai",
        **kwargs,
    ):
        """
        Initialize multi-line input.

        Args:
            text: Initial text
            language: Language for syntax highlighting (e.g., "python")
            theme: Theme for syntax highlighting
            **kwargs: Additional arguments for TextArea
        """
        super().__init__(
            text=text,
            language=language,
            theme=theme,
            show_line_numbers=False,
            **kwargs,
        )

    def action_submit(self) -> None:
        """Submit the current text."""
        text = self.text.strip()
        if text:
            # Post a custom message event
            self.post_message(self.Submitted(self, text))
            # Clear the input
            self.clear()

    def action_insert_newline(self) -> None:
        """Insert a newline at the cursor (Shift+Enter)."""
        self.insert("\n")

    def action_clear(self) -> None:
        """Clear the input."""
        self.clear()

    def action_request_slash_popup(self) -> None:
        """If input starts with /, post message so app can show slash command list."""
        prefix = (self.text or "").strip()
        if prefix.startswith("/"):
            self.post_message(InputWantsSlashPopup(prefix))

    class Submitted(TextArea.Changed):
        """Message sent when text is submitted."""

        def __init__(self, text_area: "MultiLineInput", text: str) -> None:
            super().__init__(text_area)
            self.text = text


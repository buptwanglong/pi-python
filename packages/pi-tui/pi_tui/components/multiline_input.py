"""
Multi-line Input Component with Autocomplete

A TextArea-based input widget that supports:
- Multi-line text editing
- Autocomplete suggestions
- Submit on Ctrl+Enter
"""

from textual.widgets import TextArea
from textual.binding import Binding


class MultiLineInput(TextArea):
    """
    Multi-line text input with autocomplete support.

    Features:
    - Multi-line editing (Shift+Enter for newlines)
    - Submit on Ctrl+Enter
    - Basic autocomplete (can be extended)
    - Syntax highlighting for code
    """

    BINDINGS = [
        Binding("ctrl+enter", "submit", "Submit", priority=True),
        Binding("escape", "clear", "Clear"),
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

    def action_clear(self) -> None:
        """Clear the input."""
        self.clear()

    class Submitted(TextArea.Changed):
        """Message sent when text is submitted."""

        def __init__(self, text_area: "MultiLineInput", text: str) -> None:
            super().__init__(text_area)
            self.text = text


class AutocompleteInput(MultiLineInput):
    """
    Multi-line input with autocomplete suggestions.

    This extends MultiLineInput to add autocomplete functionality.
    For now, it's a placeholder for future autocomplete features.
    """

    def __init__(
        self,
        text: str = "",
        suggestions: list[str] | None = None,
        **kwargs,
    ):
        """
        Initialize autocomplete input.

        Args:
            text: Initial text
            suggestions: List of autocomplete suggestions
            **kwargs: Additional arguments for MultiLineInput
        """
        super().__init__(text=text, **kwargs)
        self._suggestions = suggestions or []

    def set_suggestions(self, suggestions: list[str]) -> None:
        """
        Update autocomplete suggestions.

        Args:
            suggestions: New list of suggestions
        """
        self._suggestions = suggestions

    # Future: Implement autocomplete dropdown
    # For now, just tracks suggestions for later use

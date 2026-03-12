"""
Multi-line Input Component with Autocomplete

A TextArea-based input widget that supports:
- Multi-line text editing
- Enter to send, Shift+Enter for newline
- Autocomplete suggestions
- Input history (Ctrl+Up/Down) and line-edit shortcuts (improvement 10)
"""

from textual.widgets import TextArea
from textual.binding import Binding
from textual.message import Message
from textual import on
from textual.events import Key


class InputWantsSlashPopup(Message):
    """Sent when user types / (or Tab with input starting with /); app shows slash command list."""

    def __init__(self, prefix: str) -> None:
        super().__init__()
        self.prefix = (prefix or "/").strip() or "/"


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
        Binding("tab", "request_slash_popup", "Slash list", show=False, priority=True),
        # Improvement 10: input history
        Binding("ctrl+up", "history_prev", "History prev", show=False),
        Binding("ctrl+down", "history_next", "History next", show=False),
        # Line-edit (OpenClaw-style)
        Binding("ctrl+a", "cursor_line_start", "Line start", show=False),
        Binding("ctrl+e", "cursor_line_end", "Line end", show=False),
        Binding("ctrl+k", "delete_to_end_of_line", "Kill to EOL", show=False),
        Binding("ctrl+u", "delete_to_start_of_line", "Kill to BOL", show=False),
        Binding("ctrl+w", "delete_word_left", "Delete word", show=False),
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
        self._last_text = ""
        # Improvement 10: input history (dedupe on add, ↑/↓ via Ctrl+Up/Down)
        self._input_history: list[str] = []
        self._input_history_index: int = -1
        self._input_draft: str = ""

    def add_to_history(self, text: str) -> None:
        """Add a submitted line to history (dedupe; call from app on submit)."""
        t = (text or "").strip()
        if not t:
            return
        if self._input_history and self._input_history[-1] == t:
            return
        self._input_history.append(t)
        # Keep last 100
        if len(self._input_history) > 100:
            self._input_history.pop(0)
        self._input_history_index = len(self._input_history)

    @on(Key)
    def _on_key_tab_slash_popup(self, event: Key) -> None:
        """When Tab is pressed and input starts with /, open slash list (override TextArea inserting tab)."""
        if event.key != "tab":
            return
        prefix = (self.text or "").strip()
        if not prefix.startswith("/"):
            return
        event.prevent_default().stop()
        self.post_message(InputWantsSlashPopup(prefix))

    @on(TextArea.Changed)
    def _on_changed_open_slash_on_slash(self) -> None:
        """When input transitions to starting with /, open slash command popup (improvement 2)."""
        text = self.text or ""
        if text.startswith("/") and not (self._last_text or "").startswith("/"):
            self.post_message(InputWantsSlashPopup(text.strip() or "/"))
        self._last_text = text

    def action_submit(self) -> None:
        """Submit the current text."""
        text = self.text.strip()
        if text:
            self.add_to_history(text)
            self._input_history_index = len(self._input_history)
            self._input_draft = ""
            self.post_message(self.Submitted(self, text))
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

    def action_history_prev(self) -> None:
        """Cycle to previous input history entry (improvement 10)."""
        if not self._input_history:
            return
        if self._input_history_index <= 0:
            if self._input_history_index == -1:
                self._input_draft = self.text or ""
            self._input_history_index = 0
            self.load_text(self._input_history[0])
        else:
            self._input_history_index -= 1
            self.load_text(self._input_history[self._input_history_index])
        self._last_text = self.text or ""

    def action_history_next(self) -> None:
        """Cycle to next input history entry or restore draft (improvement 10)."""
        if not self._input_history:
            return
        if self._input_history_index >= len(self._input_history) - 1:
            self._input_history_index = len(self._input_history)
            self.load_text(self._input_draft)
            self._input_draft = ""
        else:
            self._input_history_index += 1
            self.load_text(self._input_history[self._input_history_index])
        self._last_text = self.text or ""

    class Submitted(TextArea.Changed):
        """Message sent when text is submitted."""

        def __init__(self, text_area: "MultiLineInput", text: str) -> None:
            super().__init__(text_area)
            self.text = text


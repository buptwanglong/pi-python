"""
Code block overlay: show last (or given) code block with syntax highlighting.
Used by /syntax slash command.
"""

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static
from rich.syntax import Syntax


class CodeBlockOverlay(ModalScreen[None]):
    """Modal showing a single code block with Pygments/Rich syntax highlighting."""

    BINDINGS = [("escape", "dismiss", "Close")]

    CSS = """
    CodeBlockOverlay Vertical {
        height: 85vh;
        width: 90vw;
        padding: 1 2;
        background: $surface;
        border: solid $primary;
    }
    #code-block-content {
        height: 1fr;
        min-height: 5;
        padding: 1 0;
        overflow: auto;
    }
    #code-block-close {
        margin-top: 1;
        width: auto;
    }
    """

    def __init__(self, code: str, language: str = "text", **kwargs) -> None:
        super().__init__(**kwargs)
        self._code = code
        self._language = language or "text"

    def compose(self):
        with Vertical():
            syntax = Syntax(
                self._code,
                self._language,
                theme="monokai",
                line_numbers=True,
                word_wrap=False,
            )
            yield Static(syntax, id="code-block-content")
            yield Button("Close", id="code-block-close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "code-block-close":
            self.dismiss(None)

    def action_dismiss(self) -> None:
        self.dismiss(None)

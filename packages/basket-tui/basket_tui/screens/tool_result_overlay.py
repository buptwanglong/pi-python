"""
Tool result overlay: show full result of last tool call (expand).
Used by Ctrl+E or /expand.
"""

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, TextArea


class ToolResultOverlay(ModalScreen[None]):
    """Modal showing full tool result text."""

    BINDINGS = [("escape", "dismiss", "Close")]

    CSS = """
    ToolResultOverlay Vertical {
        height: 85vh;
        width: 90vw;
        padding: 1 2;
        background: $surface;
        border: solid $primary;
    }
    #tool-result-content {
        height: 1fr;
        min-height: 5;
    }
    #tool-result-close {
        margin-top: 1;
        width: auto;
    }
    """

    def __init__(self, content: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._content = content or ""

    def compose(self):
        with Vertical():
            yield TextArea(self._content, id="tool-result-content", read_only=True)
            yield Button("Close", id="tool-result-close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "tool-result-close":
            self.dismiss(None)

    def action_dismiss(self) -> None:
        self.dismiss(None)

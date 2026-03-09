"""Modal listing slash commands and shortcuts."""

from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.widgets import Button, Static


class HelpScreen(ModalScreen[None]):
    """Modal listing slash commands and shortcuts."""

    BINDINGS = [("escape", "dismiss", "Close")]

    CSS = """
    HelpScreen {
        width: 60;
        height: auto;
        max-height: 80vh;
        padding: 1 2;
        background: $surface;
        border: solid $primary;
    }
    #help-content {
        width: 100%;
        padding: 0 0 1 0;
    }
    #help-close {
        width: auto;
    }
    """

    def __init__(self, content: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._content = content

    def compose(self) -> ComposeResult:
        yield Static(self._content, id="help-content")
        yield Button("Close", id="help-close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "help-close":
            self.dismiss(None)

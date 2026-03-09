"""
Full-screen error modal for system-level errors.
Shows message and Exit / Retry actions.
"""

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ErrorModal(ModalScreen[str]):
    """Modal for system errors: message + Exit (dismiss "exit") / Retry (dismiss "retry")."""

    BINDINGS = [
        ("escape", "exit", "Exit"),
        ("q", "exit", "Exit"),
    ]

    CSS = """
    ErrorModal Vertical {
        height: auto;
        max-height: 85vh;
        width: 90vw;
        padding: 1 2;
        background: $surface;
        border: solid $error 2;
    }
    #error-modal-title {
        color: $error;
        padding: 0 0 1 0;
    }
    #error-modal-body {
        height: auto;
        padding: 0 0 1 0;
    }
    #error-modal-buttons {
        height: auto;
        padding: 1 0 0 0;
    }
    """

    def __init__(self, message: str, title: str = "系统错误", **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._message = message or ""

    def compose(self):
        with Vertical():
            yield Static(self._title, id="error-modal-title")
            yield Static(self._message, id="error-modal-body")
            with Vertical(id="error-modal-buttons"):
                yield Button("重试", id="error-retry", variant="primary")
                yield Button("退出", id="error-exit")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "error-retry":
            self.dismiss("retry")
        else:
            self.dismiss("exit")

    def action_exit(self) -> None:
        self.dismiss("exit")

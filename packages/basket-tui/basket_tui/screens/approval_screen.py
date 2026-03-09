"""
Approval modal: confirm or reject an action (e.g. tool run).
Used when agent wants to run write/edit/bash and user has approval enabled.
"""

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static, TextArea


class ApprovalScreen(ModalScreen[bool]):
    """Modal with title, body, optional diff/command; Approve/Reject. Esc or Ctrl+C = Reject."""

    BINDINGS = [
        ("escape", "reject", "Reject"),
        ("ctrl+c", "reject", "Reject"),
    ]

    CSS = """
    ApprovalScreen Vertical {
        height: auto;
        max-height: 85vh;
        width: 90vw;
        padding: 1 2;
        background: $surface;
        border: solid $primary;
    }
    #approval-title {
        height: auto;
        padding: 0 0 1 0;
        color: $text;
    }
    #approval-body {
        height: auto;
        padding: 0 0 1 0;
    }
    #approval-diff {
        height: 15;
        min-height: 5;
    }
    #approval-buttons {
        height: auto;
        padding: 1 0 0 0;
    }
    """

    def __init__(
        self,
        title: str,
        body: str,
        diff_or_command: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._title = title or "Confirm"
        self._body = body or ""
        self._diff_or_command = diff_or_command or ""

    def compose(self):
        with Vertical():
            yield Static(self._title, id="approval-title")
            yield Static(self._body, id="approval-body")
            if self._diff_or_command:
                yield TextArea(
                    self._diff_or_command,
                    id="approval-diff",
                    read_only=True,
                )
            with Vertical(id="approval-buttons"):
                yield Button("Approve", id="approval-approve", variant="primary")
                yield Button("Reject", id="approval-reject")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "approval-approve":
            self.dismiss(True)
        elif event.button.id == "approval-reject":
            self.dismiss(False)

    def action_reject(self) -> None:
        self.dismiss(False)

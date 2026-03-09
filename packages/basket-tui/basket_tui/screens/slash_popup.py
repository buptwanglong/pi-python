"""
Slash command popup: show filtered list when user types / and presses Tab.
"""

from textual import on
from textual.screen import ModalScreen
from textual.widgets import OptionList


SLASH_COMMANDS = [
    ("/clear", "Clear output"),
    ("/help", "Show help"),
    ("/history", "Open transcript"),
    ("/copy", "Copy last message"),
    ("/theme", "Toggle dark/light"),
    ("/syntax", "View last code block"),
    ("/expand", "Expand last tool result"),
    ("/compact", "Compact context (send to agent)"),
    ("/status", "Show status"),
    ("/sessions", "Session picker"),
    ("/new", "New session"),
    ("/reset", "Reset current session"),
    ("/abort", "Stop agent"),
]


class SlashCommandScreen(ModalScreen[str | None]):
    """Modal listing slash commands filtered by prefix; Enter runs selected."""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, prefix: str = "/", **kwargs) -> None:
        super().__init__(**kwargs)
        self._prefix = (prefix or "/").lower().strip()
        if not self._prefix.startswith("/"):
            self._prefix = "/"

    def compose(self):
        filtered = [
            (cmd, label)
            for cmd, label in SLASH_COMMANDS
            if cmd.startswith(self._prefix) or self._prefix.startswith(cmd)
        ]
        if not filtered:
            filtered = list(SLASH_COMMANDS)
        options = [OptionList.Option(f"{cmd} — {label}", id=cmd) for cmd, label in filtered]
        yield OptionList(*options, id="slash-options")

    @on(OptionList.OptionSelected)
    def _on_option(self, event: OptionList.OptionSelected) -> None:
        if event.option and getattr(event.option, "id", None):
            self.dismiss(event.option.id)

    def action_dismiss(self) -> None:
        self.dismiss(None)

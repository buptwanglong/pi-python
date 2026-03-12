"""
Slash command popup: show when user types / or Tab; filter list as user types (improvement 2).
"""

from textual import on
from textual.screen import ModalScreen
from textual.widgets import OptionList, Input, Static


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


def _filter_commands(prefix: str) -> list[tuple[str, str]]:
    """Filter SLASH_COMMANDS by prefix (case-insensitive); prefix should start with /."""
    p = (prefix or "/").strip().lower()
    if not p.startswith("/"):
        p = "/" + p
    return [
        (cmd, label)
        for cmd, label in SLASH_COMMANDS
        if cmd.lower().startswith(p) or p.startswith(cmd.lower())
    ] or list(SLASH_COMMANDS)


class SlashCommandScreen(ModalScreen[str | None]):
    """Modal with filter input and slash commands list; type to filter, Tab/↑↓ cycle, Enter confirm (improvement 2)."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("enter", "confirm_choice", "Confirm"),
    ]

    def __init__(self, prefix: str = "/", **kwargs) -> None:
        super().__init__(**kwargs)
        self._prefix = (prefix or "/").strip()
        if not self._prefix.startswith("/"):
            self._prefix = "/"

    def compose(self):
        yield Static("Filter: type to filter, ↑/↓ or Tab 选择, Enter 执行", id="slash-hint")
        yield Input(value=self._prefix, placeholder="/", id="slash-filter")
        filtered = _filter_commands(self._prefix)
        options = [OptionList.Option(f"{cmd} — {label}", id=cmd) for cmd, label in filtered]
        yield OptionList(*options, id="slash-options")

    def on_mount(self) -> None:
        try:
            opt_list = self.query_one("#slash-options", OptionList)
            if opt_list.option_count > 0:
                if opt_list.highlighted is None:
                    opt_list.highlighted = 0
                # Focus list so Enter immediately confirms 候选值 (no need to Tab first)
                opt_list.focus()
        except Exception:
            pass

    def action_confirm_choice(self) -> None:
        """Confirm current/highlighted slash command so 候选值生效 (Enter from filter or list)."""
        try:
            opt_list = self.query_one("#slash-options", OptionList)
            idx = opt_list.highlighted if opt_list.highlighted is not None else 0
            if 0 <= idx < opt_list.option_count:
                option = opt_list.get_option_at_index(idx)
                cmd_id = getattr(option, "id", None)
                if cmd_id:
                    self.dismiss(cmd_id)
                    return
        except Exception:
            pass
        # No valid selection: dismiss without running
        self.dismiss(None)

    def _refresh_options(self, prefix: str) -> None:
        filtered = _filter_commands(prefix)
        try:
            opt_list = self.query_one("#slash-options", OptionList)
            opt_list.clear_options()
            for cmd, label in filtered:
                opt_list.add_option(OptionList.Option(f"{cmd} — {label}", id=cmd))
            if filtered:
                try:
                    opt_list.highlighted = 0
                except Exception:
                    pass
        except Exception:
            pass

    @on(Input.Changed)
    def _on_filter_changed(self, event: Input.Changed) -> None:
        if getattr(event.control, "id", None) == "slash-filter":
            self._refresh_options(event.control.value or "/")

    @on(OptionList.OptionSelected)
    def _on_option(self, event: OptionList.OptionSelected) -> None:
        if event.option and getattr(event.option, "id", None):
            self.dismiss(event.option.id)

    def action_dismiss(self) -> None:
        self.dismiss(None)

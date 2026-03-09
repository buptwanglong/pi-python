"""
Session picker modal: list sessions + "New session", return selected session_id or "new".
"""

from typing import List, Tuple

from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual import on


SESSION_NEW_ID = "__new__"


class SessionPickerScreen(ModalScreen[str | None]):
    """Modal listing sessions; OptionList of (session_id, label). Returns session_id or SESSION_NEW_ID for new."""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, options: List[Tuple[str, str]], include_new: bool = True, **kwargs) -> None:
        super().__init__(**kwargs)
        self._options = list(options)
        self._include_new = include_new

    def compose(self):
        yield Static("选择会话 (Enter 选择, Esc 取消)", id="session-picker-title")
        opts = [OptionList.Option(label, id=sid) for sid, label in self._options]
        if self._include_new:
            opts.append(OptionList.Option("+ 新会话", id=SESSION_NEW_ID))
        yield OptionList(*opts, id="session-options")

    @on(OptionList.OptionSelected)
    def _on_option(self, event: OptionList.OptionSelected) -> None:
        if event.option and getattr(event.option, "id", None):
            self.dismiss(event.option.id)

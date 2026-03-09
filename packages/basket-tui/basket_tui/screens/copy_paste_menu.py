"""Right-click context menu: 复制 / 粘贴."""

from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.widgets import OptionList
from textual.widget import Widget
from textual import on


class CopyPasteMenuScreen(ModalScreen):
    """Right-click context menu: 复制 / 粘贴."""

    CSS = """
    CopyPasteMenuScreen {
        width: auto;
        min-width: 12;
    }
    """

    def __init__(self, source_widget: Widget | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._source = source_widget

    def compose(self) -> ComposeResult:
        yield OptionList(
            OptionList.Option("复制", id="copy"),
            OptionList.Option("粘贴", id="paste"),
            id="copypaste-options",
        )

    @on(OptionList.OptionSelected)
    def _on_option(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    @staticmethod
    def _get_text_from(widget: Widget | None) -> str:
        if widget is None:
            return ""
        text = getattr(widget, "selected_text", None) or getattr(widget, "text", "")
        return (text or "").strip()

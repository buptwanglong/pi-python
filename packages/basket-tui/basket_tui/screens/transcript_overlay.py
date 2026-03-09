"""
Transcript overlay screen: shows committed output_blocks + current streaming tail.
Uses get_blocks() for (role, content); assistant blocks rendered as Markdown.
"""

from typing import Callable, List, Tuple

from rich.console import Group
from rich.markdown import Markdown
from rich.text import Text

from textual.containers import ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class TranscriptOverlay(ModalScreen[str | None]):
    """Full-screen overlay showing full transcript (committed + in-flight); assistant as Markdown."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("ctrl+shift+t", "dismiss", "Close"),
        ("pageup", "scroll_transcript_up", "Scroll up"),
        ("pagedown", "scroll_transcript_down", "Scroll down"),
        ("ctrl+end", "scroll_transcript_end", "To bottom"),
    ]

    CSS = """
    TranscriptOverlay Vertical {
        height: 90vh;
        width: 95vw;
        padding: 1 2;
        background: $surface;
        border: solid $primary;
    }
    #transcript-title {
        height: auto;
        padding: 0 0 1 0;
        color: $text;
    }
    #transcript-scroll {
        height: 1fr;
        min-height: 5;
        scrollbar-size: 1 0;
    }
    #transcript-content {
        width: 100%;
        height: auto;
    }
    #transcript-close {
        margin-top: 1;
        width: auto;
    }
    """

    def __init__(self, get_blocks: Callable[[], List[Tuple[str, str]]], **kwargs) -> None:
        super().__init__(**kwargs)
        self._get_blocks = get_blocks

    def compose(self):
        with Vertical():
            yield Static(
                "Transcript — Esc or Ctrl+Shift+T to close | Page Up/Down, Ctrl+End to scroll",
                id="transcript-title",
            )
            with ScrollableContainer(id="transcript-scroll"):
                yield Static("", id="transcript-content")
            yield Button("Close", id="transcript-close", variant="primary")

    def on_mount(self) -> None:
        self._refresh_content()
        self.set_interval(0.5, self._refresh_content)

    def _blocks_to_renderable(self, blocks: List[Tuple[str, str]]):
        """Build a Rich Group: assistant blocks as Markdown, others as Text."""
        parts = []
        for i, (role, content) in enumerate(blocks):
            if role == "assistant" and content.strip():
                parts.append(Markdown(content))
            else:
                parts.append(Text(content))
            if i < len(blocks) - 1:
                parts.append(Text("\n\n"))
        return Group(*parts) if parts else Text("")

    def _refresh_content(self) -> None:
        try:
            static = self.query_one("#transcript-content", Static)
            blocks = self._get_blocks()
            renderable = self._blocks_to_renderable(blocks)
            static.update(renderable)
            scroll = self.query_one("#transcript-scroll", ScrollableContainer)
            scroll.scroll_end()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "transcript-close":
            self.dismiss(None)

    def action_dismiss(self) -> None:
        self.dismiss(None)

    def action_scroll_transcript_up(self) -> None:
        try:
            scroll = self.query_one("#transcript-scroll", ScrollableContainer)
            scroll.scroll_page_up()
        except Exception:
            pass

    def action_scroll_transcript_down(self) -> None:
        try:
            scroll = self.query_one("#transcript-scroll", ScrollableContainer)
            scroll.scroll_page_down()
        except Exception:
            pass

    def action_scroll_transcript_end(self) -> None:
        try:
            scroll = self.query_one("#transcript-scroll", ScrollableContainer)
            scroll.scroll_end()
        except Exception:
            pass

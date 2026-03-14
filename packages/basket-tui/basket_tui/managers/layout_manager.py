"""
LayoutManager

Manages UI layout composition and status bar updates.
"""

from typing import TYPE_CHECKING
from textual.containers import ScrollableContainer, Horizontal
from textual.widgets import Header, Footer, Static

from ..components import MessageList, StreamingDisplay, ToolDisplay, MultiLineInput
from ..constants import INPUT_ID

if TYPE_CHECKING:
    from ..app import PiCodingAgentApp


class LayoutManager:
    """
    Layout manager for UI composition

    Responsible for:
    - Composing UI components
    - Updating status bar
    """

    def __init__(self, app: "PiCodingAgentApp"):
        self._app = app

    def compose(self):
        """
        Compose UI components

        Yields:
            Textual widgets in layout order
        """
        yield Header()

        # Main output area
        with ScrollableContainer(id="output-container"):
            yield MessageList(id="message-list")
            yield StreamingDisplay(id="streaming-display")
            yield ToolDisplay(id="tool-display")

        # Status bar
        with Horizontal(id="status-bar"):
            yield Static("", id="status-phase")
            yield Static("", id="status-model")
            yield Static("", id="status-session")

        # Input area (docked at bottom by CSS #input)
        yield MultiLineInput(id=INPUT_ID)

        yield Footer()

    def update_status_bar(
        self, phase: str = "", model: str = "", session: str = ""
    ) -> None:
        """
        Update status bar

        Args:
            phase: Current phase text
            model: Model name
            session: Session ID
        """
        try:
            if phase:
                self._app.query_one("#status-phase", Static).update(
                    f"Phase: {phase}"
                )
            if model:
                self._app.query_one("#status-model", Static).update(f"Model: {model}")
            if session:
                self._app.query_one("#status-session", Static).update(
                    f"Session: {session}"
                )
        except Exception:
            # Widgets may not be mounted yet
            pass

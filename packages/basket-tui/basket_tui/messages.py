"""
Message types used by the TUI app and modes (tui, attach).
"""

from textual.message import Message
from textual.widget import Widget


class StreamingTextDelta(Message):
    """Gateway stream: text delta (post from reader task so UI updates on main loop)."""
    def __init__(self, delta: str) -> None:
        super().__init__()
        self.delta = delta or ""


class StreamingThinkingDelta(Message):
    """Gateway stream: thinking delta."""
    def __init__(self, delta: str) -> None:
        super().__init__()
        self.delta = delta or ""


class MountMessageBlock(Message):
    """Request to mount a message block (user, system, tool). Processed asynchronously."""

    def __init__(self, role: str, content) -> None:
        super().__init__()
        self.role = role
        self.content = content


class MountWidget(Message):
    """Request to mount an existing widget (e.g. thinking block). Processed asynchronously."""

    def __init__(self, widget: Widget) -> None:
        super().__init__()
        self.widget = widget


class ProcessPendingInputs(Message):
    """Process queued user inputs (append and run agent) after current agent completes."""

"""
Streaming State

Mutable state for high-frequency streaming updates.
"""

from dataclasses import dataclass


@dataclass
class StreamingState:
    """
    Streaming output state (mutable)

    This is intentionally mutable for performance reasons.
    High-frequency updates (~80ms intervals) make immutability impractical.

    Attributes:
        buffer: Accumulated streaming text
        is_active: Whether streaming is currently active
        length_rendered: Number of characters already rendered to UI
    """

    buffer: str = ""
    is_active: bool = False
    length_rendered: int = 0

    def append(self, text: str) -> None:
        """
        Append text to buffer

        Args:
            text: Text to append
        """
        self.buffer += text

    def clear(self) -> None:
        """Reset all fields to initial state"""
        self.buffer = ""
        self.is_active = False
        self.length_rendered = 0

    def activate(self) -> None:
        """Activate streaming and reset buffer"""
        self.is_active = True
        self.buffer = ""
        self.length_rendered = 0

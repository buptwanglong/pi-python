"""
Double Ctrl+C (or Ctrl+D) confirmation before exiting the native TUI.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExitConfirmState:
    """First interrupt arms; second interrupt requests exit."""

    pending: bool = False

    @property
    def is_pending(self) -> bool:
        return self.pending

    def handle_ctrl_c(self) -> bool:
        """
        Handle a Ctrl+C / Ctrl+D press.

        Returns:
            True if the application should exit now; False if only armed a pending exit.
        """
        if self.pending:
            self.pending = False
            return True
        self.pending = True
        return False

    def reset_pending(self) -> None:
        """Clear armed state (e.g. after a timeout)."""
        self.pending = False

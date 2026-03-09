"""Mixin: agent task, phase, stop, approval modal."""

import asyncio
from typing import Callable, Optional

from .screens.approval_screen import ApprovalScreen


class AppAgentMixin:
    """Agent lifecycle: set_agent_task, set_phase, mark_tool_interrupted_if_any, action_stop_agent, show_approval_modal."""

    def set_agent_task(self, task: Optional[asyncio.Task]) -> None:
        """Set the currently running agent task (for cancellation). Updates phase: waiting_model when task set, idle when cleared."""
        self.state.set_agent_task(task)
        self.state.phase = "waiting_model" if task else "idle"
        self._refresh_status_bar()

    def set_phase(self, phase: str) -> None:
        """Set conversation phase for status bar (waiting_model, thinking, streaming, tool_running, error)."""
        self.state.phase = phase
        self._refresh_status_bar()

    def mark_tool_interrupted_if_any(self) -> None:
        """If a tool block is in progress, mark it as interrupted (e.g. on cancel or error)."""
        if self.state.current_tool_name:
            self.show_tool_result("已中断", success=False)

    def action_stop_agent(self) -> None:
        """Cancel the currently running agent task."""
        self.mark_tool_interrupted_if_any()
        self.state.cancel_agent_task()

    def show_approval_modal(
        self,
        title: str,
        body: str,
        diff_or_command: str | None = None,
        callback: Callable[[bool], None] | None = None,
    ) -> None:
        """Show Approve/Reject modal; callback(True) on Approve, callback(False) on Reject or Esc/Ctrl+C."""
        cb = callback if callback is not None else lambda _: None
        self.push_screen(
            ApprovalScreen(
                title=title,
                body=body,
                diff_or_command=diff_or_command,
            ),
            cb,
        )

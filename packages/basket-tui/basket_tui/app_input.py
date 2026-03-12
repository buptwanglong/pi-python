"""Mixin: input handler, input changed, multi-line input submitted."""

import asyncio

from .constants import INPUT_ID
from .components.multiline_input import MultiLineInput


class AppInputMixin:
    """Input: set_input_handler, _handle_input_changed, on_multi_line_input_submitted."""

    def set_input_handler(self, handler) -> None:
        """
        Set the callback for handling user input.

        Args:
            handler: Async function that takes user_input string
        """
        self._input_handler = handler

    def _handle_input_changed(self, event) -> None:
        """Clear input error when user types (called from _on_text_area_changed on App)."""
        if getattr(event.control, "id", None) == INPUT_ID:
            self._clear_input_error()

    async def on_multi_line_input_submitted(
        self, event: MultiLineInput.Submitted
    ) -> None:
        """
        Handle multi-line input submission (Enter).

        Slash commands are handled in TUI; others go to agent (or queue if agent running).
        """
        user_input = (event.text or "").strip()

        if not user_input:
            return

        if self._handle_slash_command(user_input):
            return

        if self._input_handler and self.state.is_agent_running():
            self._pending_user_inputs.append(user_input)
            self._refresh_status_bar()
            self.notify("已加入队列，将在当前回复完成后处理", severity="information", timeout=2)
            return

        await self.append_user_message_async(user_input)
        await asyncio.sleep(0)

        if self._input_handler:
            await self._input_handler(user_input)
        else:
            self.append_message("assistant", f"Echo: {user_input}")

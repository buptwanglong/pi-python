"""Mixin: model info, session picker, status, reset, session switch handler, load_messages_into_output."""

import logging
from typing import Awaitable, Callable, Optional

from textual.css.query import NoMatches

from .constants import INPUT_ID
from .components.multiline_input import MultiLineInput
from .screens.model_info_screen import ModelInfoScreen
from .screens.session_picker import SessionPickerScreen
from .screens import HelpScreen
from .screens.session_picker import SESSION_NEW_ID

logger = logging.getLogger(__name__)


class AppSessionModelMixin:
    """Session/model: action_show_model_info, action_session_picker, _open_session_picker_async, _on_session_picker_dismissed, _show_status, _on_reset_confirm, set_session_switch_handler, load_messages_into_output."""

    def action_show_model_info(self) -> None:
        """Show current model info modal (Ctrl+L)."""
        if self.coding_agent is None:
            self.notify("No model (no agent).", severity="information", timeout=2)
            return
        m = getattr(self.coding_agent, "settings", None) and getattr(self.coding_agent.settings, "model", None)
        if not m:
            self.notify("No model config.", severity="information", timeout=2)
            return
        provider = getattr(m, "provider", "-")
        model_id = getattr(m, "model_id", "-")
        context_window = getattr(m, "context_window", 0)
        max_tokens = getattr(m, "max_tokens", 0)
        self.push_screen(ModelInfoScreen(provider=provider, model_id=model_id, context_window=context_window, max_tokens=max_tokens), lambda _: None)

    def action_session_picker(self) -> None:
        """Open session picker (Ctrl+P). Load sessions and show modal."""
        if self.coding_agent is None or not hasattr(self.coding_agent, "session_manager"):
            self.notify("No session manager.", severity="information", timeout=2)
            return
        self.run_worker(self._open_session_picker_async(), exclusive=False)

    async def _open_session_picker_async(self) -> None:
        sm = getattr(self.coding_agent, "session_manager", None)
        if not sm:
            self.notify("No session manager.", severity="information", timeout=2)
            return
        try:
            sessions = await sm.list_sessions()
        except Exception as e:
            logger.exception("List sessions failed")
            self.notify(f"List sessions failed: {e}", severity="error", timeout=3)
            return
        options = [(s.session_id, f"{s.model_id} ({s.total_messages} msgs)") for s in sessions]
        self.push_screen(SessionPickerScreen(options=options, include_new=True), self._on_session_picker_dismissed)

    def _on_session_picker_dismissed(self, result: str | None) -> None:
        if result is None:
            return
        if self._session_switch_handler:
            self.run_worker(self._session_switch_handler(result), exclusive=False)
        try:
            inp = self.query_one(f"#{INPUT_ID}", MultiLineInput)
            inp.focus()
        except NoMatches:
            pass

    def _show_status(self) -> None:
        """Show status modal (/status)."""
        phase = self.state.phase
        model_id = "-"
        session_id = "-"
        if self.coding_agent:
            m = getattr(self.coding_agent, "settings", None) and getattr(self.coding_agent.settings, "model", None)
            if m:
                model_id = getattr(m, "model_id", "-")
            session_id = getattr(self.coding_agent, "_session_id", None) or "-"
        n = len(self._pending_user_inputs)
        lines = [
            f"Phase: {phase}",
            f"Model: {model_id}",
            f"Session: {session_id}",
            f"Queued: {n}",
        ]
        self.push_screen(HelpScreen("\n".join(lines)), lambda _: None)

    def _on_reset_confirm(self, confirmed: bool) -> None:
        if confirmed and self._session_switch_handler:
            self.run_worker(self._session_switch_handler(SESSION_NEW_ID), exclusive=False)

    def set_session_switch_handler(self, handler: Optional[Callable[[str], Awaitable[None]]]) -> None:
        """Set async handler for session switch (called from run_tui_mode)."""
        self._session_switch_handler = handler

    def load_messages_into_output(self, blocks: list[tuple[str, str]]) -> None:
        """Replace output with (role, content) blocks; used after session switch."""
        self.state.output_blocks.clear()
        self.state.output_blocks_with_role.clear()
        self.state.tool_expanded.clear()
        for role, content in blocks:
            self.state.output_blocks.append(content)
            self.state.output_blocks_with_role.append((role, content))
        self._refresh_output()

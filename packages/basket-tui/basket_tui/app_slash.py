"""Mixin: slash commands, slash popup, plan mode toggle."""

from textual.css.query import NoMatches
from textual import on

from .constants import INPUT_ID
from .components.multiline_input import MultiLineInput, InputWantsSlashPopup
from .screens.slash_popup import SlashCommandScreen
from .screens.code_block_overlay import CodeBlockOverlay
from .screens import HelpScreen
from .screens.session_picker import SESSION_NEW_ID


class AppSlashMixin:
    """Slash: _handle_slash_command, _run_slash_command, _show_slash_help, _on_input_wants_slash_popup, _on_slash_popup_dismissed, action_toggle_plan_mode."""

    def _run_slash_command(self, cmd: str) -> None:
        """Run a single slash command (used by slash popup)."""
        if cmd == "/clear":
            self.action_clear()
        elif cmd == "/help":
            self._show_slash_help()
        elif cmd == "/history":
            self.action_transcript_overlay()
        elif cmd == "/copy":
            self.action_copy_last()
        elif cmd == "/theme":
            self.action_toggle_dark()
            self.notify("Theme toggled.", severity="information", timeout=1)
        elif cmd == "/syntax":
            last = self.state.get_last_code_block()
            if last is None:
                self.notify("No code block found in output.", severity="information", timeout=2)
            else:
                code, lang = last
                self.push_screen(CodeBlockOverlay(code=code, language=lang), lambda _: None)
        elif cmd == "/expand":
            self.action_expand_last_tool()
        elif cmd == "/compact":
            if self._input_handler is not None:
                self.run_worker(self._send_compact_to_agent(), exclusive=False)
            else:
                self.notify("Compact not available (no agent).", severity="information", timeout=2)
        elif cmd == "/status":
            self._show_status()
        elif cmd == "/sessions":
            self.action_session_picker()
        elif cmd == "/new":
            if self._session_switch_handler:
                self.run_worker(self._session_switch_handler(SESSION_NEW_ID), exclusive=False)
            else:
                self.notify("Session switch not available.", severity="information", timeout=2)
        elif cmd == "/reset":
            self.show_approval_modal(
                title="重置当前会话?",
                body="将清空当前对话并创建新会话。",
                callback=self._on_reset_confirm,
            )
        elif cmd == "/abort":
            self.action_stop_agent()

    @on(InputWantsSlashPopup)
    def _on_input_wants_slash_popup(self, event: InputWantsSlashPopup) -> None:
        """User pressed Tab with / in input; show slash command list."""
        try:
            inp = self.query_one(f"#{INPUT_ID}", MultiLineInput)
            inp.clear()
        except NoMatches:
            pass
        self.push_screen(SlashCommandScreen(prefix=event.prefix), self._on_slash_popup_dismissed)

    def _on_slash_popup_dismissed(self, result: str | None) -> None:
        """After slash popup: run selected command and refocus input."""
        if result:
            self._run_slash_command(result)
        try:
            inp = self.query_one(f"#{INPUT_ID}", MultiLineInput)
            inp.focus()
        except NoMatches:
            pass

    async def action_toggle_plan_mode(self) -> None:
        """Toggle plan mode (Ctrl+Shift+P). Local: set on coding_agent; attach: send /plan to gateway."""
        if self.coding_agent is not None:
            self.coding_agent.set_plan_mode(not self.coding_agent.get_plan_mode())
            self._refresh_plan_mode_panel()
            self.notify(
                f"Plan mode {'on' if self.coding_agent.get_plan_mode() else 'off'}",
                severity="information",
                timeout=2,
            )
        elif self._input_handler is not None:
            await self._input_handler("/plan")

    def _handle_slash_command(self, user_input: str) -> bool:
        """
        Handle TUI slash commands. Returns True if handled (do not send to agent).
        Unknown or agent commands (e.g. /plan) return False and are passed to _input_handler.
        """
        raw = user_input.strip()
        if not raw.startswith("/"):
            return False
        parts = raw.split(maxsplit=1)
        cmd = (parts[0] or "").lower()
        if cmd == "/clear":
            self.action_clear()
            return True
        if cmd == "/help":
            self._show_slash_help()
            return True
        if cmd == "/history":
            self.action_transcript_overlay()
            return True
        if cmd == "/copy":
            self.action_copy_last()
            return True
        if cmd == "/theme":
            self.action_toggle_dark()
            self.notify("Theme toggled.", severity="information", timeout=1)
            return True
        if cmd == "/syntax":
            last = self.state.get_last_code_block()
            if last is None:
                self.notify("No code block found in output.", severity="information", timeout=2)
            else:
                code, lang = last
                self.push_screen(CodeBlockOverlay(code=code, language=lang), lambda _: None)
            return True
        if cmd == "/expand":
            self.action_expand_last_tool()
            return True
        if cmd == "/compact":
            if self._input_handler is not None:
                self.run_worker(self._send_compact_to_agent(), exclusive=False)
            else:
                self._set_input_error("Compact not available (no agent).")
                self.notify("Compact not available (no agent).", severity="information", timeout=2)
            return True
        if cmd == "/status":
            self._show_status()
            return True
        if cmd == "/sessions":
            self.action_session_picker()
            return True
        if cmd == "/new":
            if self._session_switch_handler:
                self.run_worker(self._session_switch_handler(SESSION_NEW_ID), exclusive=False)
            else:
                self._set_input_error("Session switch not available.")
                self.notify("Session switch not available.", severity="information", timeout=2)
            return True
        if cmd == "/reset":
            self.show_approval_modal(
                title="重置当前会话?",
                body="将清空当前对话并创建新会话。",
                callback=self._on_reset_confirm,
            )
            return True
        if cmd == "/abort":
            self.action_stop_agent()
            return True
        return False

    def _show_slash_help(self) -> None:
        """Show slash commands and shortcuts in a modal."""
        help_text = """Commands (type in input):
/clear   Clear output
/help    This help
/history Open transcript overlay
/copy    Copy last complete message
/theme   Toggle dark/light
/syntax  View last code block with syntax highlighting
/expand  Expand last tool result (full output)
/compact Compact context (sent to agent if supported)
/status  Show status
/sessions Session picker
/new     New session
/reset   Reset current session
/abort   Stop agent

Shortcuts:
Ctrl+Shift+T  Transcript overlay
Ctrl+E        Expand last tool result
Ctrl+G        Stop agent
Ctrl+L        Model info
Ctrl+Shift+L  Clear
Ctrl+P        Session picker
Ctrl+Shift+P  Plan mode
Ctrl+D        Toggle dark
Ctrl+T        Todo expand/collapse
Ctrl+End      Scroll to bottom
Q             Quit"""
        self.push_screen(HelpScreen(help_text), lambda _: None)

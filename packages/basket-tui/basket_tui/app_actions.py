"""Mixin: clear, copy, paste, theme, transcript overlay, expand tool, todo toggle, send compact."""

import asyncio
import logging

from textual.css.query import NoMatches

from .constants import INPUT_ID
from .components.multiline_input import MultiLineInput
from .screens.transcript_overlay import TranscriptOverlay
from .screens.tool_result_overlay import ToolResultOverlay

logger = logging.getLogger(__name__)


class AppActionsMixin:
    """Actions: clear, copy_last, copy_output, paste, toggle_dark, transcript_overlay, expand_last_tool, toggle_todo_full, _send_compact_to_agent."""

    def action_clear(self) -> None:
        """Clear output and reset state (TextArea mode)."""
        try:
            self.state.output_blocks = [self.WELCOME_LINE]
            self.state.output_blocks_with_role = [("system", self.WELCOME_LINE)]
            self.state.reset_streaming()
            self.state.phase = "idle"
            self.state.tool_block_full_results.clear()
            self.state.tool_expanded.clear()
            self._refresh_output()
            self._refresh_status_bar()
            self.notify("Output cleared.", severity="information")
        except Exception as e:
            logger.error(f"Error while clearing output: {e}")

    def action_copy_last(self) -> None:
        """Copy last complete message to clipboard (/copy). Excludes welcome line."""
        text = self.state.get_last_complete_message()
        if text and text.strip() != self.WELCOME_LINE.strip():
            text = text.strip()
        else:
            text = ""
        if not text:
            self.notify("No message to copy.", severity="information", timeout=1)
            return
        text = self._sanitize_for_clipboard(text)
        if not text:
            self.notify("No message to copy.", severity="information", timeout=1)
            return
        try:
            import pyperclip
            pyperclip.copy(text)
            self.notify(f"已复制最后一条消息 ({len(text)} 字)", severity="information", timeout=2)
        except Exception as e:
            logger.debug("pyperclip copy failed: %s", e)
            try:
                self.copy_to_clipboard(text)
                self.notify(f"已复制 {len(text)} 字", severity="information", timeout=2)
            except Exception:
                self.notify("复制失败", severity="warning", timeout=2)

    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.dark = not self.dark

    def action_paste(self) -> None:
        """Paste from clipboard into input (Cmd+V). Always paste into input regardless of focus."""
        try:
            inp = self.query_one(f"#{INPUT_ID}", MultiLineInput)
        except NoMatches:
            return
        try:
            import pyperclip
            text = pyperclip.paste()
        except Exception as e:
            logger.debug("pyperclip paste failed: %s", e)
            self.notify("粘贴失败（需要 pyperclip）", severity="warning", timeout=2)
            return
        if text:
            inp.insert(text)
            inp.focus()
            self.notify(f"已粘贴 {len(text)} 字", severity="information", timeout=1)

    def action_copy_output(self) -> None:
        """Copy full transcript to clipboard (Cmd+C)."""
        text = self.state.get_transcript_text()
        if not (text and text.strip()):
            self.notify("No content to copy.", severity="information")
            return
        text = self._sanitize_for_clipboard(text.strip())
        if not text:
            self.notify("No content to copy.", severity="information")
            return
        try:
            import pyperclip
            pyperclip.copy(text)
            self.notify(f"已复制 {len(text)} 字", severity="information", timeout=2)
        except Exception as e:
            logger.debug("pyperclip copy failed: %s", e)
            try:
                self.copy_to_clipboard(text)
                self.notify(f"已复制 {len(text)} 字", severity="information", timeout=2)
            except Exception as e2:
                logger.debug("copy_to_clipboard failed: %s", e2)
                self.notify("复制失败（需要 pyperclip 或终端支持剪贴板）", severity="warning", timeout=3)

    def action_toggle_todo_full(self) -> None:
        """Toggle todo panel between compact and full list (Ctrl+T)."""
        self._todo_show_full = not self._todo_show_full
        todos = (
            getattr(self.coding_agent, "_current_todos", [])
            if self.coding_agent is not None
            else self._last_todos
        )
        self.update_todo_panel(todos)

    def action_transcript_overlay(self) -> None:
        """Open transcript overlay (committed + streaming tail). Ctrl+Shift+T to close when open."""
        self.push_screen(
            TranscriptOverlay(get_blocks=lambda: self.state.get_transcript_blocks()),
            lambda _: None,
        )

    def action_expand_last_tool(self) -> None:
        """Open overlay with full result of last tool call (Ctrl+E)."""
        full = self.state.get_last_tool_full_result()
        if full is None:
            self.notify("No tool result to expand.", severity="information", timeout=2)
            return
        self.push_screen(ToolResultOverlay(content=full), lambda _: None)

    async def _send_compact_to_agent(self) -> None:
        """Append /compact message and send to agent (for slash popup or submit)."""
        await self.append_user_message_async("/compact")
        await asyncio.sleep(0)
        if self._input_handler is not None:
            await self._input_handler("/compact")
        self.notify("Sent /compact to agent.", severity="information", timeout=1)

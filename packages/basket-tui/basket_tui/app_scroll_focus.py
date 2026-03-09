"""Mixin: scroll, focus, escape, abort confirm, tool card toggle, click/menu, clipboard sanitize."""

import logging

from textual.containers import ScrollableContainer
from textual.widgets import Static
from textual.css.query import NoMatches
from textual.events import Click
from textual import on

from .constants import OUTPUT_CONTAINER_ID, MESSAGE_LIST_ID, INPUT_ID
from .components.message_list import MessageList
from .components.multiline_input import MultiLineInput
from .screens import CopyPasteMenuScreen

logger = logging.getLogger(__name__)


class AppScrollFocusMixin:
    """Scroll, focus, escape, abort confirm, toggle tool card, click (focus + menu), _sanitize_for_clipboard."""

    @staticmethod
    def _sanitize_for_clipboard(text: str) -> str:
        """Remove cursor, spinner, and control chars before copying to clipboard."""
        if not text:
            return ""
        s = text.strip()
        for ch in ("\x00", "\u2588", "\u2502", "\u2503", "\u2501"):
            s = s.replace(ch, "")
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        return s.strip()

    def _scroll_output_end(self) -> None:
        """Scroll the message area: to top when content fits in viewport, else to bottom."""
        try:
            container = self.query_one(f"#{OUTPUT_CONTAINER_ID}", ScrollableContainer)
            content_height = getattr(container, "scrollable_size", None)
            viewport_height = container.content_region.height
            if content_height is not None and content_height.height <= viewport_height:
                container.scroll_home()
            elif content_height is None and hasattr(self, "state"):
                # Fallback when scrollable_size unavailable: few blocks => likely fits, scroll to top
                blocks = getattr(self.state, "output_blocks_with_role", [])
                if len(blocks) <= 4:
                    container.scroll_home()
                    return
                container.scroll_end()
            else:
                container.scroll_end()
        except NoMatches:
            logger.debug("Output container not found, skipping scroll")
        except Exception as e:
            logger.error(f"Unexpected error while scrolling: {e}")

    def action_scroll_to_bottom(self) -> None:
        """Scroll the message area to the bottom (see latest messages)."""
        self._scroll_output_end()
        self.notify("Scrolled to latest.", severity="information", timeout=1)

    def action_scroll_output_up(self) -> None:
        """Scroll the message area up (Page Up from anywhere)."""
        try:
            container = self.query_one(f"#{OUTPUT_CONTAINER_ID}", ScrollableContainer)
            container.scroll_page_up()
        except NoMatches:
            logger.debug("Output container not found, skipping scroll up")
        except Exception as e:
            logger.error(f"Unexpected error while scrolling up: {e}")

    def action_scroll_output_down(self) -> None:
        """Scroll the message area down (Page Down from anywhere)."""
        try:
            container = self.query_one(f"#{OUTPUT_CONTAINER_ID}", ScrollableContainer)
            container.scroll_page_down()
        except NoMatches:
            logger.debug("Output container not found, skipping scroll down")
        except Exception as e:
            logger.error(f"Unexpected error while scrolling down: {e}")

    def action_focus_next_region(self) -> None:
        """Cycle focus to next region: message area -> input -> message area."""
        try:
            inp = self.query_one(f"#{INPUT_ID}", MultiLineInput)
            msg_list = self.query_one(f"#{MESSAGE_LIST_ID}", MessageList)
            focused = self.focused
            if focused is not None and focused == inp:
                msg_list.focus()
            else:
                inp.focus()
        except NoMatches:
            pass

    def action_focus_prev_region(self) -> None:
        """Cycle focus to previous region."""
        self.action_focus_next_region()

    def action_focus_message_region(self) -> None:
        """Move focus to message area (Ctrl+PgUp)."""
        try:
            self.query_one(f"#{MESSAGE_LIST_ID}", MessageList).focus()
        except NoMatches:
            pass

    def action_focus_input_region(self) -> None:
        """Move focus to input area (Ctrl+PgDown)."""
        try:
            self.query_one(f"#{INPUT_ID}", MultiLineInput).focus()
        except NoMatches:
            pass

    def action_escape(self) -> None:
        """Esc: abort confirm if agent running; else clear input when focus on input."""
        if self.state.is_agent_running():
            self.show_approval_modal(
                title="中止当前任务?",
                body="确定要停止 Agent 吗？",
                callback=self._on_abort_confirm,
            )
            return
        try:
            inp = self.query_one(f"#{INPUT_ID}", MultiLineInput)
            if self.focused is inp:
                inp.clear()
        except NoMatches:
            pass

    def _on_abort_confirm(self, confirmed: bool) -> None:
        """Called when user confirms or rejects abort in modal."""
        if confirmed:
            self.mark_tool_interrupted_if_any()
            self.state.cancel_agent_task()
            self._refresh_status_bar()
            self.notify("已停止", severity="information", timeout=1)

    def action_toggle_last_tool_card(self) -> None:
        """Toggle expand/collapse of last tool card (Ctrl+O)."""
        idx = self.state.get_last_tool_block_index()
        if idx is None:
            return
        self.state.tool_expanded[idx] = not self.state.tool_expanded.get(idx, False)
        self._refresh_output()

    @on(Click)
    def _on_click(self, event: Click) -> None:
        """Left-click/tap on message area: focus it for scroll (touch/keyboard). Right-click: 复制/粘贴 menu."""
        w = event.widget
        try:
            container = self.query_one(f"#{OUTPUT_CONTAINER_ID}", ScrollableContainer)
            msg_list = self.query_one(f"#{MESSAGE_LIST_ID}", MessageList)
            inp = self.query_one(f"#{INPUT_ID}", MultiLineInput)
        except NoMatches:
            return
        in_message_area = (
            w == container
            or w == msg_list
            or msg_list in w.ancestors_with_self
            or (container in w.ancestors_with_self and w != inp and inp not in w.ancestors_with_self)
        )
        if event.button == 1 and in_message_area:
            if getattr(container, "can_focus", False):
                container.focus()
            else:
                msg_list.focus()
            return
        if event.button != 3:
            return
        if w == msg_list or msg_list in w.ancestors_with_self or (container in w.ancestors_with_self and w != inp):
            self._menu_source = None
            self._menu_from_output = True
        elif w == inp or inp in w.ancestors_with_self:
            self._menu_source = inp
            self._menu_from_output = False
        else:
            return
        self.push_screen(CopyPasteMenuScreen(source_widget=self._menu_source), self._on_menu_result)

    def _on_menu_result(self, choice: str | None) -> None:
        """Handle 复制/粘贴 menu choice."""
        source = getattr(self, "_menu_source", None)
        from_output = getattr(self, "_menu_from_output", False)
        if choice == "copy" and from_output:
            text = self.state.get_transcript_text()
            if text:
                text = self._sanitize_for_clipboard(text.strip())
            if text:
                try:
                    import pyperclip
                    pyperclip.copy(text)
                    self.notify(f"已复制 {len(text)} 字", severity="information", timeout=2)
                except Exception as e:
                    logger.debug("pyperclip copy failed: %s", e)
                    try:
                        self.copy_to_clipboard(text)
                        self.notify(f"已复制 {len(text)} 字", severity="information", timeout=2)
                    except Exception:
                        self.notify("复制失败", severity="warning", timeout=2)
            else:
                self.notify("无内容可复制", severity="information", timeout=1)
        elif choice == "copy" and source is not None:
            text = CopyPasteMenuScreen._get_text_from(source)
            if text:
                text = self._sanitize_for_clipboard(text)
            if text:
                try:
                    import pyperclip
                    pyperclip.copy(text)
                    self.notify(f"已复制 {len(text)} 字", severity="information", timeout=2)
                except Exception as e:
                    logger.debug("pyperclip copy failed: %s", e)
                    try:
                        self.copy_to_clipboard(text)
                        self.notify(f"已复制 {len(text)} 字", severity="information", timeout=2)
                    except Exception:
                        self.notify("复制失败", severity="warning", timeout=2)
            else:
                self.notify("无内容可复制", severity="information", timeout=1)
        elif choice == "paste":
            self.action_paste()
        self._menu_source = None
        self._menu_from_output = False

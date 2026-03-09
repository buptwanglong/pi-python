"""Mixin: compose, on_mount, on_resize, refresh methods, todo/plan panels, long-running timer."""

import signal

from textual.app import App, ComposeResult
from textual.containers import Horizontal, ScrollableContainer
from textual.widgets import Footer, Header, Static
from textual.css.query import NoMatches
from textual.events import Resize

from .constants import (
    OUTPUT_CONTAINER_ID,
    MESSAGE_LIST_ID,
    TODO_PANEL_ID,
    PLAN_MODE_PANEL_ID,
    INPUT_ID,
    INPUT_HINT_ID,
    INPUT_ERROR_ID,
    STATUS_BAR_ID,
    STATUS_PHASE_ID,
    STATUS_MODEL_ID,
    STATUS_SESSION_ID,
    STATUS_QUEUE_ID,
    HEADER_CONTEXT_ID,
    SHORTCUT_HINT,
)
from .components.message_list import MessageList
from .components.multiline_input import MultiLineInput


class AppLayoutMixin:
    """Layout: compose, on_mount, on_resize, _set_input_error, _clear_input_error, _refresh_header_context, _refresh_status_bar, _refresh_plan_mode_panel, _refresh_output, _refresh_live_output, _on_long_running, _sync_long_running_timer, update_todo_panel, update_plan_mode, _live_display_text."""

    def compose(self) -> ComposeResult:
        """Message list (cards) in scrollable container; header context + multi-column status bar."""
        yield Header()
        yield Static("", id=HEADER_CONTEXT_ID)
        with ScrollableContainer(id=OUTPUT_CONTAINER_ID):
            yield MessageList(id=MESSAGE_LIST_ID)
        yield Static("", id=TODO_PANEL_ID)
        yield Static("", id=PLAN_MODE_PANEL_ID)
        yield MultiLineInput(id=INPUT_ID)
        yield Static(SHORTCUT_HINT, id=INPUT_HINT_ID)
        yield Static("", id=INPUT_ERROR_ID)
        with Horizontal(id=STATUS_BAR_ID):
            yield Static("", id=STATUS_PHASE_ID)
            yield Static("", id=STATUS_MODEL_ID)
            yield Static("", id=STATUS_SESSION_ID)
            yield Static("", id=STATUS_QUEUE_ID)
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        try:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        except (ValueError, OSError):
            pass
        self.state.output_blocks = [self.WELCOME_LINE]
        self.state.output_blocks_with_role = [("system", self.WELCOME_LINE)]
        self.query_one(f"#{INPUT_ID}", MultiLineInput).focus()
        if self.coding_agent is not None:
            todos = getattr(self.coding_agent, "_current_todos", [])
            self.update_todo_panel(todos)
            self._plan_mode = self.coding_agent.get_plan_mode()
        self._refresh_plan_mode_panel()
        self._refresh_header_context()
        self._refresh_status_bar()
        self._refresh_output()
        self._clear_input_error()
        try:
            container = self.query_one(f"#{OUTPUT_CONTAINER_ID}", ScrollableContainer)
            container.can_focus = True
        except NoMatches:
            pass

    def on_resize(self, _event: Resize) -> None:
        """Refresh status bar and header for minimal/full layout when width crosses 80/120."""
        self._refresh_status_bar()
        self._refresh_header_context()

    def _set_input_error(self, msg: str) -> None:
        """Show error message below input; clear when user types."""
        try:
            w = self.query_one(f"#{INPUT_ERROR_ID}", Static)
            w.update(msg)
            w.display = True
        except NoMatches:
            pass

    def _clear_input_error(self) -> None:
        """Clear input error line."""
        try:
            w = self.query_one(f"#{INPUT_ERROR_ID}", Static)
            w.update("")
            w.display = False
        except NoMatches:
            pass

    def _refresh_header_context(self) -> None:
        """Update header context line: connection/mode, model name, session id."""
        try:
            ctx = self.query_one(f"#{HEADER_CONTEXT_ID}", Static)
            width = getattr(getattr(self, "size", None), "width", 120) or 120
            left = "窄屏 建议扩大窗口" if width < 80 else "本地"
            model_name = "-"
            session_abbrev = "-"
            if self.coding_agent is not None:
                model_name = getattr(
                    getattr(self.coding_agent, "settings", None),
                    "model",
                    None,
                )
                if model_name is not None:
                    model_name = getattr(model_name, "model_id", "-") or "-"
                sid = getattr(self.coding_agent, "_session_id", None)
                if sid:
                    session_abbrev = sid[:8] if len(sid) > 8 else sid
            ctx.update(f"  {left}  |  {model_name}  |  {session_abbrev}")
        except NoMatches:
            pass

    def _on_long_running(self) -> None:
        """Called after 15s in waiting_model or tool_running."""
        self._long_running_timer = None
        self._show_still_running = True
        self._refresh_status_bar()
        self.notify("Still running…", severity="information", timeout=3)

    def _sync_long_running_timer(self) -> None:
        """Start 15s timer when phase is waiting_model/tool_running, cancel otherwise."""
        if self.state.phase in ("waiting_model", "tool_running"):
            if self._long_running_timer is None:
                self._long_running_timer = self.set_timer(15, self._on_long_running)
        else:
            if self._long_running_timer is not None:
                self._long_running_timer.stop()
                self._long_running_timer = None

    def _refresh_status_bar(self) -> None:
        """Update status bar columns: phase, model, session, queue. Minimal mode when width < 80."""
        self._sync_long_running_timer()
        try:
            phase_w = self.query_one(f"#{STATUS_PHASE_ID}", Static)
            model_w = self.query_one(f"#{STATUS_MODEL_ID}", Static)
            session_w = self.query_one(f"#{STATUS_SESSION_ID}", Static)
            queue_w = self.query_one(f"#{STATUS_QUEUE_ID}", Static)
        except NoMatches:
            return
        n = len(self._pending_user_inputs)
        minimal = getattr(self, "size", None) and getattr(self.size, "width", 120) < 80
        if self.state.phase == "error":
            phase_text = "已出错"
        elif self.state.is_agent_running():
            if self._show_still_running:
                phase_text = "Still running…"
            else:
                p = self.state.phase
                if p == "waiting_model":
                    phase_text = "等待模型…"
                elif p == "thinking":
                    phase_text = "思考中…"
                elif p == "tool_running" and self.state.current_tool_name:
                    phase_text = f"工具:{self.state.current_tool_name[:8]}"
                elif p == "streaming":
                    phase_text = "回复中…"
                else:
                    phase_text = "Running..."
        else:
            phase_text = "Ready"
            self._show_still_running = False
        phase_w.update(phase_text)
        model_name = "-"
        session_abbrev = "-"
        if not minimal and self.coding_agent is not None:
            m = getattr(getattr(self.coding_agent, "settings", None), "model", None)
            if m is not None:
                model_name = (getattr(m, "model_id", None) or "-")[:18]
            sid = getattr(self.coding_agent, "_session_id", None)
            if sid:
                session_abbrev = (sid[:8] if len(sid) > 8 else sid) or "-"
        model_w.update(model_name)
        session_w.update(session_abbrev)
        queue_w.update(f"{n} queued" if n > 0 else "")
        if minimal:
            model_w.display = False
            session_w.display = False
        else:
            model_w.display = True
            session_w.display = True

    def _refresh_plan_mode_panel(self) -> None:
        """Update the plan mode panel from _plan_mode or coding_agent."""
        on = self._plan_mode
        if self.coding_agent is not None:
            on = self.coding_agent.get_plan_mode()
        try:
            panel = self.query_one(f"#{PLAN_MODE_PANEL_ID}", Static)
            panel.update("⏸ Plan mode" if on else "")
        except NoMatches:
            pass

    def update_plan_mode(self, on: bool) -> None:
        """Set plan mode state (attach mode: from gateway plan_mode message) and refresh panel."""
        self._plan_mode = on
        self._refresh_plan_mode_panel()

    def update_todo_panel(self, todos: list) -> None:
        """Update the todo panel text from a list of todo dicts (id, content, status). Works without coding_agent (e.g. attach)."""
        self._last_todos = list(todos)
        try:
            panel = self.query_one(f"#{TODO_PANEL_ID}", Static)
        except NoMatches:
            return
        if not todos:
            panel.update("")
            return
        total = len(todos)
        done = sum(1 for t in todos if t.get("status") == "completed")
        in_progress = [t for t in todos if t.get("status") == "in_progress"]
        icons = {"completed": "✓", "pending": "○", "in_progress": "→", "cancelled": "✗"}
        if self._todo_show_full:
            lines = []
            for t in todos:
                icon = icons.get(t.get("status", "pending"), "○")
                content = (t.get("content") or "").strip()
                lines.append(f"{icon} {content}")
            panel.update("\n".join(lines))
        else:
            if in_progress:
                content = (in_progress[0].get("content") or "").strip()
                panel.update(f"[Todo {done}/{total}] → {content}")
            else:
                panel.update(f"[Todo {total} items]")

    def _live_display_text(self) -> str:
        """Text for live area: last N lines of streaming buffer (N = _live_rows or 8)."""
        buf = self.state.streaming_buffer
        if not buf:
            return ""
        n = self._live_rows or 8
        lines = buf.split("\n")
        if len(lines) <= n:
            return buf
        return "\n".join(lines[-n:])

    def _refresh_output(self) -> None:
        """Rebuild message list from state and scroll to end."""
        try:
            message_list = self.query_one(f"#{MESSAGE_LIST_ID}", MessageList)
            message_list.update_from_state(self.state)
        except NoMatches:
            return
        self._scroll_output_end()

    def _refresh_live_output(self) -> None:
        """Streaming tick: refresh message list so streaming tail updates."""
        self._refresh_output()

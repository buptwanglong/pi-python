"""
Main TUI Application for Pi Coding Agent

Composes mixins for layout, scroll/focus, session/model, agent, slash, output/messages, input, actions.
"""

import logging
from typing import Awaitable, Callable, Optional

from textual.app import App
from textual.binding import Binding

from .core.message_renderer import MessageRenderer
from .state import AppState
from .app_layout import AppLayoutMixin
from .app_scroll_focus import AppScrollFocusMixin
from .app_session_model import AppSessionModelMixin
from .app_agent import AppAgentMixin
from .app_slash import AppSlashMixin
from .app_output_messages import AppOutputMessagesMixin
from .app_input import AppInputMixin
from .app_actions import AppActionsMixin

logger = logging.getLogger(__name__)


class PiCodingAgentApp(
    AppLayoutMixin,
    App,
    AppScrollFocusMixin,
    AppSessionModelMixin,
    AppAgentMixin,
    AppSlashMixin,
    AppOutputMessagesMixin,
    AppInputMixin,
    AppActionsMixin,
):
    """
    Interactive TUI for Pi Coding Agent.

    Features:
    - Real-time streaming of LLM responses
    - Markdown rendering with syntax highlighting
    - Tool execution display
    - Multi-line input support
    """

    TITLE = "Pi Coding Agent"
    SUB_TITLE = "Interactive AI Coding Assistant"
    WELCOME_LINE = "Enter 发送，Shift+Enter 换行。右键 复制/粘贴，Q 退出。Scroll: 滚轮或 Page Up/Down。"

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("escape", "escape", "Esc", priority=True),
        Binding("tab", "focus_next_region", "Next region", show=False),
        Binding("shift+tab", "focus_prev_region", "Prev region", show=False),
        Binding("ctrl+pageup", "focus_message_region", "Focus messages", show=False),
        Binding("ctrl+pagedown", "focus_input_region", "Focus input", show=False),
        Binding("ctrl+o", "toggle_last_tool_card", "Toggle tool card", show=False),
        Binding("meta+c", "copy_output", "Copy (Cmd+C)", priority=True),
        Binding("ctrl+shift+c", "copy_output", "Copy", show=False),
        Binding("meta+v", "paste", "Paste (Cmd+V)", priority=True),
        Binding("ctrl+v", "paste", "Paste", show=False),
        Binding("ctrl+g", "stop_agent", "Stop", priority=True),
        Binding("ctrl+l", "show_model_info", "Model info"),
        Binding("ctrl+shift+l", "clear", "Clear"),
        Binding("ctrl+p", "session_picker", "Sessions"),
        Binding("ctrl+shift+p", "toggle_plan_mode", "Plan mode", show=False),
        Binding("ctrl+d", "toggle_dark", "Toggle Dark Mode"),
        Binding("ctrl+t", "toggle_todo_full", "Todo expand/collapse"),
        Binding("ctrl+shift+t", "transcript_overlay", "Transcript"),
        Binding("ctrl+e", "expand_last_tool", "Expand last tool"),
        Binding("ctrl+end", "scroll_to_bottom", "To bottom"),
        Binding("pageup", "scroll_output_up", "Scroll up", show=False),
        Binding("pagedown", "scroll_output_down", "Scroll down", show=False),
    ]

    CSS_PATH = "styles/app.tcss"

    def __init__(
        self,
        agent=None,
        coding_agent=None,
        max_cols: Optional[int] = None,
        live_rows: Optional[int] = None,
        **kwargs,
    ):
        """
        Initialize the TUI app.

        Args:
            agent: Optional Pi Agent instance to connect to
            coding_agent: Optional CodingAgent (has _current_todos); when None (e.g. attach), todos come via update_todo_panel only
            max_cols: Optional max column width for output (e.g. from --max-cols).
            live_rows: Optional number of rows for live streaming area (e.g. from --live-rows).
            **kwargs: Additional arguments for Textual App
        """
        super().__init__(**kwargs)
        self.agent = agent
        self.coding_agent = coding_agent
        self._max_cols = max_cols
        self._live_rows = live_rows
        self._todo_show_full = False
        self._last_todos: list = []
        self._plan_mode = False
        self._input_handler = None
        self._menu_source = None
        self._menu_from_output = False
        self._pending_user_inputs: list[str] = []
        self._session_switch_handler: Optional[Callable[[str], Awaitable[None]]] = None
        self._stream_refresh_timer = None
        self._streaming_length_rendered = 0
        self._long_running_timer = None
        self._show_still_running = False
        self.state = AppState()
        self.renderer = MessageRenderer()


if __name__ == "__main__":
    app = PiCodingAgentApp()
    app.run()

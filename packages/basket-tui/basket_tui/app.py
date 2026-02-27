"""
Main TUI Application for Pi Coding Agent

This module provides the main Textual App that handles:
- User input and interaction
- Streaming LLM response display
- Tool call visualization
- Agent event handling
"""

import logging
import signal
from typing import Optional
import asyncio
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Header, Footer, TextArea, OptionList, Static
from textual.widget import Widget
from textual.binding import Binding
from textual.message import Message
from textual.css.query import NoMatches
from textual.events import Click
from textual import on

from .components.multiline_input import MultiLineInput
from .core.message_renderer import MessageRenderer
from .constants import OUTPUT_CONTAINER_ID, OUTPUT_ID, TODO_PANEL_ID, PLAN_MODE_PANEL_ID, INPUT_ID
from .state import AppState

# Configure logging
logger = logging.getLogger(__name__)


class MountMessageBlock(Message):
    """Request to mount a message block (user, system, tool). Processed asynchronously."""

    def __init__(self, role: str, content, sender=None) -> None:
        super().__init__()
        self.role = role
        self.content = content


class MountWidget(Message):
    """Request to mount an existing widget (e.g. thinking block). Processed asynchronously."""

    def __init__(self, widget: Widget, sender=None) -> None:
        super().__init__()
        self.widget = widget


class ProcessPendingInputs(Message):
    """Process queued user inputs (append and run agent) after current agent completes."""


class OutputTextArea(TextArea):
    """Read-only output area: Cmd+C delegates to app copy (system clipboard)."""

    def action_copy(self) -> None:
        """Forward to app so selection is copied to system clipboard."""
        if hasattr(self, "app") and self.app is not None:
            self.app.action_copy_output()


class CopyPasteMenuScreen(ModalScreen):
    """Right-click context menu: 复制 / 粘贴."""

    CSS = """
    CopyPasteMenuScreen {
        width: auto;
        min-width: 12;
    }
    """

    def __init__(self, source_widget: Widget | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._source = source_widget

    def compose(self) -> ComposeResult:
        yield OptionList(
            OptionList.Option("复制", id="copy"),
            OptionList.Option("粘贴", id="paste"),
            id="copypaste-options",
        )

    @on(OptionList.OptionSelected)
    def _on_option(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    @staticmethod
    def _get_text_from(widget: Widget | None) -> str:
        if widget is None:
            return ""
        text = getattr(widget, "selected_text", None) or getattr(widget, "text", "")
        return (text or "").strip()


class PiCodingAgentApp(App):
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

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("meta+c", "copy_output", "Copy (Cmd+C)", priority=True),
        Binding("ctrl+shift+c", "copy_output", "Copy", show=False),
        Binding("meta+v", "paste", "Paste (Cmd+V)", priority=True),
        Binding("ctrl+v", "paste", "Paste", show=False),
        Binding("ctrl+g", "stop_agent", "Stop", priority=True),
        Binding("ctrl+l", "clear", "Clear"),
        Binding("ctrl+d", "toggle_dark", "Toggle Dark Mode"),
        Binding("ctrl+t", "toggle_todo_full", "Todo expand/collapse"),
        Binding("ctrl+p", "toggle_plan_mode", "Plan mode"),
        Binding("ctrl+end", "scroll_to_bottom", "To bottom"),
        Binding("pageup", "scroll_output_up", "Scroll up", show=False),
        Binding("pagedown", "scroll_output_down", "Scroll down", show=False),
    ]

    # Load CSS from external file
    CSS_PATH = "styles/app.tcss"

    def __init__(self, agent=None, coding_agent=None, **kwargs):
        """
        Initialize the TUI app.

        Args:
            agent: Optional Pi Agent instance to connect to
            coding_agent: Optional CodingAgent (has _current_todos); when None (e.g. attach), todos come via update_todo_panel only
            **kwargs: Additional arguments for Textual App
        """
        super().__init__(**kwargs)
        self.agent = agent
        self.coding_agent = coding_agent
        self._todo_show_full = False
        self._last_todos: list = []  # last todos passed to update_todo_panel (for attach mode toggle)
        self._plan_mode = False  # attach mode: set by plan_mode message; local: mirrors coding_agent.get_plan_mode()
        self._input_handler = None
        self._menu_source = None
        self._pending_user_inputs: list[str] = []
        self._stream_refresh_timer = None  # throttle streaming redraws to reduce flicker
        self._streaming_length_rendered = 0  # chars of current streaming block already inserted into TextArea
        self.state = AppState()
        self.renderer = MessageRenderer()

    WELCOME_LINE = "Enter 发送，Shift+Enter 换行。右键 复制/粘贴，Q 退出。Scroll: 滚轮或 Page Up/Down。"

    def compose(self) -> ComposeResult:
        """Output is a single read-only TextArea so text is selectable (click, drag, double-click)."""
        yield Header()
        with Vertical(id=OUTPUT_CONTAINER_ID):
            yield OutputTextArea(
                self.WELCOME_LINE,
                id=OUTPUT_ID,
                read_only=True,
            )
        yield Static("", id=TODO_PANEL_ID)
        yield Static("", id=PLAN_MODE_PANEL_ID)
        yield MultiLineInput(id=INPUT_ID)
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        # Ignore Ctrl+C (SIGINT) so only Q quits
        try:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        except (ValueError, OSError):
            pass  # main thread only / Windows
        self.state.output_blocks = [self.WELCOME_LINE]
        self.query_one(f"#{INPUT_ID}", MultiLineInput).focus()
        if self.coding_agent is not None:
            todos = getattr(self.coding_agent, "_current_todos", [])
            self.update_todo_panel(todos)
            self._plan_mode = self.coding_agent.get_plan_mode()
        self._refresh_plan_mode_panel()

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

    @on(Click)
    def _on_click(self, event: Click) -> None:
        """Right-click on output/input: show 复制/粘贴 menu."""
        if event.button != 3:  # 3 = right-click
            return
        w = event.widget
        try:
            output = self.query_one(f"#{OUTPUT_ID}", TextArea)
            inp = self.query_one(f"#{INPUT_ID}", MultiLineInput)
        except NoMatches:
            return
        if w == output or output in w.ancestors_with_self:
            self._menu_source = output
        elif w == inp or inp in w.ancestors_with_self:
            self._menu_source = inp
        else:
            return
        self.push_screen(CopyPasteMenuScreen(source_widget=self._menu_source), self._on_menu_result)

    def _on_menu_result(self, choice: str | None) -> None:
        """Handle 复制/粘贴 menu choice."""
        source = getattr(self, "_menu_source", None)
        if choice == "copy" and source is not None:
            text = CopyPasteMenuScreen._get_text_from(source)
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


    def _on_streaming_refresh_tick(self) -> None:
        """Called by throttle timer: append only the new streaming delta at document end to avoid full-screen redraw."""
        self._stream_refresh_timer = None
        delta_start = self._streaming_length_rendered
        new_chars = self.state.streaming_buffer[delta_start:]
        if not new_chars:
            return
        to_insert = ("\n\n" + new_chars) if delta_start == 0 else new_chars
        try:
            output = self.query_one(f"#{OUTPUT_ID}", TextArea)
        except NoMatches:
            return
        try:
            was_read_only = output.read_only
            output.read_only = False
            output.insert(to_insert, output.document.end)
        finally:
            output.read_only = was_read_only
        self._streaming_length_rendered = len(self.state.streaming_buffer)
        self._scroll_output_end()

    def _refresh_output(self) -> None:
        """Rebuild output TextArea from output_blocks + current streaming buffer."""
        try:
            output = self.query_one(f"#{OUTPUT_ID}", TextArea)
        except NoMatches:
            return
        parts = list(self.state.output_blocks)
        if self.state.streaming_assistant and self.state.streaming_buffer:
            parts.append(self.state.streaming_buffer)
        full = "\n\n".join(parts)
        output.text = full
        self._scroll_output_end()

    def _scroll_output_end(self) -> None:
        """Scroll the output to the bottom."""
        try:
            output = self.query_one(f"#{OUTPUT_ID}", TextArea)
            output.scroll_end()
        except NoMatches:
            logger.debug("Output not found, skipping scroll")
        except Exception as e:
            logger.error(f"Unexpected error while scrolling: {e}")

    async def on_mount_message_block(self, event: MountMessageBlock) -> None:
        """Append plain text to output (TextArea mode)."""
        content = event.content
        plain = content if isinstance(content, str) else str(content)
        self.state.output_blocks.append(plain)
        self._refresh_output()

    async def on_process_pending_inputs(self, _event: ProcessPendingInputs) -> None:
        """Process first queued user input after agent completed."""
        if not self._pending_user_inputs or not self._input_handler:
            return
        user_input = self._pending_user_inputs.pop(0)
        await self.append_user_message_async(user_input)
        await asyncio.sleep(0)
        await self._input_handler(user_input)

    async def on_mount_widget(self, event: MountWidget) -> None:
        """No-op when using TextArea output (no widgets mounted)."""
        pass

    def action_scroll_to_bottom(self) -> None:
        """Scroll the message area to the bottom (see latest messages)."""
        self._scroll_output_end()
        self.notify("Scrolled to latest.", severity="information", timeout=1)

    def action_scroll_output_up(self) -> None:
        """Scroll the message area up (Page Up from anywhere)."""
        try:
            output = self.query_one(f"#{OUTPUT_ID}", TextArea)
            output.scroll_page_up()
        except NoMatches:
            logger.debug("Output not found, skipping scroll up")
        except Exception as e:
            logger.error(f"Unexpected error while scrolling up: {e}")

    def action_scroll_output_down(self) -> None:
        """Scroll the message area down (Page Down from anywhere)."""
        try:
            output = self.query_one(f"#{OUTPUT_ID}", TextArea)
            output.scroll_page_down()
        except NoMatches:
            logger.debug("Output not found, skipping scroll down")
        except Exception as e:
            logger.error(f"Unexpected error while scrolling down: {e}")

    async def append_user_message_async(self, content: str) -> None:
        """Append user message to output (TextArea mode)."""
        self.state.output_blocks.append(content)
        self._refresh_output()

    async def ensure_assistant_block(self) -> None:
        """Start streaming assistant block (TextArea mode)."""
        if self.state.streaming_assistant:
            return
        self.state.streaming_assistant = True
        self.state.streaming_buffer = ""
        self._streaming_length_rendered = 0
        self._refresh_output()

    def set_agent_task(self, task: Optional[asyncio.Task]) -> None:
        """Set the currently running agent task (for cancellation)."""
        self.state.set_agent_task(task)

    def action_stop_agent(self) -> None:
        """Cancel the currently running agent task."""
        self.state.cancel_agent_task()

    def action_toggle_todo_full(self) -> None:
        """Toggle todo panel between compact and full list (Ctrl+T)."""
        self._todo_show_full = not self._todo_show_full
        todos = (
            getattr(self.coding_agent, "_current_todos", [])
            if self.coding_agent is not None
            else self._last_todos
        )
        self.update_todo_panel(todos)

    async def action_toggle_plan_mode(self) -> None:
        """Toggle plan mode (Ctrl+P). Local: set on coding_agent; attach: send /plan to gateway."""
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

    async def on_multi_line_input_submitted(
        self, event: MultiLineInput.Submitted
    ) -> None:
        """
        Handle multi-line input submission (Enter).

        If agent is still running (streaming), queue the input and process it
        after the current response completes, so user messages appear in correct order.
        """
        user_input = (event.text or "").strip()

        if not user_input:
            return

        if self._input_handler and self.state.is_agent_running():
            # Agent still streaming: queue input, process after agent completes
            self._pending_user_inputs.append(user_input)
            self.notify("已加入队列，将在当前回复完成后处理", severity="information", timeout=2)
            return

        # Mount user message block first so it appears before the assistant response
        await self.append_user_message_async(user_input)
        await asyncio.sleep(0)

        if self._input_handler:
            await self._input_handler(user_input)
        else:
            self.append_message("assistant", f"Echo: {user_input}")

    def set_input_handler(self, handler):
        """
        Set the callback for handling user input.

        Args:
            handler: Async function that takes user_input string
        """
        self._input_handler = handler

    def append_message(self, role: str, content: str) -> None:
        """
        Append a message block. User/system/tool mount a new block; assistant with ""
        is a no-op (use ensure_assistant_block() before streaming).
        """
        if role == "assistant" and content == "":
            return
        self.post_message(MountMessageBlock(role, content))

    def append_text(self, text: str) -> None:
        """Append streaming text to current assistant block (TextArea mode). Throttle redraws to reduce flicker."""
        if not self.state.streaming_assistant:
            self.state.streaming_assistant = True
            self.state.streaming_buffer = ""
        self.state.streaming_buffer += text
        if self._stream_refresh_timer is None:
            self._stream_refresh_timer = self.set_timer(0.08, self._on_streaming_refresh_tick)

    def append_thinking(self, thinking: str) -> None:
        """Append thinking as a block in output (TextArea mode)."""
        if self.state.thinking_block_index is None:
            self.state.output_blocks.append("Thinking... ")
            self.state.thinking_block_index = len(self.state.output_blocks) - 1
        self.state.output_blocks[self.state.thinking_block_index] = "Thinking... " + thinking
        self._refresh_output()

    def show_tool_call(self, tool_name: str, args: Optional[dict] = None) -> None:
        """Append tool block (TextArea mode). Finalizes assistant block first."""
        self.finalize_assistant_block()
        args = args or {}
        self.state.current_tool_name = tool_name
        self.state.current_tool_args = args
        line = self.renderer.render_tool_block_claude(tool_name, args, "执行中...", success=True).plain
        self.state.output_blocks.append(line)
        self._refresh_output()

    def show_tool_result(self, result: str, success: bool = True) -> None:
        """Update last block with tool result (TextArea mode)."""
        if self.state.current_tool_name is None:
            self._scroll_output_end()
            return
        result_line = self.renderer.format_tool_result_line(result, success)
        line = self.renderer.render_tool_block_claude(
            self.state.current_tool_name,
            self.state.current_tool_args or {},
            result_line,
            success=success,
        ).plain
        self.state.output_blocks[-1] = line
        self.state.current_tool_name = None
        self.state.current_tool_args = None
        self._refresh_output()

    def finalize_assistant_block(self, full_text: Optional[str] = None) -> None:
        """Push streaming buffer to output_blocks and clear streaming state (TextArea mode)."""
        content = (full_text if full_text is not None else self.state.streaming_buffer).strip()
        logger.debug(
            "finalize_assistant_block: full_text=%s, len(streaming_buffer)=%s, len(content)=%s, will_append=%s",
            full_text is not None,
            len(self.state.streaming_buffer),
            len(content),
            bool(content),
        )
        if content:
            self.state.output_blocks.append(content)
        self.state.streaming_assistant = False
        self.state.streaming_buffer = ""
        self.state.thinking_block_index = None
        if self._stream_refresh_timer is not None:
            self._stream_refresh_timer.stop()
            self._stream_refresh_timer = None
        self._streaming_length_rendered = 0
        self._refresh_output()

    def append_markdown(self, markdown_text: str) -> None:
        """Append markdown as plain text block (TextArea mode)."""
        self.state.output_blocks.append(markdown_text.strip())
        self._refresh_output()

    def show_code_block(self, code: str, language: str = "python") -> None:
        """Append code block as plain text (TextArea mode)."""
        self.state.output_blocks.append(f"```{language}\n{code}\n```")
        self._refresh_output()

    def action_clear(self) -> None:
        """Clear output and reset state (TextArea mode)."""
        try:
            self.state.output_blocks = [self.WELCOME_LINE]
            self.state.reset_streaming()
            self._refresh_output()
            self.notify("Output cleared.", severity="information")
        except Exception as e:
            logger.error(f"Error while clearing output: {e}")

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
        """Copy selection to clipboard (Cmd+C), or full output if nothing selected."""
        try:
            output = self.query_one(f"#{OUTPUT_ID}", TextArea)
        except NoMatches:
            self.notify("No output to copy.", severity="warning")
            return
        text = getattr(output, "selected_text", None) or output.text
        if not (text and text.strip()):
            self.notify("No content to copy.", severity="information")
            return
        text = text.strip()
        # Use system clipboard (pyperclip) so Cmd+C / Cmd+V use the same clipboard
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


# Example usage
if __name__ == "__main__":
    app = PiCodingAgentApp()
    app.run()

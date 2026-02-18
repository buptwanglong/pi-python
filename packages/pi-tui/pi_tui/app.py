"""
Main TUI Application for Pi Coding Agent

This module provides the main Textual App that handles:
- User input and interaction
- Streaming LLM response display
- Tool call visualization
- Agent event handling
"""

import logging
from typing import Any, Optional
import asyncio
from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Header, Footer, Static
from textual.widget import Widget
from textual.binding import Binding
from textual.message import Message
from textual.css.query import NoMatches
from rich.text import Text

from .components.multiline_input import MultiLineInput
from .components.message_blocks import ThinkingBlock, ToolBlock
from .core.message_renderer import MessageRenderer
from .constants import (
    OUTPUT_CONTAINER_ID,
    OUTPUT_ID,
    INPUT_ID,
    MESSAGE_BLOCK_CLASS,
    MESSAGE_USER_CLASS,
    MESSAGE_ASSISTANT_CLASS,
    MESSAGE_SYSTEM_CLASS,
)
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


class EnsureAssistantBlockAndAppend(Message):
    """Request to ensure an assistant block exists (e.g. after tool) and append text. Processed asynchronously."""

    def __init__(self, text: str, sender=None) -> None:
        super().__init__()
        self.text = text


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
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+g", "stop_agent", "Stop", priority=True),
        Binding("ctrl+l", "clear", "Clear"),
        Binding("ctrl+d", "toggle_dark", "Toggle Dark Mode"),
        Binding("ctrl+end", "scroll_to_bottom", "To bottom"),
        Binding("pageup", "scroll_output_up", "Scroll up", show=False),
        Binding("pagedown", "scroll_output_down", "Scroll down", show=False),
    ]

    # Load CSS from external file
    CSS_PATH = "styles/app.tcss"

    def __init__(self, agent=None, **kwargs):
        """
        Initialize the TUI app.

        Args:
            agent: Optional Pi Agent instance to connect to
            **kwargs: Additional arguments for Textual App
        """
        super().__init__(**kwargs)
        self.agent = agent
        self._input_handler = None
        self.state = AppState()
        self.renderer = MessageRenderer()

    def compose(self) -> ComposeResult:
        """Create the UI layout. Output is a scrollable container for message blocks."""
        yield Header()
        with Vertical(id=OUTPUT_CONTAINER_ID):
            with VerticalScroll(id=OUTPUT_ID):
                yield Static(
                    "Welcome to Pi Coding Agent!",
                    classes=f"{MESSAGE_BLOCK_CLASS} {MESSAGE_SYSTEM_CLASS}",
                )
                yield Static(
                    "Type your request. Enter to send, Shift+Enter for new line. "
                    "Scroll: move pointer here + trackpad, or Page Up/Down, or Ctrl+End to bottom.",
                    classes=f"{MESSAGE_BLOCK_CLASS} {MESSAGE_SYSTEM_CLASS}",
                )
        yield MultiLineInput(id=INPUT_ID)
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        self.query_one(f"#{INPUT_ID}", MultiLineInput).focus()

    async def on_mount_message_block(self, event: MountMessageBlock) -> None:
        """Mount a message block (user, system, tool) to the output container."""
        role, content = event.role, event.content
        container = self.query_one(f"#{OUTPUT_ID}", VerticalScroll)
        if isinstance(content, Widget):
            content.add_class(MESSAGE_BLOCK_CLASS)
            content.add_class(f"message-{role}")
            await container.mount(content)
        else:
            if role == "user":
                renderable = self.renderer.render_user_message(content)
            elif role == "system":
                renderable = self.renderer.render_system_message(content)
            else:
                renderable = content if hasattr(content, "__rich_console__") else Text(str(content))
            block = Static(renderable, classes=MESSAGE_BLOCK_CLASS, id=None)
            block.add_class(f"message-{role}")
            await container.mount(block)
        self._scroll_output_end()

    async def on_mount_widget(self, event: MountWidget) -> None:
        """Mount an existing widget (e.g. thinking block, tool block) to the output container."""
        container = self.query_one(f"#{OUTPUT_ID}", VerticalScroll)
        await container.mount(event.widget)
        self._scroll_output_end()

    async def on_ensure_assistant_block_and_append(self, event: "EnsureAssistantBlockAndAppend") -> None:
        """Ensure assistant block exists (e.g. after tool), then append text. Used for post-tool summary."""
        await self.ensure_assistant_block()
        self.state.streaming_buffer += event.text
        if self.state.has_active_assistant_widget():
            self.state.current_assistant_widget.update(
                self.renderer.render_assistant_text(self.state.streaming_buffer)
            )
        self._scroll_output_end()

    def _scroll_output_end(self) -> None:
        """Scroll the output container to the bottom."""
        try:
            output = self.query_one(f"#{OUTPUT_ID}", VerticalScroll)
            output.scroll_end()
        except NoMatches:
            logger.debug("Output container not found, skipping scroll")
        except Exception as e:
            logger.error(f"Unexpected error while scrolling to bottom: {e}")

    def action_scroll_to_bottom(self) -> None:
        """Scroll the message area to the bottom (see latest messages)."""
        self._scroll_output_end()
        self.notify("Scrolled to latest.", severity="information", timeout=1)

    def action_scroll_output_up(self) -> None:
        """Scroll the message area up (Page Up from anywhere)."""
        try:
            output = self.query_one(f"#{OUTPUT_ID}", VerticalScroll)
            output.scroll_page_up()
        except NoMatches:
            logger.debug("Output container not found, skipping scroll up")
        except Exception as e:
            logger.error(f"Unexpected error while scrolling up: {e}")

    def action_scroll_output_down(self) -> None:
        """Scroll the message area down (Page Down from anywhere)."""
        try:
            output = self.query_one(f"#{OUTPUT_ID}", VerticalScroll)
            output.scroll_page_down()
        except NoMatches:
            logger.debug("Output container not found, skipping scroll down")
        except Exception as e:
            logger.error(f"Unexpected error while scrolling down: {e}")

    async def append_user_message_async(self, content: str) -> None:
        """Mount the user message block immediately so it appears before the assistant block."""
        block = Static(
            self.renderer.render_user_message(content),
            classes=f"{MESSAGE_BLOCK_CLASS} {MESSAGE_USER_CLASS}",
            id=None,
        )
        container = self.query_one(f"#{OUTPUT_ID}", VerticalScroll)
        await container.mount(block)
        self._scroll_output_end()

    async def ensure_assistant_block(self) -> None:
        """Create and mount the current assistant (streaming) block. Call before agent.run()."""
        if self.state.has_active_assistant_widget():
            return
        block = Static("", classes=f"{MESSAGE_BLOCK_CLASS} {MESSAGE_ASSISTANT_CLASS}", id=None)
        container = self.query_one(f"#{OUTPUT_ID}", VerticalScroll)
        await container.mount(block)
        self.state.current_assistant_widget = block
        self.state.streaming_buffer = ""
        self._scroll_output_end()

    def set_agent_task(self, task: Optional[asyncio.Task]) -> None:
        """Set the currently running agent task (for cancellation)."""
        self.state.set_agent_task(task)

    def action_stop_agent(self) -> None:
        """Cancel the currently running agent task."""
        self.state.cancel_agent_task()

    async def on_multi_line_input_submitted(
        self, event: MultiLineInput.Submitted
    ) -> None:
        """
        Handle multi-line input submission (Enter).

        Args:
            event: Submitted event with .text
        """
        user_input = (event.text or "").strip()

        if not user_input:
            return

        # Mount user message block first so it appears before the assistant response
        await self.append_user_message_async(user_input)
        # Yield so the UI paints the user block before the agent starts
        await asyncio.sleep(0)

        # Forward to agent if connected
        if self.agent and self._input_handler:
            await self._input_handler(user_input)
        else:
            # Echo response (for testing without agent)
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
        """Append streaming text to the current assistant block (buffer + update in place).
        If there is no current block (e.g. after a tool call), posts EnsureAssistantBlockAndAppend
        so the summary text gets a new block.
        """
        if self.state.has_active_assistant_widget():
            self.state.streaming_buffer += text
            self.state.current_assistant_widget.update(
                self.renderer.render_assistant_text(self.state.streaming_buffer)
            )
            self._scroll_output_end()
        else:
            self.post_message(EnsureAssistantBlockAndAppend(text))

    def append_thinking(self, thinking: str) -> None:
        """Append thinking text. Mounts a thinking block on first call, then updates in place."""
        if not self.state.has_active_thinking_widget():
            self.state.current_thinking_widget = ThinkingBlock()
            self.post_message(MountWidget(self.state.current_thinking_widget))
        self.state.current_thinking_widget.append_thinking(thinking)
        self._scroll_output_end()

    def show_tool_call(self, tool_name: str, args: Optional[dict] = None) -> None:
        """Show tool call in a separate block: 调用 / 入参 / 结果 (结果=执行中...).
        Finalizes the current assistant block first so order is: 模型首段 → 工具执行 → 模型总结.
        """
        # Freeze current assistant text so tool block appears after it; next stream will open a new block
        self.finalize_assistant_block()
        args = args or {}
        tool_block = ToolBlock(tool_name, args)
        self.state.current_tool_widget = tool_block
        self.post_message(MountWidget(tool_block))

    def show_tool_result(self, result: str, success: bool = True) -> None:
        """Update the current tool block with 结果 (or mount one if none)."""
        if self.state.has_active_tool_widget():
            self.state.current_tool_widget.update_result(result, success)
            self.state.current_tool_widget = None
        self._scroll_output_end()

    def finalize_assistant_block(self, full_text: Optional[str] = None) -> None:
        """Replace current assistant block content with Markdown and clear streaming state.
        Uses internal streaming_buffer (assistant text only; tools are in separate blocks) when full_text is None.
        """
        content = (full_text if full_text is not None else self.state.streaming_buffer).strip()
        if self.state.has_active_assistant_widget() and content:
            self.state.current_assistant_widget.update(
                self.renderer.render_assistant_markdown(content)
            )
        self.state.reset_streaming()
        self._scroll_output_end()

    def append_markdown(self, markdown_text: str) -> None:
        """Append a markdown block (mounts a new block)."""
        self.post_message(
            MountMessageBlock("system", self.renderer.render_assistant_markdown(markdown_text))
        )

    def show_code_block(self, code: str, language: str = "python") -> None:
        """Display a code block (mounts a new block with syntax highlighting)."""
        try:
            from rich.syntax import Syntax

            syntax = Syntax(
                code,
                language,
                theme="monokai",
                line_numbers=True,
                word_wrap=False,
                background_color="#1e1e1e",
            )
            block = Static(syntax, classes=MESSAGE_BLOCK_CLASS)
            self.post_message(MountWidget(block))
        except ImportError:
            logger.error("Pygments not available for syntax highlighting")
            # Fallback to plain text
            self.append_message("system", f"```{language}\n{code}\n```")
        except Exception as e:
            logger.error(f"Error displaying code block: {e}")
            # Fallback to plain text
            self.append_message("system", code)

    def action_clear(self) -> None:
        """Clear all message blocks and reset streaming state."""
        try:
            output = self.query_one(f"#{OUTPUT_ID}", VerticalScroll)
            for child in list(output.children):
                child.remove()
            self.state.reset_streaming()
            self.append_message("system", "Output cleared.")
        except NoMatches:
            logger.error("Output container not found, cannot clear")
        except Exception as e:
            logger.error(f"Error while clearing output: {e}")

    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.dark = not self.dark


# Example usage
if __name__ == "__main__":
    app = PiCodingAgentApp()
    app.run()

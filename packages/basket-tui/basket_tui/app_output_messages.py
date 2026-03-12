"""Mixin: message blocks, streaming, tool call/result, finalize, append_user_message_async, ensure_assistant_block."""

import asyncio
import logging
import time
from typing import Optional

from .messages import MountMessageBlock, MountWidget, ProcessPendingInputs

logger = logging.getLogger(__name__)

# Braille spinner for "Thinking..." (improvement 5, OpenClaw-style)
BRAILLE_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class AppOutputMessagesMixin:
    """Output/messages: on_mount_message_block, on_process_pending_inputs, on_mount_widget, _on_streaming_refresh_tick, append_user_message_async, ensure_assistant_block, append_message, append_text, append_thinking, finalize_assistant_block, show_tool_call, show_tool_result, show_ask_question, append_markdown, show_code_block."""

    def _on_streaming_refresh_tick(self) -> None:
        """Update only the live area with current streaming buffer (history stays committed)."""
        self._stream_refresh_timer = None
        self._refresh_live_output()
        self._scroll_output_end()

    async def on_mount_message_block(self, event: MountMessageBlock) -> None:
        """Append plain text to output (role + content)."""
        content = event.content
        plain = content if isinstance(content, str) else str(content)
        role = getattr(event, "role", "assistant")
        self.state.output_blocks.append(plain)
        self.state.output_blocks_with_role.append((role, plain))
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

    async def append_user_message_async(self, content: str) -> None:
        """Append user message to output (TextArea mode)."""
        self.state.output_blocks.append(content)
        self.state.output_blocks_with_role.append(("user", content))
        self._refresh_output()

    async def ensure_assistant_block(self) -> None:
        """Start streaming assistant block (TextArea mode)."""
        if self.state.streaming_assistant:
            return
        self.state.streaming_assistant = True
        self.state.streaming_buffer = ""
        self._streaming_length_rendered = 0
        self._refresh_output()

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

    def _start_thinking_spinner(self) -> None:
        """Start timer to animate Braille spinner and elapsed time (improvement 5)."""
        if getattr(self, "_thinking_spinner_timer", None) is not None:
            return
        self._thinking_spinner_timer = self.set_timer(0.08, self._on_thinking_spinner_tick)

    def _on_thinking_spinner_tick(self) -> None:
        """Update thinking block with next Braille frame and elapsed time; keep accumulated content."""
        self._thinking_spinner_timer = None
        idx = self.state.thinking_block_index
        if idx is None or idx >= len(self.state.output_blocks):
            return
        start = self.state.thinking_start_time
        if start is None:
            start = time.time()
            self.state.thinking_start_time = start
        elapsed = time.time() - start
        frame_idx = getattr(self, "_thinking_spinner_frame_index", 0) % len(BRAILLE_SPINNER_FRAMES)
        frame = BRAILLE_SPINNER_FRAMES[frame_idx]
        content = getattr(self.state, "thinking_content", "") or ""
        text = f"{frame} Thinking... ({elapsed:.1f}s)" + (f" {content}" if content else "")
        self.state.output_blocks[idx] = text
        self.state.output_blocks_with_role[idx] = ("assistant", text)
        self._thinking_spinner_frame_index = (frame_idx + 1) % len(BRAILLE_SPINNER_FRAMES)
        self._refresh_output()
        if self.state.thinking_block_index is not None:
            self._thinking_spinner_timer = self.set_timer(0.08, self._on_thinking_spinner_tick)

    def _stop_thinking_spinner(self) -> None:
        """Stop Braille spinner timer (e.g. on finalize)."""
        t = getattr(self, "_thinking_spinner_timer", None)
        if t is not None:
            t.stop()
            self._thinking_spinner_timer = None

    def append_thinking(self, thinking: str) -> None:
        """Append thinking as a block in output (TextArea mode). Braille spinner + elapsed time (improvement 5)."""
        just_created = self.state.thinking_block_index is None
        if just_created:
            self.state.thinking_start_time = time.time()
            self.state.thinking_content = ""
            self.state.output_blocks.append("Thinking... ")
            self.state.output_blocks_with_role.append(("assistant", "Thinking... "))
            self.state.thinking_block_index = len(self.state.output_blocks) - 1
            self._start_thinking_spinner()
        self.state.thinking_content = (getattr(self.state, "thinking_content", "") or "") + thinking
        elapsed = time.time() - (self.state.thinking_start_time or time.time())
        frame_idx = getattr(self, "_thinking_spinner_frame_index", 0) % len(BRAILLE_SPINNER_FRAMES)
        frame = BRAILLE_SPINNER_FRAMES[frame_idx]
        text = f"{frame} Thinking... ({elapsed:.1f}s)" + (f" {self.state.thinking_content}" if self.state.thinking_content else "")
        self.state.output_blocks[self.state.thinking_block_index] = text
        self.state.output_blocks_with_role[self.state.thinking_block_index] = ("assistant", text)
        self._refresh_output()

    def show_tool_call(self, tool_name: str, args: Optional[dict] = None) -> None:
        """Append tool block (TextArea mode). Finalizes assistant block first."""
        self.finalize_assistant_block()
        args = args or {}
        self.state.current_tool_name = tool_name
        self.state.current_tool_args = args
        line = self.renderer.render_tool_block_claude(tool_name, args, "执行中...", success=True).plain
        self.state.output_blocks.append(line)
        self.state.output_blocks_with_role.append(("tool", line))
        self._refresh_output()

    def show_tool_result(self, result: str, success: bool = True) -> None:
        """Update last block with tool result (TextArea mode); store full result for expand."""
        if self.state.current_tool_name is None:
            self._scroll_output_end()
            return
        self.state.tool_block_full_results.append(result)
        result_line = self.renderer.format_tool_result_line(result, success)
        line = self.renderer.render_tool_block_claude(
            self.state.current_tool_name,
            self.state.current_tool_args or {},
            result_line,
            success=success,
        ).plain
        self.state.output_blocks[-1] = line
        self.state.output_blocks_with_role[-1] = ("tool", line)
        self.state.current_tool_name = None
        self.state.current_tool_args = None
        self._refresh_output()

    def show_ask_question(self, question: str, options: Optional[list] = None) -> None:
        """
        Append a dedicated 'Agent asks you' block (not a tool call). Use for ask_user_question.
        """
        self.finalize_assistant_block()
        line = self.renderer.render_ask_question_block(
            question or "", options or []
        ).plain
        self.state.output_blocks.append(line)
        self.state.output_blocks_with_role.append(("system", line))
        self._refresh_output()

    def finalize_assistant_block(self, full_text: Optional[str] = None) -> None:
        """Push streaming buffer to output_blocks and clear streaming state (TextArea mode).
        If there was a thinking block, keep it as a separate block (optionally truncated).
        """
        content = (full_text if full_text is not None else self.state.streaming_buffer).strip()
        logger.debug(
            "finalize_assistant_block: full_text=%s, len(streaming_buffer)=%s, len(content)=%s, will_append=%s",
            full_text is not None,
            len(self.state.streaming_buffer),
            len(content),
            bool(content),
        )
        idx = self.state.thinking_block_index
        if idx is not None and idx < len(self.state.output_blocks):
            block = self.state.output_blocks[idx]
            if len(block) > 250:
                truncated = block[:247] + "..."
                self.state.output_blocks[idx] = truncated
                self.state.output_blocks_with_role[idx] = ("assistant", truncated)
        if content:
            self.state.output_blocks.append(content)
            self.state.output_blocks_with_role.append(("assistant", content))
        self.state.streaming_assistant = False
        self.state.streaming_buffer = ""
        self.state.thinking_block_index = None
        self.state.thinking_start_time = None
        self.state.thinking_content = ""
        self._stop_thinking_spinner()
        if self._stream_refresh_timer is not None:
            self._stream_refresh_timer.stop()
            self._stream_refresh_timer = None
        self._streaming_length_rendered = 0
        self._refresh_output()

    def append_markdown(self, markdown_text: str) -> None:
        """Append markdown as plain text block (TextArea mode)."""
        text = markdown_text.strip()
        self.state.output_blocks.append(text)
        self.state.output_blocks_with_role.append(("assistant", text))
        self._refresh_output()

    def show_code_block(self, code: str, language: str = "python") -> None:
        """Append code block as plain text (TextArea mode)."""
        block = f"```{language}\n{code}\n```"
        self.state.output_blocks.append(block)
        self.state.output_blocks_with_role.append(("assistant", block))
        self._refresh_output()

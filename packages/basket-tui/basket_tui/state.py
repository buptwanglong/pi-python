"""
Application State Management

This module provides the AppState dataclass that encapsulates
all stateful components of the Pi TUI application.

Committed vs in-flight: output_blocks is the list of committed (finalized)
content strings; streaming_buffer + streaming_assistant represent the
single in-flight assistant cell. Transcript overlay uses both.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import asyncio
from textual.widgets import Static


@dataclass
class OutputCell:
    """
    Optional abstraction for a single output block (committed or in-flight).
    role: user, assistant, system, tool; content: display text.
    """
    role: str
    content: str
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None


@dataclass
class AppState:
    """
    Centralized state management for Pi TUI Application.

    Attributes:
        output_blocks: Plain-text blocks when using TextArea output (selectable).
        streaming_buffer: Accumulated text for current assistant message.
        streaming_assistant: True while streaming an assistant block (between ensure and finalize).
        current_assistant_widget: Widget displaying streaming assistant (None when using TextArea).
        current_tool_widget: Widget displaying current tool call (None when using TextArea).
        current_thinking_widget: Widget displaying thinking/reasoning text.
        agent_task: Currently running agent task (for cancellation).
    """

    output_blocks: List[str] = field(default_factory=list)
    """Parallel to output_blocks: (role, content) for transcript Markdown rendering."""
    output_blocks_with_role: List[Tuple[str, str]] = field(default_factory=list)
    streaming_buffer: str = ""
    streaming_assistant: bool = False
    current_assistant_widget: Optional[Static] = None
    current_tool_widget: Optional[Static] = None
    current_thinking_widget: Optional[Static] = None
    current_tool_name: Optional[str] = None
    current_tool_args: Optional[dict] = None
    thinking_block_index: Optional[int] = None
    """When thinking block is active, time when it started (for Braille spinner elapsed time)."""
    thinking_start_time: Optional[float] = None
    """Accumulated thinking text for current block (so spinner doesn't overwrite it)."""
    thinking_content: str = ""
    agent_task: Optional[asyncio.Task] = None
    tool_block_full_results: List[str] = field(default_factory=list)
    """Conversation phase for status bar: idle, waiting_model, thinking, streaming, tool_running, error."""
    phase: str = "idle"
    """Per-block expand state for tool cards (block index -> expanded)."""
    tool_expanded: Dict[int, bool] = field(default_factory=dict)

    def reset_streaming(self) -> None:
        """
        Reset all streaming-related state.

        Called when finalizing an assistant response or clearing the output.
        """
        self.current_assistant_widget = None
        self.streaming_buffer = ""
        self.streaming_assistant = False
        self.current_tool_widget = None
        self.current_thinking_widget = None
        self.current_tool_name = None
        self.current_tool_args = None
        self.thinking_block_index = None
        self.thinking_start_time = None
        self.thinking_content = ""
        # tool_block_full_results is not cleared on reset_streaming; cleared on reset_all / clear

    def reset_all(self) -> None:
        """
        Reset all state including agent task.

        Called when clearing the output or resetting the application.
        """
        self.reset_streaming()
        self.agent_task = None
        self.phase = "idle"
        self.tool_block_full_results.clear()
        self.output_blocks_with_role.clear()
        self.tool_expanded.clear()

    def get_last_tool_block_index(self) -> Optional[int]:
        """Index of last block with role 'tool', or None."""
        for i in range(len(self.output_blocks_with_role) - 1, -1, -1):
            if self.output_blocks_with_role[i][0] == "tool":
                return i
        return None

    def get_transcript_blocks(self) -> List[Tuple[str, str]]:
        """
        Blocks for transcript overlay: list of (role, content).
        role is one of: user, assistant, system, tool.
        Includes streaming tail as ("assistant", streaming_buffer) when in-flight.
        """
        out = list(self.output_blocks_with_role)
        if self.streaming_assistant and self.streaming_buffer:
            out.append(("assistant", self.streaming_buffer))
        return out

    def get_last_tool_full_result(self) -> Optional[str]:
        """Last full tool result for expand overlay; None if none."""
        if not self.tool_block_full_results:
            return None
        return self.tool_block_full_results[-1]

    def has_active_assistant_widget(self) -> bool:
        """Check if there's an active assistant block for streaming (widget or TextArea mode)."""
        return self.current_assistant_widget is not None or self.streaming_assistant

    def has_active_tool_widget(self) -> bool:
        """Check if there's an active tool widget."""
        return self.current_tool_widget is not None

    def has_active_thinking_widget(self) -> bool:
        """Check if there's an active thinking widget."""
        return self.current_thinking_widget is not None

    def is_agent_running(self) -> bool:
        """Check if an agent task is currently running."""
        return self.agent_task is not None and not self.agent_task.done()

    def set_agent_task(self, task: Optional[asyncio.Task]) -> None:
        """Set the currently running agent task."""
        self.agent_task = task

    def cancel_agent_task(self) -> bool:
        """
        Cancel the currently running agent task.

        Returns:
            True if task was cancelled, False if no task or already done
        """
        if self.is_agent_running():
            self.agent_task.cancel()
            return True
        return False

    def get_transcript_text(self) -> str:
        """
        Full transcript for overlay: committed output_blocks plus current
        streaming tail (in-flight assistant content).
        """
        parts = list(self.output_blocks)
        if self.streaming_assistant and self.streaming_buffer:
            parts.append(self.streaming_buffer)
        return "\n\n".join(parts)

    def get_last_complete_message(self) -> str:
        """
        Last copyable message: last non-empty block from output_blocks.
        When streaming, this is the last finalized block (excludes current buffer).
        """
        for i in range(len(self.output_blocks) - 1, -1, -1):
            block = (self.output_blocks[i] or "").strip()
            if block:
                return block
        return ""

    def get_last_code_block(self) -> tuple[str, str] | None:
        """
        Last fenced code block in output_blocks (```lang\\n...\\n```).
        Returns (code, language) or None if none found.
        """
        full = "\n\n".join(self.output_blocks)
        last_close = full.rfind("```")
        if last_close == -1:
            return None
        # Find the opening ``` of this block (the one before the closing)
        start = full.rfind("```", 0, last_close)
        if start == -1 or start == last_close:
            return None
        chunk = full[start : last_close + 3]
        first_nl = chunk.find("\n")
        if first_nl == -1:
            return None
        lang = (chunk[3:first_nl].strip() or "text").lower()
        code_start = first_nl + 1
        close_marker = chunk.find("\n```", code_start)
        if close_marker == -1:
            return None
        code = chunk[code_start:close_marker].strip()
        return (code, lang)

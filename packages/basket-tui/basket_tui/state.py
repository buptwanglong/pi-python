"""
Application State Management

This module provides the AppState dataclass that encapsulates
all stateful components of the Pi TUI application.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import asyncio
from textual.widgets import Static


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
    streaming_buffer: str = ""
    streaming_assistant: bool = False
    current_assistant_widget: Optional[Static] = None
    current_tool_widget: Optional[Static] = None
    current_thinking_widget: Optional[Static] = None
    current_tool_name: Optional[str] = None
    current_tool_args: Optional[dict] = None
    thinking_block_index: Optional[int] = None
    agent_task: Optional[asyncio.Task] = None

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

    def reset_all(self) -> None:
        """
        Reset all state including agent task.

        Called when clearing the output or resetting the application.
        """
        self.reset_streaming()
        self.agent_task = None

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

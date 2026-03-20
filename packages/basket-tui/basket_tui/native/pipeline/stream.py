"""
Stream assembler for terminal-native TUI.

Accumulates text_delta / thinking_delta, tool_call_start/end, and commits
assistant messages on agent_complete.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class StreamAssembler:
    """
    In-memory state for streaming assistant output and tool blocks.

    - text_delta / thinking_delta: append to buffer.
    - agent_complete: append buffer as one assistant message, clear buffer.
    - tool_call_start / tool_call_end: record tool and on end append one tool message.
    """

    __slots__ = ("messages", "_buffer", "_thinking_buffer", "_current_tool")

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self._buffer = ""
        self._thinking_buffer = ""
        self._current_tool: Optional[dict[str, Any]] = None

    def text_delta(self, delta: str) -> None:
        """Append text delta to streaming buffer."""
        self._buffer += delta
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Text appended to buffer",
                extra={"delta_len": len(delta), "buffer_size": len(self._buffer)},
            )

    def thinking_delta(self, delta: str) -> None:
        """Append thinking delta (optional; can be shown or discarded)."""
        self._thinking_buffer += delta
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Thinking appended",
                extra={"delta_len": len(delta), "thinking_size": len(self._thinking_buffer)},
            )

    def tool_call_start(self, tool_name: str, arguments: Optional[dict] = None) -> None:
        """Record start of a tool call."""
        self._current_tool = {
            "tool_name": tool_name,
            "arguments": arguments or {},
            "result": None,
            "error": None,
        }
        logger.info(
            "Tool call recorded",
            extra={
                "tool_name": tool_name,
                "args_count": len(arguments) if arguments else 0,
            },
        )

    def tool_call_end(
        self,
        tool_name: str,
        result: Any = None,
        error: Optional[str] = None,
    ) -> None:
        """Record end of tool call and append a tool message."""
        if self._current_tool and self._current_tool.get("tool_name") == tool_name:
            self._current_tool["result"] = result
            self._current_tool["error"] = error
        else:
            self._current_tool = {
                "tool_name": tool_name,
                "arguments": {},
                "result": result,
                "error": error,
            }
        content = tool_name
        if self._current_tool.get("error"):
            content += f"\n-> error: {self._current_tool['error']}"
        elif self._current_tool.get("result") is not None:
            content += f"\n-> {self._current_tool['result']}"
        self.messages.append({"role": "tool", "content": content})
        logger.info(
            "Tool result recorded",
            extra={
                "tool_name": tool_name,
                "has_error": error is not None,
                "messages_count": len(self.messages),
            },
        )
        self._current_tool = None

    def agent_complete(self) -> None:
        """Commit streaming buffer as one assistant message and clear buffer."""
        buffer_len = len(self._buffer)
        if self._buffer:
            self.messages.append({"role": "assistant", "content": self._buffer})
        logger.info(
            "Buffer committed",
            extra={"buffer_len": buffer_len, "total_messages": len(self.messages)},
        )
        self._buffer = ""
        self._thinking_buffer = ""

    def flush_buffer(self) -> bool:
        """Commit current _buffer as assistant message if non-empty.

        Returns True if content was committed, False if buffer was empty.
        Used by tool_call_start to commit streaming text before the tool block.
        """
        if not self._buffer:
            return False
        self.messages.append({"role": "assistant", "content": self._buffer})
        buffer_len = len(self._buffer)
        self._buffer = ""
        logger.info(
            "Buffer flushed",
            extra={"buffer_len": buffer_len, "total_messages": len(self.messages)},
        )
        return True

    def abort(self) -> None:
        """Clear all buffers and current tool state (abort operation)."""
        had_buffer = bool(self._buffer)
        had_thinking = bool(self._thinking_buffer)
        had_tool = self._current_tool is not None

        self._buffer = ""
        self._thinking_buffer = ""
        self._current_tool = None

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Buffers cleared",
                extra={
                    "had_buffer": had_buffer,
                    "had_thinking": had_thinking,
                    "had_tool": had_tool,
                },
            )

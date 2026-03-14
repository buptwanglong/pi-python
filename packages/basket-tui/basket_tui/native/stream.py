"""
Stream assembler for terminal-native TUI.

Accumulates text_delta / thinking_delta, tool_call_start/end, and commits
assistant messages on agent_complete.
"""

from typing import Any, Optional


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

    def thinking_delta(self, delta: str) -> None:
        """Append thinking delta (optional; can be shown or discarded)."""
        self._thinking_buffer += delta

    def tool_call_start(self, tool_name: str, arguments: Optional[dict] = None) -> None:
        """Record start of a tool call."""
        self._current_tool = {
            "tool_name": tool_name,
            "arguments": arguments or {},
            "result": None,
            "error": None,
        }

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
        self._current_tool = None

    def agent_complete(self) -> None:
        """Commit streaming buffer as one assistant message and clear buffer."""
        if self._buffer:
            self.messages.append({"role": "assistant", "content": self._buffer})
        self._buffer = ""
        self._thinking_buffer = ""

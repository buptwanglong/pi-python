"""
Message dispatch for terminal-native TUI: WebSocket message → StreamAssembler + output.
"""

import logging
import queue
import threading
from typing import Any, Callable, Optional

from .render import render_messages
from .stream import StreamAssembler

logger = logging.getLogger(__name__)


def _dispatch_ws_message(
    msg: dict[str, Any],
    assembler: StreamAssembler,
    width: int,
    output_put: Callable[[str], None],
    last_output_count: list[int],
    header_state: Optional[dict[str, str]] = None,
    ui_state: Optional[dict[str, str]] = None,
) -> None:
    """Dispatch one WebSocket message to StreamAssembler and optionally output (on agent_complete)."""
    typ = msg.get("type")
    if ui_state is not None:
        if typ == "text_delta":
            ui_state["phase"] = "streaming"
        elif typ == "tool_call_start":
            ui_state["phase"] = "tool_running"
        elif typ == "agent_complete":
            ui_state["phase"] = "idle"
        elif typ == "agent_error":
            ui_state["phase"] = "error"
    if typ == "text_delta":
        assembler.text_delta(msg.get("delta", ""))
    elif typ == "thinking_delta":
        assembler.thinking_delta(msg.get("delta", ""))
    elif typ == "tool_call_start":
        assembler.tool_call_start(
            msg.get("tool_name", "unknown"),
            msg.get("arguments"),
        )
    elif typ == "tool_call_end":
        assembler.tool_call_end(
            msg.get("tool_name", "unknown"),
            result=msg.get("result"),
            error=msg.get("error"),
        )
    elif typ == "agent_complete":
        assembler.agent_complete()
        if assembler.messages:
            start = last_output_count[0]
            for m in assembler.messages[start:]:
                lines = render_messages([m], width)
                for line in lines:
                    output_put(line)
            last_output_count[0] = len(assembler.messages)
    elif typ == "agent_error":
        err = msg.get("error", "Unknown error")
        output_put(f"[system] Agent error: {err}")
    elif typ == "session_switched":
        sid = msg.get("session_id", "")
        if sid:
            if header_state is not None:
                header_state["session"] = sid
            output_put(f"[system] Switched to session {sid}")
    elif typ == "agent_switched":
        name = msg.get("agent_name", "")
        if name:
            if header_state is not None:
                header_state["agent"] = name
            output_put(f"[system] Switched to agent {name}")
    elif typ == "agent_aborted":
        assembler._buffer = ""
        assembler._thinking_buffer = ""
        assembler._current_tool = None
        output_put("[system] Aborted.")
    elif typ in ("ready", "agent_disconnected"):
        pass
    elif typ == "error":
        output_put(f"[system] Gateway error: {msg.get('error', 'Unknown')}")
    else:
        logger.debug("Unhandled WebSocket message type: %s", typ)


def _make_output_put(
    output_queue: Optional[queue.Queue],
    print_lock: Optional[threading.Lock] = None,
) -> Callable[[str], None]:
    """Return a callable that outputs one line: to queue or to stdout with lock."""
    if output_queue is not None:
        return output_queue.put
    lock = print_lock or threading.Lock()

    def _print_line(line: str) -> None:
        with lock:
            print(line, flush=True)

    return _print_line

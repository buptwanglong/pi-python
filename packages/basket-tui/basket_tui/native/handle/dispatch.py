"""
Message dispatch for terminal-native TUI: WebSocket message → StreamAssembler + output.
"""

import logging
from typing import Any, Callable, Optional

from ..pipeline.render import render_messages
from ..pipeline.stream import StreamAssembler

logger = logging.getLogger(__name__)


def handle_text_delta(
    assembler: StreamAssembler,
    delta: str,
    ui_state: Optional[dict[str, str]] = None,
) -> None:
    """Handle text_delta: set phase streaming, append to assembler buffer."""
    if ui_state is not None:
        ui_state["phase"] = "streaming"
    assembler.text_delta(delta)


def handle_thinking_delta(assembler: StreamAssembler, delta: str) -> None:
    """Handle thinking_delta: append to assembler thinking buffer."""
    assembler.thinking_delta(delta)


def handle_tool_call_start(
    assembler: StreamAssembler,
    tool_name: str,
    arguments: Optional[dict] = None,
    ui_state: Optional[dict[str, str]] = None,
) -> None:
    """Handle tool_call_start: set phase tool_running, record current tool."""
    if ui_state is not None:
        ui_state["phase"] = "tool_running"
    assembler.tool_call_start(tool_name, arguments)


def handle_tool_call_end(
    assembler: StreamAssembler,
    tool_name: str,
    result: Any = None,
    error: Optional[str] = None,
) -> None:
    """Handle tool_call_end: append tool message to assembler."""
    assembler.tool_call_end(tool_name, result=result, error=error)


def handle_agent_complete(
    assembler: StreamAssembler,
    width: int,
    output_put: Callable[[str], None],
    last_output_count: list[int],
    ui_state: Optional[dict[str, str]] = None,
) -> None:
    """Handle agent_complete: commit buffer, set phase idle, render new messages."""
    if ui_state is not None:
        ui_state["phase"] = "idle"
    assembler.agent_complete()
    if assembler.messages:
        start = last_output_count[0]
        for m in assembler.messages[start:]:
            lines = render_messages([m], width)
            for line in lines:
                output_put(line)
        last_output_count[0] = len(assembler.messages)


def handle_agent_error(
    output_put: Callable[[str], None],
    error: str,
    ui_state: Optional[dict[str, str]] = None,
) -> None:
    """Handle agent_error: set phase error, output system message."""
    if ui_state is not None:
        ui_state["phase"] = "error"
    output_put(f"[system] Agent error: {error}")


def handle_session_switched(
    header_state: Optional[dict[str, str]],
    output_put: Callable[[str], None],
    session_id: str,
) -> None:
    """Handle session_switched: update header_state and output when session_id non-empty."""
    if not session_id:
        return
    if header_state is not None:
        header_state["session"] = session_id
    output_put(f"[system] Switched to session {session_id}")


def handle_agent_switched(
    header_state: Optional[dict[str, str]],
    output_put: Callable[[str], None],
    agent_name: str,
) -> None:
    """Handle agent_switched: update header_state and output when agent_name non-empty."""
    if not agent_name:
        return
    if header_state is not None:
        header_state["agent"] = agent_name
    output_put(f"[system] Switched to agent {agent_name}")


def handle_agent_aborted(
    assembler: StreamAssembler,
    output_put: Callable[[str], None],
) -> None:
    """Handle agent_aborted: clear assembler buffers and current tool, output message."""
    assembler._buffer = ""
    assembler._thinking_buffer = ""
    assembler._current_tool = None
    output_put("[system] Aborted.")


def handle_system(
    event: str,
    payload: dict[str, Any],
    output_put: Callable[[str], None],
) -> None:
    """Handle system events: ready, agent_disconnected (no-op), error (output gateway error)."""
    if event == "error":
        output_put(f"[system] Gateway error: {payload.get('error', 'Unknown')}")
    # ready, agent_disconnected: no-op


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
    if typ == "text_delta":
        handle_text_delta(assembler, msg.get("delta", ""), ui_state=ui_state)
    elif typ == "thinking_delta":
        handle_thinking_delta(assembler, msg.get("delta", ""))
    elif typ == "tool_call_start":
        handle_tool_call_start(
            assembler,
            msg.get("tool_name", "unknown"),
            arguments=msg.get("arguments"),
            ui_state=ui_state,
        )
    elif typ == "tool_call_end":
        handle_tool_call_end(
            assembler,
            msg.get("tool_name", "unknown"),
            result=msg.get("result"),
            error=msg.get("error"),
        )
    elif typ == "agent_complete":
        handle_agent_complete(
            assembler, width, output_put, last_output_count, ui_state=ui_state
        )
    elif typ == "agent_error":
        handle_agent_error(
            output_put, msg.get("error", "Unknown error"), ui_state=ui_state
        )
    elif typ == "session_switched":
        handle_session_switched(
            header_state, output_put, msg.get("session_id", "")
        )
    elif typ == "agent_switched":
        handle_agent_switched(
            header_state, output_put, msg.get("agent_name", "")
        )
    elif typ == "agent_aborted":
        handle_agent_aborted(assembler, output_put)
    elif typ in ("ready", "agent_disconnected"):
        handle_system(typ, msg, output_put)
    elif typ == "error":
        handle_system(typ, msg, output_put)
    else:
        logger.debug("Unhandled WebSocket message type: %s", typ)

"""
Message dispatch for terminal-native TUI: WebSocket message → StreamAssembler + output.
"""

import logging
from typing import Any, Callable, Optional

from basket_protocol import (
    AgentAborted,
    AgentComplete,
    AgentError,
    AgentSwitched,
    SessionSwitched,
    System,
    TextDelta,
    ThinkingDelta,
    ToolCallEnd,
    ToolCallStart,
    Unknown,
    parse_inbound,
)

from ..pipeline.render import render_messages
from ..pipeline.stream import StreamAssembler

logger = logging.getLogger(__name__)


def _render_and_output(
    msg: dict[str, Any],
    width: int,
    output_put: Callable[[str], None],
) -> None:
    """Render a single message and output it with a trailing blank-line separator."""
    lines = render_messages([msg], width)
    if not lines:
        return
    for line in lines:
        output_put(line)
    # Add blank line separator so consecutive blocks don't appear glued together.
    # render_messages strips trailing newlines via rstrip, so we must add spacing here.
    output_put("")


def handle_text_delta(
    assembler: StreamAssembler,
    delta: str,
    ui_state: Optional[dict[str, str]] = None,
    on_streaming_update: Optional[Callable[[], None]] = None,
) -> None:
    """Handle text_delta: set phase streaming, append to assembler buffer."""
    if ui_state is not None:
        ui_state["phase"] = "streaming"
    assembler.text_delta(delta)
    if on_streaming_update is not None:
        on_streaming_update()
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "Text delta processed",
            extra={
                "delta_len": len(delta),
                "buffer_size": len(assembler._buffer),
                "phase": ui_state.get("phase") if ui_state else None,
            },
        )


def handle_thinking_delta(assembler: StreamAssembler, delta: str) -> None:
    """Handle thinking_delta: append to assembler thinking buffer."""
    assembler.thinking_delta(delta)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "Thinking delta processed",
            extra={
                "delta_len": len(delta),
                "thinking_size": len(assembler._thinking_buffer),
            },
        )


def handle_tool_call_start(
    assembler: StreamAssembler,
    tool_name: str,
    arguments: Optional[dict] = None,
    ui_state: Optional[dict[str, str]] = None,
    width: int = 80,
    output_put: Optional[Callable[[str], None]] = None,
    last_output_count: Optional[list[int]] = None,
) -> None:
    """Handle tool_call_start: flush buffer, set phase tool_running, record current tool."""
    # Flush streaming buffer BEFORE tool starts so text appears before tool block
    if output_put is not None and last_output_count is not None:
        if assembler.flush_buffer():
            _render_and_output(assembler.messages[-1], width, output_put)
            last_output_count[0] = len(assembler.messages)

    if ui_state is not None:
        ui_state["phase"] = "tool_running"
    assembler.tool_call_start(tool_name, arguments)
    logger.info(
        "Tool call started",
        extra={
            "tool_name": tool_name,
            "args_keys": list(arguments.keys()) if arguments else [],
            "phase": "tool_running",
        },
    )


def handle_tool_call_end(
    assembler: StreamAssembler,
    tool_name: str,
    result: Any = None,
    error: Optional[str] = None,
    width: int = 80,
    output_put: Optional[Callable[[str], None]] = None,
    last_output_count: Optional[list[int]] = None,
) -> None:
    """Handle tool_call_end: append tool message and render immediately."""
    assembler.tool_call_end(tool_name, result=result, error=error)

    # Render tool block immediately instead of waiting for agent_complete
    if output_put is not None and last_output_count is not None:
        _render_and_output(assembler.messages[-1], width, output_put)
        last_output_count[0] = len(assembler.messages)

    logger.info(
        "Tool call ended",
        extra={
            "tool_name": tool_name,
            "has_result": result is not None,
            "has_error": error is not None,
        },
    )


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

    new_messages = len(assembler.messages) - last_output_count[0]
    logger.info(
        "Agent turn complete",
        extra={
            "new_messages": new_messages,
            "total_messages": len(assembler.messages),
            "phase": "idle",
        },
    )

    if assembler.messages:
        start = last_output_count[0]
        for m in assembler.messages[start:]:
            _render_and_output(m, width, output_put)
        last_output_count[0] = len(assembler.messages)


def handle_agent_error(
    output_put: Callable[[str], None],
    error: str,
    ui_state: Optional[dict[str, str]] = None,
) -> None:
    """Handle agent_error: set phase error, output system message."""
    if ui_state is not None:
        ui_state["phase"] = "error"
    logger.error("Agent error occurred", extra={"error": error, "phase": "error"})
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
    logger.info("Session switched", extra={"session_id": session_id})
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
    logger.info("Agent switched", extra={"agent_name": agent_name})
    output_put(f"[system] Switched to agent {agent_name}")


def handle_agent_aborted(
    assembler: StreamAssembler,
    output_put: Callable[[str], None],
) -> None:
    """Handle agent_aborted: clear assembler buffers and current tool, output message."""
    logger.info("Agent aborted", extra={})
    assembler.abort()
    output_put("[system] Aborted.")


def handle_system(
    event: str,
    payload: dict[str, Any],
    output_put: Callable[[str], None],
) -> None:
    """Handle system events: ready, agent_disconnected (no-op), error (output gateway error)."""
    logger.info(
        "System event received",
        extra={"event": event, "payload_keys": list(payload.keys()) if payload else []},
    )
    if event == "error":
        output_put(f"[system] Gateway error: {payload.get('error', 'Unknown')}")
    # ready, agent_disconnected: no-op


def handle_todo_update(
    todo_state: list[dict[str, Any]],
    todos: list[dict[str, Any]],
) -> None:
    """Handle todo_update: replace todo_state with new snapshot."""
    todo_state.clear()
    todo_state.extend(todos)
    logger.info("Todo state updated", extra={"count": len(todos)})


def _dispatch_ws_message(
    msg: dict[str, Any],
    assembler: StreamAssembler,
    width: int,
    output_put: Callable[[str], None],
    last_output_count: list[int],
    header_state: Optional[dict[str, str]] = None,
    ui_state: Optional[dict[str, str]] = None,
) -> None:
    """Dispatch one WebSocket message (dict) to StreamAssembler after parsing to typed message."""
    parsed = parse_inbound(msg)
    if isinstance(parsed, Unknown):
        logger.debug("Unhandled WebSocket message type: %s", parsed.type)
        return
    if isinstance(parsed, TextDelta):
        handle_text_delta(assembler, parsed.delta, ui_state=ui_state)
    elif isinstance(parsed, ThinkingDelta):
        handle_thinking_delta(assembler, parsed.delta)
    elif isinstance(parsed, ToolCallStart):
        handle_tool_call_start(
            assembler,
            parsed.tool_name,
            arguments=parsed.arguments,
            ui_state=ui_state,
            width=width,
            output_put=output_put,
            last_output_count=last_output_count,
        )
    elif isinstance(parsed, ToolCallEnd):
        handle_tool_call_end(
            assembler,
            parsed.tool_name,
            result=parsed.result,
            error=parsed.error,
            width=width,
            output_put=output_put,
            last_output_count=last_output_count,
        )
    elif isinstance(parsed, AgentComplete):
        handle_agent_complete(
            assembler, width, output_put, last_output_count, ui_state=ui_state
        )
    elif isinstance(parsed, AgentError):
        handle_agent_error(output_put, parsed.error, ui_state=ui_state)
    elif isinstance(parsed, SessionSwitched):
        handle_session_switched(
            header_state, output_put, parsed.session_id
        )
    elif isinstance(parsed, AgentSwitched):
        handle_agent_switched(
            header_state, output_put, parsed.agent_name
        )
    elif isinstance(parsed, AgentAborted):
        handle_agent_aborted(assembler, output_put)
    elif isinstance(parsed, System):
        handle_system(parsed.event, parsed.payload or {}, output_put)
    else:
        logger.debug("Unhandled WebSocket message type: %s", type(parsed).__name__)

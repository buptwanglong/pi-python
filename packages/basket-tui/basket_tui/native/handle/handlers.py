"""
Gateway handler factory: build GatewayHandlers that delegate to dispatch handle_*.
"""

import logging
from typing import Callable, Optional

from ..connection.types import GatewayHandlers
from ..pipeline.stream import StreamAssembler
from .dispatch import (
    handle_agent_aborted,
    handle_agent_complete,
    handle_agent_error,
    handle_agent_switched,
    handle_session_switched,
    handle_system,
    handle_text_delta,
    handle_thinking_delta,
    handle_tool_call_end,
    handle_tool_call_start,
)

logger = logging.getLogger(__name__)


def make_handlers(
    assembler: StreamAssembler,
    width: int,
    output_put: Callable[[str], None],
    last_output_count: list[int],
    header_state: Optional[dict[str, str]] = None,
    ui_state: Optional[dict[str, str]] = None,
    on_streaming_update: Optional[Callable[[], None]] = None,
) -> GatewayHandlers:
    """Build GatewayHandlers that delegate to dispatch handle_* with closed-over state."""
    handlers: GatewayHandlers = {
        "on_text_delta": lambda event: handle_text_delta(
            assembler,
            event.delta,
            ui_state=ui_state,
            on_streaming_update=on_streaming_update,
        ),
        "on_thinking_delta": lambda event: handle_thinking_delta(assembler, event.delta),
        "on_tool_call_start": lambda event: handle_tool_call_start(
            assembler,
            event.tool_name,
            arguments=event.arguments,
            ui_state=ui_state,
            width=width,
            output_put=output_put,
            last_output_count=last_output_count,
        ),
        "on_tool_call_end": lambda event: handle_tool_call_end(
            assembler,
            event.tool_name,
            result=event.result,
            error=event.error,
            width=width,
            output_put=output_put,
            last_output_count=last_output_count,
        ),
        "on_agent_complete": lambda event: handle_agent_complete(
            assembler, width, output_put, last_output_count, ui_state=ui_state
        ),
        "on_agent_error": lambda event: handle_agent_error(
            output_put, event.error, ui_state=ui_state
        ),
        "on_session_switched": lambda event: handle_session_switched(
            header_state, output_put, event.session_id
        ),
        "on_agent_switched": lambda event: handle_agent_switched(
            header_state, output_put, event.agent_name
        ),
        "on_agent_aborted": lambda event: handle_agent_aborted(assembler, output_put),
        "on_system": lambda event: handle_system(
            event.event, event.payload or {}, output_put
        ),
    }

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Handler mapping created", extra={"handler_count": len(handlers)})

    return handlers

"""Logging-only event handlers for LLM turns and tool calls."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from basket_agent.types import (
    AgentEventToolCallStart,
    AgentEventToolCallEnd,
    AgentEventTurnStart,
    AgentEventTurnEnd,
)

from ._event_handlers import _tool_call_args_summary

if TYPE_CHECKING:
    from ._protocol import AssistantAgentProtocol

logger = logging.getLogger(__name__)


def setup_logging_handlers(agent: AssistantAgentProtocol) -> None:
    """
    Register handlers that only write INFO logs for LLM turns and tool calls.
    Shared by CLI and TUI; same events drive both logging and display responses.
    """
    basket_agent = agent.agent if hasattr(agent, "agent") else agent

    def on_turn_start(event: AgentEventTurnStart) -> None:
        logger.info(
            "LLM turn started, turn_number=%s",
            event.turn_number,
        )

    def on_turn_end(event: AgentEventTurnEnd) -> None:
        logger.info(
            "LLM turn ended, turn_number=%s, has_tool_calls=%s",
            event.turn_number,
            event.has_tool_calls,
        )

    def on_tool_call_start_log(event: AgentEventToolCallStart) -> None:
        tool_name = event.tool_name
        args = event.arguments or {}
        summary = _tool_call_args_summary(tool_name, args)
        if summary:
            logger.info("Tool call start: %s %s", tool_name, summary)
        else:
            logger.info("Tool call start: %s", tool_name)

    def on_tool_call_end_log(event: AgentEventToolCallEnd) -> None:
        tool_name = event.tool_name
        err = event.error
        logger.info("Tool call end: %s error=%s", tool_name, bool(err))

    basket_agent.on("agent_turn_start", on_turn_start)
    basket_agent.on("agent_turn_end", on_turn_end)
    basket_agent.on("agent_tool_call_start", on_tool_call_start_log)
    basket_agent.on("agent_tool_call_end", on_tool_call_end_log)

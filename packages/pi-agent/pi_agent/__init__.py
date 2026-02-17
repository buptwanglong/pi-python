"""
Pi-Agent: Stateful agent runtime with tool execution.

This package provides a high-level agent abstraction for building
AI agents with tool calling capabilities.
"""

from .agent import Agent
from .agent_loop import AgentLoopError, run_agent_loop, run_agent_turn
from .types import (
    AgentEvent,
    AgentEventComplete,
    AgentEventError,
    AgentEventToolCallEnd,
    AgentEventToolCallStart,
    AgentEventTurnEnd,
    AgentEventTurnStart,
    AgentState,
    AgentTool,
    FollowUpMessage,
    SteeringMessage,
    ToolExecutor,
)

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "AgentLoopError",
    "run_agent_loop",
    "run_agent_turn",
    "AgentEvent",
    "AgentEventComplete",
    "AgentEventError",
    "AgentEventToolCallEnd",
    "AgentEventToolCallStart",
    "AgentEventTurnEnd",
    "AgentEventTurnStart",
    "AgentState",
    "AgentTool",
    "FollowUpMessage",
    "SteeringMessage",
    "ToolExecutor",
]

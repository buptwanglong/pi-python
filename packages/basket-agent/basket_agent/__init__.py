"""
Pi-Agent: Stateful agent runtime with tool execution.

This package provides a high-level agent abstraction for building
AI agents with tool calling capabilities.
"""

from .agent import Agent
from .agent_loop import AgentLoopError, run_agent_loop, run_agent_turn
from .blackboard import Blackboard, BlackboardEntry
from .context_manager import compact_context, estimate_context_tokens
from .event_bus import (
    AgentEventBus,
    CrossAgentEvent,
    EVENT_COMPLETION,
    EVENT_ERROR,
    EVENT_FINDING,
    EVENT_PROGRESS,
    EVENT_REQUEST,
)
from .retry import RetryPolicy, execute_with_retry, is_retryable_error
from .tool_filter import (
    ALWAYS_INCLUDE,
    DEFAULT_RULES,
    ToolFilterRule,
    create_filtered_context,
    filter_tools,
)
from .types import (
    AgentEvent,
    AgentEventComplete,
    AgentEventContextCompacted,
    AgentEventError,
    AgentEventToolCallEnd,
    AgentEventToolCallStart,
    AgentEventToolRetry,
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
    # Blackboard
    "Blackboard",
    "BlackboardEntry",
    # Context Manager
    "compact_context",
    "estimate_context_tokens",
    # Event Bus
    "AgentEventBus",
    "CrossAgentEvent",
    "EVENT_COMPLETION",
    "EVENT_ERROR",
    "EVENT_FINDING",
    "EVENT_PROGRESS",
    "EVENT_REQUEST",
    # Retry
    "RetryPolicy",
    "execute_with_retry",
    "is_retryable_error",
    # Tool Filter
    "ALWAYS_INCLUDE",
    "DEFAULT_RULES",
    "ToolFilterRule",
    "create_filtered_context",
    "filter_tools",
    # Types
    "AgentEvent",
    "AgentEventComplete",
    "AgentEventContextCompacted",
    "AgentEventError",
    "AgentEventToolCallEnd",
    "AgentEventToolCallStart",
    "AgentEventToolRetry",
    "AgentEventTurnEnd",
    "AgentEventTurnStart",
    "AgentState",
    "AgentTool",
    "FollowUpMessage",
    "SteeringMessage",
    "ToolExecutor",
]

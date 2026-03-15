"""Gateway WebSocket wire protocol: inbound/outbound message types and (de)serialization."""

from .inbound import (
    AgentAborted,
    AgentComplete,
    AgentError,
    AgentSwitched,
    InboundMessage,
    SessionSwitched,
    System,
    TextDelta,
    ThinkingDelta,
    ToolCallEnd,
    ToolCallStart,
    Unknown,
    parse_inbound,
)

__all__ = [
    "AgentAborted",
    "AgentComplete",
    "AgentError",
    "AgentSwitched",
    "InboundMessage",
    "SessionSwitched",
    "System",
    "TextDelta",
    "ThinkingDelta",
    "ToolCallEnd",
    "ToolCallStart",
    "Unknown",
    "parse_inbound",
]

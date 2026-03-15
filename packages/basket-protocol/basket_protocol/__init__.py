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
from .outbound import (
    Abort,
    Message,
    NewSession,
    OutboundMessage,
    SwitchAgent,
    SwitchSession,
    serialize_outbound,
)

__all__ = [
    "Abort",
    "AgentAborted",
    "AgentComplete",
    "AgentError",
    "AgentSwitched",
    "InboundMessage",
    "Message",
    "NewSession",
    "OutboundMessage",
    "SessionSwitched",
    "SwitchAgent",
    "SwitchSession",
    "System",
    "TextDelta",
    "ThinkingDelta",
    "ToolCallEnd",
    "ToolCallStart",
    "Unknown",
    "parse_inbound",
    "serialize_outbound",
]

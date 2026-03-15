"""Inbound WebSocket message types (server → client) and parsing."""

from dataclasses import dataclass
from typing import Any, Union


@dataclass(frozen=True)
class TextDelta:
    """Streamed text chunk from the agent."""

    delta: str = ""


@dataclass(frozen=True)
class ThinkingDelta:
    """Streamed thinking chunk from the agent."""

    delta: str = ""


@dataclass(frozen=True)
class ToolCallStart:
    """Tool call started."""

    tool_name: str = "unknown"
    arguments: dict[str, Any] | None = None


@dataclass(frozen=True)
class ToolCallEnd:
    """Tool call finished."""

    tool_name: str = "unknown"
    result: Any = None
    error: str | None = None


@dataclass(frozen=True)
class AgentComplete:
    """Agent run completed."""


@dataclass(frozen=True)
class AgentError:
    """Agent run error."""

    error: str = "Unknown error"


@dataclass(frozen=True)
class SessionSwitched:
    """Session was switched."""

    session_id: str = ""


@dataclass(frozen=True)
class AgentSwitched:
    """Agent was switched."""

    agent_name: str = ""


@dataclass(frozen=True)
class AgentAborted:
    """Agent was aborted."""


@dataclass(frozen=True)
class System:
    """System event (ready, agent_disconnected, error, reconnected)."""

    event: str = ""
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class Unknown:
    """Unknown message type (parse but do not handle)."""

    type: str = ""
    payload: dict[str, Any] | None = None


InboundMessage = Union[
    TextDelta,
    ThinkingDelta,
    ToolCallStart,
    ToolCallEnd,
    AgentComplete,
    AgentError,
    SessionSwitched,
    AgentSwitched,
    AgentAborted,
    System,
    Unknown,
]


def parse_inbound(data: dict[str, Any]) -> InboundMessage:
    """Parse a JSON-like dict into a typed inbound message.

    Unknown or missing \"type\" yields Unknown(type, payload).
    """
    typ = data.get("type")
    if not typ or not isinstance(typ, str):
        return Unknown(type="", payload=data)

    if typ == "text_delta":
        return TextDelta(delta=data.get("delta", "") or "")
    if typ == "thinking_delta":
        return ThinkingDelta(delta=data.get("delta", "") or "")
    if typ == "tool_call_start":
        return ToolCallStart(
            tool_name=data.get("tool_name", "unknown") or "unknown",
            arguments=data.get("arguments"),
        )
    if typ == "tool_call_end":
        return ToolCallEnd(
            tool_name=data.get("tool_name", "unknown") or "unknown",
            result=data.get("result"),
            error=data.get("error"),
        )
    if typ == "agent_complete":
        return AgentComplete()
    if typ == "agent_error":
        return AgentError(error=data.get("error", "Unknown error") or "Unknown error")
    if typ == "session_switched":
        return SessionSwitched(session_id=data.get("session_id", "") or "")
    if typ == "agent_switched":
        return AgentSwitched(agent_name=data.get("agent_name", "") or "")
    if typ == "agent_aborted":
        return AgentAborted()
    if typ in ("ready", "agent_disconnected", "reconnected", "error"):
        return System(event=typ, payload=data)

    return Unknown(type=typ, payload=data)

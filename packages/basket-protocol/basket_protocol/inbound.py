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
class TodoUpdate:
    """Todo list snapshot (full replacement)."""

    todos: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class AskUserQuestion:
    """Ask user a question with optional choices."""

    tool_call_id: str = ""
    question: str = ""
    options: tuple[str, ...] = ()


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
    TodoUpdate,
    AskUserQuestion,
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
    if typ == "todos":
        raw_todos = data.get("todos") or []
        return TodoUpdate(todos=tuple(raw_todos))

    if typ == "ask_user_question":
        raw_options = data.get("options") or []
        return AskUserQuestion(
            tool_call_id=data.get("tool_call_id", "") or "",
            question=data.get("question", "") or "",
            options=tuple(raw_options),
        )

    return Unknown(type=typ, payload=data)


def inbound_to_dict(msg: InboundMessage) -> dict[str, Any]:
    """Serialize an inbound (server→client) message to wire-format dict for sending."""
    if isinstance(msg, TextDelta):
        return {"type": "text_delta", "delta": msg.delta}
    if isinstance(msg, ThinkingDelta):
        return {"type": "thinking_delta", "delta": msg.delta}
    if isinstance(msg, ToolCallStart):
        out: dict[str, Any] = {"type": "tool_call_start", "tool_name": msg.tool_name}
        if msg.arguments is not None:
            out["arguments"] = msg.arguments
        return out
    if isinstance(msg, ToolCallEnd):
        out = {"type": "tool_call_end", "tool_name": msg.tool_name}
        if msg.result is not None:
            out["result"] = msg.result
        if msg.error is not None:
            out["error"] = msg.error
        return out
    if isinstance(msg, AgentComplete):
        return {"type": "agent_complete"}
    if isinstance(msg, AgentError):
        return {"type": "agent_error", "error": msg.error}
    if isinstance(msg, SessionSwitched):
        return {"type": "session_switched", "session_id": msg.session_id}
    if isinstance(msg, AgentSwitched):
        return {"type": "agent_switched", "agent_name": msg.agent_name}
    if isinstance(msg, AgentAborted):
        return {"type": "agent_aborted"}
    if isinstance(msg, System):
        return {"type": msg.event, **(msg.payload or {})}
    if isinstance(msg, TodoUpdate):
        return {"type": "todos", "todos": list(msg.todos)}
    if isinstance(msg, AskUserQuestion):
        return {
            "type": "ask_user_question",
            "tool_call_id": msg.tool_call_id,
            "question": msg.question,
            "options": list(msg.options),
        }
    if isinstance(msg, Unknown):
        return dict(msg.payload) if msg.payload else {"type": msg.type}
    raise TypeError(f"Unknown inbound message type: {type(msg)}")

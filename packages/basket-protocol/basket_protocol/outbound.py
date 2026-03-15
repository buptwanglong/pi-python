"""Outbound WebSocket message types (client → server) and serialization."""

import json
from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class Message:
    """User message to send to the agent."""

    content: str = ""


@dataclass(frozen=True)
class Abort:
    """Abort the current agent run."""


@dataclass(frozen=True)
class NewSession:
    """Start a new session."""


@dataclass(frozen=True)
class SwitchSession:
    """Switch to another session."""

    session_id: str = ""


@dataclass(frozen=True)
class SwitchAgent:
    """Switch to another agent."""

    agent_name: str = ""


OutboundMessage = Union[Message, Abort, NewSession, SwitchSession, SwitchAgent]


def serialize_outbound(msg: OutboundMessage) -> str:
    """Serialize an outbound message to JSON wire format."""
    if isinstance(msg, Message):
        return json.dumps({"type": "message", "content": msg.content})
    if isinstance(msg, Abort):
        return json.dumps({"type": "abort"})
    if isinstance(msg, NewSession):
        return json.dumps({"type": "new_session"})
    if isinstance(msg, SwitchSession):
        return json.dumps({"type": "switch_session", "session_id": msg.session_id})
    if isinstance(msg, SwitchAgent):
        return json.dumps({"type": "switch_agent", "agent_name": msg.agent_name})
    raise TypeError(f"Unknown outbound message type: {type(msg)}")

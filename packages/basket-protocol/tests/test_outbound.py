"""Tests for outbound message types and serialize_outbound."""

import json

from basket_protocol import (
    Abort,
    Message,
    NewSession,
    SwitchAgent,
    SwitchSession,
    serialize_outbound,
)


def test_serialize_message() -> None:
    """serialize_outbound(Message(content='hi')) returns JSON with type 'message' and content 'hi'."""
    s = serialize_outbound(Message(content="hi"))
    data = json.loads(s)
    assert data["type"] == "message"
    assert data["content"] == "hi"


def test_serialize_abort() -> None:
    """serialize_outbound(Abort()) returns JSON with type 'abort'."""
    s = serialize_outbound(Abort())
    data = json.loads(s)
    assert data["type"] == "abort"


def test_serialize_new_session() -> None:
    """serialize_outbound(NewSession()) returns JSON with type 'new_session'."""
    s = serialize_outbound(NewSession())
    data = json.loads(s)
    assert data["type"] == "new_session"


def test_serialize_switch_session() -> None:
    """serialize_outbound(SwitchSession(session_id='s1')) returns type 'switch_session', session_id 's1'."""
    s = serialize_outbound(SwitchSession(session_id="s1"))
    data = json.loads(s)
    assert data["type"] == "switch_session"
    assert data["session_id"] == "s1"


def test_serialize_switch_agent() -> None:
    """serialize_outbound(SwitchAgent(agent_name='a1')) returns type 'switch_agent', agent_name 'a1'."""
    s = serialize_outbound(SwitchAgent(agent_name="a1"))
    data = json.loads(s)
    assert data["type"] == "switch_agent"
    assert data["agent_name"] == "a1"

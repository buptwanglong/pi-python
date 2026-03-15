"""Tests for inbound message types and parse_inbound."""

from basket_protocol import (
    AgentAborted,
    AgentComplete,
    AgentError,
    AgentSwitched,
    SessionSwitched,
    System,
    TextDelta,
    ThinkingDelta,
    ToolCallEnd,
    ToolCallStart,
    Unknown,
    inbound_to_dict,
    parse_inbound,
)


def test_parse_inbound_text_delta() -> None:
    """parse_inbound({'type': 'text_delta', 'delta': 'hi'}) returns TextDelta(delta='hi')."""
    msg = parse_inbound({"type": "text_delta", "delta": "hi"})
    assert isinstance(msg, TextDelta)
    assert msg.delta == "hi"


def test_parse_inbound_thinking_delta() -> None:
    """parse_inbound({'type': 'thinking_delta', 'delta': 'x'}) returns ThinkingDelta(delta='x')."""
    msg = parse_inbound({"type": "thinking_delta", "delta": "x"})
    assert isinstance(msg, ThinkingDelta)
    assert msg.delta == "x"


def test_parse_inbound_tool_call_start() -> None:
    """parse_inbound tool_call_start returns ToolCallStart with tool_name and arguments."""
    msg = parse_inbound(
        {"type": "tool_call_start", "tool_name": "read", "arguments": {"path": "a"}}
    )
    assert isinstance(msg, ToolCallStart)
    assert msg.tool_name == "read"
    assert msg.arguments == {"path": "a"}


def test_parse_inbound_tool_call_end() -> None:
    """parse_inbound tool_call_end returns ToolCallEnd with tool_name, result, error=None."""
    msg = parse_inbound(
        {"type": "tool_call_end", "tool_name": "read", "result": "ok"}
    )
    assert isinstance(msg, ToolCallEnd)
    assert msg.tool_name == "read"
    assert msg.result == "ok"
    assert msg.error is None


def test_parse_inbound_agent_complete() -> None:
    """parse_inbound agent_complete returns AgentComplete()."""
    msg = parse_inbound({"type": "agent_complete"})
    assert isinstance(msg, AgentComplete)


def test_parse_inbound_agent_error() -> None:
    """parse_inbound agent_error returns AgentError(error='err')."""
    msg = parse_inbound({"type": "agent_error", "error": "err"})
    assert isinstance(msg, AgentError)
    assert msg.error == "err"


def test_parse_inbound_session_switched() -> None:
    """parse_inbound session_switched returns SessionSwitched(session_id='s1')."""
    msg = parse_inbound({"type": "session_switched", "session_id": "s1"})
    assert isinstance(msg, SessionSwitched)
    assert msg.session_id == "s1"


def test_parse_inbound_agent_switched() -> None:
    """parse_inbound agent_switched returns AgentSwitched(agent_name='a1')."""
    msg = parse_inbound({"type": "agent_switched", "agent_name": "a1"})
    assert isinstance(msg, AgentSwitched)
    assert msg.agent_name == "a1"


def test_parse_inbound_agent_aborted() -> None:
    """parse_inbound agent_aborted returns AgentAborted()."""
    msg = parse_inbound({"type": "agent_aborted"})
    assert isinstance(msg, AgentAborted)


def test_parse_inbound_ready() -> None:
    """parse_inbound ready returns System(event='ready', payload=...)."""
    msg = parse_inbound({"type": "ready"})
    assert isinstance(msg, System)
    assert msg.event == "ready"
    assert msg.payload == {"type": "ready"}


def test_parse_inbound_agent_disconnected() -> None:
    """parse_inbound agent_disconnected returns System(event='agent_disconnected', ...)."""
    msg = parse_inbound({"type": "agent_disconnected"})
    assert isinstance(msg, System)
    assert msg.event == "agent_disconnected"
    assert msg.payload == {"type": "agent_disconnected"}


def test_parse_inbound_error() -> None:
    """parse_inbound error returns System(event='error', ...)."""
    msg = parse_inbound({"type": "error", "error": "x"})
    assert isinstance(msg, System)
    assert msg.event == "error"
    assert msg.payload == {"type": "error", "error": "x"}


def test_parse_inbound_unknown_type() -> None:
    """Unknown type returns Unknown(type=..., payload=...)."""
    msg = parse_inbound({"type": "unknown"})
    assert isinstance(msg, Unknown)
    assert msg.type == "unknown"
    assert msg.payload == {"type": "unknown"}


def test_inbound_to_dict_text_delta_roundtrip() -> None:
    """inbound_to_dict(TextDelta(delta='hi')) returns wire dict; parse_inbound roundtrips."""
    msg = TextDelta(delta="hi")
    d = inbound_to_dict(msg)
    assert d == {"type": "text_delta", "delta": "hi"}
    assert parse_inbound(d) == msg

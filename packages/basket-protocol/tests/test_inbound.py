"""Tests for inbound message types and parse_inbound."""

import pytest

from basket_protocol import (
    AgentAborted,
    AgentComplete,
    AgentError,
    AgentSwitched,
    SessionSwitched,
    TextDelta,
    ThinkingDelta,
    ToolCallEnd,
    ToolCallStart,
    Unknown,
    parse_inbound,
)


def test_parse_inbound_text_delta() -> None:
    """parse_inbound({'type': 'text_delta', 'delta': 'hi'}) returns TextDelta(delta='hi')."""
    msg = parse_inbound({"type": "text_delta", "delta": "hi"})
    assert isinstance(msg, TextDelta)
    assert msg.delta == "hi"


def test_parse_inbound_unknown_type() -> None:
    """Unknown type returns Unknown(type=..., payload=...)."""
    msg = parse_inbound({"type": "unknown"})
    assert isinstance(msg, Unknown)
    assert msg.type == "unknown"
    assert msg.payload == {"type": "unknown"}

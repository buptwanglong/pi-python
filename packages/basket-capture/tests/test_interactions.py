"""Tests for basket_capture.interactions (interaction detector)."""

from pathlib import Path

import pytest

from basket_capture.cast import parse_cast
from basket_capture.interactions import detect_interactions


def test_detect_returns_list_of_events() -> None:
    """detect_interactions(parsed) returns a list; if non-empty, each item has timestamp and type."""
    path = Path(__file__).parent / "fixtures" / "sample.cast"
    parsed = parse_cast(path)
    result = detect_interactions(parsed)
    assert isinstance(result, list)
    for item in result:
        assert hasattr(item, "timestamp")
        assert hasattr(item, "type")


def test_detect_with_mock_events_returns_interactions() -> None:
    """When CastResult has non-empty events, detect_interactions maps them to Interaction with timestamp and type."""
    from basket_capture.cast import CastResult

    parsed = CastResult(
        frames=[],
        events=[{"timestamp": 1.5, "type": "send", "payload": "hello"}],
        width=80,
        height=24,
    )
    result = detect_interactions(parsed)
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].timestamp == 1.5
    assert result[0].type == "send"

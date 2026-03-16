"""Tests for basket_capture.cast (asciinema v2 cast parser)."""

from pathlib import Path

import pytest

from basket_capture.cast import parse_cast


def test_parse_cast_returns_frames_and_events() -> None:
    """parse_cast(path) returns a result with frames (list) and events (list)."""
    path = Path(__file__).parent / "fixtures" / "sample.cast"
    result = parse_cast(path)
    assert hasattr(result, "frames")
    assert isinstance(result.frames, list)
    assert hasattr(result, "events")
    assert isinstance(result.events, list)


def test_parse_cast_invalid_file_raises() -> None:
    """parse_cast(non-existent path) raises FileNotFoundError."""
    path = Path(__file__).parent / "fixtures" / "nonexistent.cast"
    with pytest.raises(FileNotFoundError):
        parse_cast(path)

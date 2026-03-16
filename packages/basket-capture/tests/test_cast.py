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


def test_parse_cast_invalid_json_raises_value_error(tmp_path: Path) -> None:
    """parse_cast(corrupted or invalid JSON) raises ValueError with clear message."""
    bad = tmp_path / "bad.cast"
    bad.write_text("not valid json {", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_cast(bad)


def test_parse_cast_root_not_object_raises_value_error(tmp_path: Path) -> None:
    """parse_cast(JSON array or non-object root) raises ValueError."""
    bad = tmp_path / "bad.cast"
    bad.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError, match="root must be a JSON object"):
        parse_cast(bad)


def test_parse_cast_stdout_not_list_raises_value_error(tmp_path: Path) -> None:
    """parse_cast(cast with stdout not a list) raises ValueError."""
    bad = tmp_path / "bad.cast"
    bad.write_text('{"version": 2, "width": 80, "height": 24, "stdout": "oops"}', encoding="utf-8")
    with pytest.raises(ValueError, match="stdout.*must be a list"):
        parse_cast(bad)

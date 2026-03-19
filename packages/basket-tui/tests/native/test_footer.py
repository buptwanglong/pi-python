"""Tests for native TUI footer formatting."""

import re

import pytest

from basket_tui.native.ui.footer import (
    SPINNER_FRAMES,
    format_footer,
    spinner_frame,
)


def _strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m|\x1b\]8;;.*?\x1b\\", "", s)


def test_spinner_frame_cycles():
    """Spinner index wraps modulo frame count."""
    n = len(SPINNER_FRAMES)
    assert n >= 1
    assert spinner_frame(0) == SPINNER_FRAMES[0]
    assert spinner_frame(n) == SPINNER_FRAMES[0]
    assert spinner_frame(n + 1) == SPINNER_FRAMES[1]


@pytest.mark.parametrize(
    "phase,expected_label,has_timer",
    [
        ("tool_running", "running", True),
        ("streaming", "streaming", True),
        ("idle", "idle", False),
        ("error", "error", False),
    ],
)
def test_format_footer_phase_mapping(phase, expected_label, has_timer):
    """Internal phase maps to user-facing label and timer segment."""
    plain = _strip_ansi(
        format_footer(
            connection="connected",
            phase=phase,
            elapsed_s=7,
            spinner_index=0,
            exit_pending=False,
        )
    )
    assert expected_label in plain
    assert "connected" in plain
    if has_timer:
        assert "• 7s" in plain
        assert SPINNER_FRAMES[0] in plain
    else:
        assert "•" not in plain


def test_format_footer_tool_running_openclaw_shape():
    """tool_running shows spinner, running, elapsed, connection."""
    plain = _strip_ansi(
        format_footer(
            connection="connected",
            phase="tool_running",
            elapsed_s=3,
            spinner_index=2,
            exit_pending=False,
        )
    )
    assert "running" in plain
    assert "• 3s" in plain
    assert "connected" in plain
    assert spinner_frame(2) in plain


def test_format_footer_streaming():
    plain = _strip_ansi(
        format_footer(
            connection="connected",
            phase="streaming",
            elapsed_s=0,
            spinner_index=0,
            exit_pending=False,
        )
    )
    assert "streaming" in plain
    assert "• 0s" in plain


def test_format_footer_connecting_connection_string():
    """Connection text is passed through (e.g. connecting)."""
    plain = _strip_ansi(
        format_footer(
            connection="connecting",
            phase="idle",
            elapsed_s=0,
            spinner_index=0,
            exit_pending=False,
        )
    )
    assert "idle" in plain
    assert "connecting" in plain


def test_format_footer_exit_pending_suffix():
    plain = _strip_ansi(
        format_footer(
            connection="connected",
            phase="idle",
            elapsed_s=0,
            spinner_index=0,
            exit_pending=True,
        )
    )
    assert "press ctrl+c again to exit" in plain


def test_format_footer_negative_elapsed_clamped():
    plain = _strip_ansi(
        format_footer(
            connection="connected",
            phase="streaming",
            elapsed_s=-5,
            spinner_index=0,
            exit_pending=False,
        )
    )
    assert "• 0s" in plain


def test_format_footer_contains_ansi_color():
    out = format_footer(
        connection="connected",
        phase="idle",
        elapsed_s=0,
        spinner_index=0,
        exit_pending=False,
    )
    assert "\x1b[38;2;123;127;135m" in out
    assert out.endswith("\x1b[0m")


def test_format_footer_unknown_phase_no_timer():
    plain = _strip_ansi(
        format_footer(
            connection="connected",
            phase="custom_phase",
            elapsed_s=99,
            spinner_index=0,
            exit_pending=False,
        )
    )
    assert "custom_phase" in plain
    assert "•" not in plain

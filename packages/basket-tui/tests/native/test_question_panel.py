"""Tests for TUI question panel rendering."""

import re

import pytest

from basket_tui.native.ui.question_panel import (
    format_question_panel,
    question_panel_height,
    new_question_state,
    FREE_TEXT_LABEL,
)


def _strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m|\x1b\]8;;.*?\x1b\\", "", s)


# --- new_question_state ---

def test_new_question_state_returns_inactive():
    """Default state is inactive."""
    state = new_question_state()
    assert state["active"] is False
    assert state["tool_call_id"] == ""
    assert state["question"] == ""
    assert state["options"] == []
    assert state["selected"] == 0


# --- question_panel_height ---

def test_question_panel_height_inactive_returns_zero():
    """Inactive state -> height 0 (panel hidden)."""
    state = new_question_state()
    assert question_panel_height(state) == 0


def test_question_panel_height_active_with_options():
    """Active with 3 options -> height = 3 options + 1 free text = 4."""
    state = new_question_state()
    state["active"] = True
    state["options"] = ["A", "B", "C"]
    assert question_panel_height(state) == 4


def test_question_panel_height_active_no_options():
    """Active with no options -> height = 1 (free text only)."""
    state = new_question_state()
    state["active"] = True
    state["options"] = []
    assert question_panel_height(state) == 1


# --- format_question_panel ---

def test_format_question_panel_inactive_returns_empty():
    """Inactive state -> empty string."""
    state = new_question_state()
    assert format_question_panel(state, 80) == ""


def test_format_question_panel_selected_item_has_marker():
    """Selected item shows ❯ marker."""
    state = new_question_state()
    state["active"] = True
    state["options"] = ["Option A", "Option B"]
    state["selected"] = 0
    result = _strip_ansi(format_question_panel(state, 80))
    lines = result.split("\n")
    assert any("\u276f" in line and "Option A" in line for line in lines)


def test_format_question_panel_unselected_item_no_marker():
    """Unselected item does NOT show ❯ marker."""
    state = new_question_state()
    state["active"] = True
    state["options"] = ["Option A", "Option B"]
    state["selected"] = 0
    result = _strip_ansi(format_question_panel(state, 80))
    lines = result.split("\n")
    b_lines = [l for l in lines if "Option B" in l]
    assert b_lines, "Option B must appear"
    assert "\u276f" not in b_lines[0]


def test_format_question_panel_free_text_shown():
    """Free text slot always shown as last item."""
    state = new_question_state()
    state["active"] = True
    state["options"] = ["Option A"]
    result = _strip_ansi(format_question_panel(state, 80))
    assert FREE_TEXT_LABEL in result


def test_format_question_panel_free_text_selected():
    """When selected == len(options), free text is highlighted."""
    state = new_question_state()
    state["active"] = True
    state["options"] = ["Option A"]
    state["selected"] = 1  # free text index
    result = _strip_ansi(format_question_panel(state, 80))
    lines = result.split("\n")
    ft_lines = [l for l in lines if FREE_TEXT_LABEL in l]
    assert ft_lines, "Free text must appear"
    assert "\u276f" in ft_lines[0]


def test_format_question_panel_truncates_long_option():
    """Option longer than width is truncated with ellipsis."""
    state = new_question_state()
    state["active"] = True
    state["options"] = ["A" * 200]
    state["selected"] = 0
    result = _strip_ansi(format_question_panel(state, 60))
    assert "\u2026" in result
    for line in result.split("\n"):
        assert len(line) <= 60


def test_format_question_panel_no_options_only_free_text():
    """When options is empty, only free text row shown."""
    state = new_question_state()
    state["active"] = True
    state["options"] = []
    state["selected"] = 0
    result = _strip_ansi(format_question_panel(state, 80))
    assert FREE_TEXT_LABEL in result
    lines = [l for l in result.split("\n") if l.strip()]
    assert len(lines) == 1

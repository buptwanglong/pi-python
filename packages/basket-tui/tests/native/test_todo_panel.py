"""Tests for TUI todo panel rendering."""

import re

import pytest

from basket_tui.native.ui.todo_panel import (
    MAX_PANEL_LINES,
    format_todo_panel,
    todo_panel_height,
)


def _strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m|\x1b\]8;;.*?\x1b\\", "", s)


# --- todo_panel_height ---

def test_todo_panel_height_empty_returns_zero():
    """No todos -> height 0 (panel hidden)."""
    assert todo_panel_height([]) == 0


def test_todo_panel_height_all_completed_returns_zero():
    """All completed/cancelled -> height 0 (panel hidden)."""
    todos = [
        {"id": "1", "content": "A", "status": "completed"},
        {"id": "2", "content": "B", "status": "cancelled"},
    ]
    assert todo_panel_height(todos) == 0


def test_todo_panel_height_with_active_tasks():
    """Active tasks -> height = min(active_count + 1, MAX)."""
    todos = [
        {"id": "1", "content": "A", "status": "in_progress"},
        {"id": "2", "content": "B", "status": "pending"},
        {"id": "3", "content": "C", "status": "completed"},
    ]
    # 2 active + 1 separator line = 3
    assert todo_panel_height(todos) == 3


def test_todo_panel_height_capped_at_max():
    """Many active tasks -> capped at MAX_PANEL_LINES."""
    todos = [{"id": str(i), "content": f"Task {i}", "status": "pending"} for i in range(20)]
    assert todo_panel_height(todos) == MAX_PANEL_LINES


# --- format_todo_panel ---

def test_format_todo_panel_empty_returns_empty_string():
    """No todos -> empty string."""
    assert format_todo_panel([], 80) == ""


def test_format_todo_panel_in_progress_shows_solid_square():
    """in_progress items display solid square icon."""
    todos = [{"id": "1", "content": "Explore context", "status": "in_progress"}]
    result = _strip_ansi(format_todo_panel(todos, 80))
    assert "\u25fc" in result
    assert "Explore context" in result


def test_format_todo_panel_pending_shows_hollow_square():
    """pending items display hollow square icon."""
    todos = [{"id": "1", "content": "Ask questions", "status": "pending"}]
    result = _strip_ansi(format_todo_panel(todos, 80))
    assert "\u25fb" in result
    assert "Ask questions" in result


def test_format_todo_panel_sort_order():
    """in_progress first, then pending, then completed."""
    todos = [
        {"id": "1", "content": "AAA-pending", "status": "pending"},
        {"id": "2", "content": "BBB-progress", "status": "in_progress"},
        {"id": "3", "content": "CCC-done", "status": "completed"},
    ]
    result = _strip_ansi(format_todo_panel(todos, 80))
    idx_progress = result.index("BBB-progress")
    idx_pending = result.index("AAA-pending")
    assert idx_progress < idx_pending, "in_progress should come before pending"


def test_format_todo_panel_overflow_shows_count():
    """When items exceed MAX_PANEL_LINES, overflow count is shown."""
    todos = [{"id": str(i), "content": f"Task {i}", "status": "pending"} for i in range(20)]
    result = _strip_ansi(format_todo_panel(todos, 80))
    assert "more" in result.lower()


def test_format_todo_panel_all_completed_returns_empty():
    """All completed -> empty (panel hidden)."""
    todos = [
        {"id": "1", "content": "Done", "status": "completed"},
        {"id": "2", "content": "Cancelled", "status": "cancelled"},
    ]
    assert format_todo_panel(todos, 80) == ""


def test_format_todo_panel_truncates_long_content():
    """Content longer than available width is truncated with ellipsis."""
    todos = [{"id": "1", "content": "A" * 200, "status": "pending"}]
    result = _strip_ansi(format_todo_panel(todos, 60))
    assert "\u2026" in result
    # Each line should not exceed width
    for line in result.split("\n"):
        assert len(line) <= 60

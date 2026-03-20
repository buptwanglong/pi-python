"""
Todo panel rendering for terminal-native TUI.

Renders a fixed-height panel showing task progress with status icons and ANSI colors.
Panel is hidden (height 0) when no active tasks exist.
"""

from __future__ import annotations

from typing import Any

# Maximum panel height in lines (including separator)
MAX_PANEL_LINES = 8

# Status -> (icon, ANSI color code)
_STATUS_STYLE: dict[str, tuple[str, str]] = {
    "in_progress": ("\u25fc", "\x1b[38;2;100;200;255m"),  # bright cyan
    "pending":     ("\u25fb", "\x1b[38;2;123;127;135m"),   # muted gray
    "completed":   ("\u2713", "\x1b[38;2;80;160;80m"),     # dim green
    "cancelled":   ("\u2717", "\x1b[38;2;200;80;80m"),     # dim red
}
_ANSI_RESET = "\x1b[0m"
_ANSI_DIM = "\x1b[38;2;123;127;135m"

# Sort priority: lower = higher priority (shown first)
_STATUS_ORDER: dict[str, int] = {
    "in_progress": 0,
    "pending": 1,
    "completed": 2,
    "cancelled": 3,
}

# Prefix indentation matching design mockup
_ITEM_PREFIX = "  "
# icon(1) + space(1) = 2, total overhead per item line
_ITEM_OVERHEAD = len(_ITEM_PREFIX) + 2


def todo_panel_height(todos: list[dict[str, Any]]) -> int:
    """Return the panel height in lines. 0 means hidden (no active tasks)."""
    active = [t for t in todos if t.get("status") in ("pending", "in_progress")]
    if not active:
        return 0
    # +1 for top separator line
    return min(len(active) + 1, MAX_PANEL_LINES)


def _sort_todos(todos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort: in_progress first, pending second, completed/cancelled last. Stable within group."""
    return sorted(
        todos,
        key=lambda t: _STATUS_ORDER.get(t.get("status", "pending"), 99),
    )


def format_todo_panel(todos: list[dict[str, Any]], width: int) -> str:
    """
    Render the todo panel as a single ANSI string (lines joined by newline).

    Returns empty string when no active tasks (panel should be hidden).
    """
    active = [t for t in todos if t.get("status") in ("pending", "in_progress")]
    if not active:
        return ""

    sorted_todos = _sort_todos(todos)
    # Show only active items (completed/cancelled are hidden)
    active_sorted = [
        t for t in sorted_todos if t.get("status") in ("pending", "in_progress")
    ]

    # Available lines: MAX_PANEL_LINES - 1 (separator) - 1 (overflow indicator if needed)
    max_items = MAX_PANEL_LINES - 1  # reserve 1 for separator
    needs_overflow = len(active_sorted) > max_items
    if needs_overflow:
        # Reserve 1 line for the "+N more" indicator
        max_items -= 1

    show_items = active_sorted[:max_items]
    remaining = len(active_sorted) - len(show_items)

    lines: list[str] = []

    # Top separator (respects width)
    sep_char = "\u2500"
    lines.append(f"{_ANSI_DIM}{sep_char * width}{_ANSI_RESET}")

    # Max content width = width - prefix - icon - space
    max_content_len = max(width - _ITEM_OVERHEAD, 1)

    for item in show_items:
        status = item.get("status", "pending")
        icon, color = _STATUS_STYLE.get(status, ("?", _ANSI_DIM))
        content = item.get("content", "")
        if len(content) > max_content_len:
            content = content[: max_content_len - 1] + "\u2026"
        lines.append(f"{color}{_ITEM_PREFIX}{icon} {content}{_ANSI_RESET}")

    # Overflow indicator
    if remaining > 0:
        overflow_text = f"{_ITEM_PREFIX}  +{remaining} more"
        if len(overflow_text) > width:
            overflow_text = overflow_text[:width]
        lines.append(f"{_ANSI_DIM}{overflow_text}{_ANSI_RESET}")

    return "\n".join(lines)

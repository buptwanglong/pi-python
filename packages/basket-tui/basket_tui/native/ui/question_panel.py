"""
Question panel rendering for terminal-native TUI.

Renders an interactive option list at the bottom of the screen when
an ask_user_question tool is active. Panel is hidden (height 0) when inactive.
"""

from __future__ import annotations

from typing import Any

# ANSI styles
_ANSI_RESET = "\x1b[0m"
_ANSI_HIGHLIGHT = "\x1b[38;2;100;200;255m"  # bright cyan (matches todo in_progress)
_ANSI_DIM = "\x1b[38;2;123;127;135m"  # muted gray

# Selection marker
_SELECTED_PREFIX = "  \u276f "  # ❯
_UNSELECTED_PREFIX = "    "
_ITEM_OVERHEAD = len(_UNSELECTED_PREFIX)

# Free text label (always last item)
FREE_TEXT_LABEL = "\u81ea\u7531\u8f93\u5165..."


def new_question_state() -> dict[str, Any]:
    """Return a fresh, inactive question state dict."""
    return {
        "active": False,
        "tool_call_id": "",
        "question": "",
        "options": [],
        "selected": 0,
    }


def question_panel_height(state: dict[str, Any]) -> int:
    """Return the panel height in lines. 0 means hidden (inactive)."""
    if not state.get("active"):
        return 0
    options = state.get("options") or []
    return len(options) + 1  # +1 for free text slot


def format_question_panel(state: dict[str, Any], width: int) -> str:
    """
    Render the question option list as a single ANSI string (lines joined by newline).

    Returns empty string when inactive (panel should be hidden).
    """
    if not state.get("active"):
        return ""

    options: list[str] = state.get("options") or []
    selected: int = state.get("selected", 0)
    max_content_len = max(width - _ITEM_OVERHEAD, 1)

    lines: list[str] = []

    for i, option in enumerate(options):
        is_sel = i == selected
        prefix = _SELECTED_PREFIX if is_sel else _UNSELECTED_PREFIX
        color = _ANSI_HIGHLIGHT if is_sel else _ANSI_RESET
        text = option
        if len(text) > max_content_len:
            text = text[: max_content_len - 1] + "\u2026"
        lines.append(f"{color}{prefix}{text}{_ANSI_RESET}")

    # Free text slot (always last)
    ft_idx = len(options)
    is_ft_sel = selected == ft_idx
    ft_prefix = _SELECTED_PREFIX if is_ft_sel else _UNSELECTED_PREFIX
    ft_color = _ANSI_HIGHLIGHT if is_ft_sel else _ANSI_DIM
    lines.append(f"{ft_color}{ft_prefix}{FREE_TEXT_LABEL}{_ANSI_RESET}")

    return "\n".join(lines)

"""Tests for native line renderer."""

import re

import pytest

from basket_tui.native.render import render_messages


def _visible_width(line: str) -> int:
    """Strip ANSI codes and return character count."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m|\x1b\]8;;.*?\x1b\\")
    return len(ansi_escape.sub("", line))


def test_render_messages_returns_list_of_strings():
    """render_messages returns a list of strings."""
    messages = [{"role": "user", "content": "Hi"}]
    lines = render_messages(messages, width=80)
    assert isinstance(lines, list)
    assert all(isinstance(line, str) for line in lines)
    assert len(lines) >= 1


def test_render_messages_no_line_exceeds_width():
    """Each line has visible length <= width."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "A " + "long " * 20 + " reply."},
    ]
    lines = render_messages(messages, width=80)
    for line in lines:
        assert _visible_width(line) <= 80, f"Line exceeds 80 cols: {line!r}"


def test_render_messages_assistant_markdown_contains_ansi_and_bold():
    """Assistant message with Markdown **bold** is rendered with ANSI and bold text."""
    messages = [{"role": "assistant", "content": "Say **bold** here."}]
    lines = render_messages(messages, width=80)
    text = "".join(lines)
    assert "\x1b[" in text or "\033[" in text, "Output should contain ANSI codes"
    assert "bold" in text, "Output should contain bold text"

"""Tests for native line renderer."""

import re

import pytest

from basket_tui.native.pipeline import render_messages


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


def test_render_messages_no_role_prefix_in_output():
    """User/assistant/tool are distinguished by styling, not [role] prefixes."""
    text = "".join(
        render_messages(
            [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "收到。"},
                {"role": "tool", "content": "Exec\n{}"},
            ],
            width=80,
        )
    )
    assert "[user]" not in text
    assert "[assistant]" not in text
    assert "[tool]" not in text
    assert "你好" in text
    assert "收到" in text
    assert "Exec" in text


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


def test_render_messages_empty_list_returns_empty():
    """Empty message list returns empty list of lines."""
    lines = render_messages([], width=80)
    assert lines == []


def test_render_messages_very_long_line_renders():
    """Very long content renders without crashing; Console may or may not wrap long words."""
    messages = [{"role": "user", "content": "x" * 200}]
    lines = render_messages(messages, width=40)
    assert len(lines) >= 1
    assert any("x" in line for line in lines)


def test_render_messages_markdown_code_block():
    """Assistant message with Markdown code block renders without crashing."""
    messages = [
        {"role": "assistant", "content": "Use:\n```python\nprint('hi')\n```\nDone."}
    ]
    lines = render_messages(messages, width=80)
    assert len(lines) >= 1
    text = "".join(lines)
    assert "hi" in text or "print" in text

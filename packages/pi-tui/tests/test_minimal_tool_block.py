"""Test minimal tool block formatting."""
from pi_tui.core.message_renderer import MessageRenderer


def test_tool_block_no_complex_borders():
    """Tool blocks use simple formatting, no Unicode box chars."""
    renderer = MessageRenderer()

    formatted = renderer.format_tool_block(
        "bash",
        {"command": "ls -la"},
        "exit 0"
    )

    # Should NOT contain complex Unicode borders
    assert "╭" not in formatted
    assert "╰" not in formatted
    assert "├" not in formatted

    # Should contain tool name and basic info
    assert "bash" in formatted.lower()


def test_tool_block_simple_separator():
    """Tool blocks use simple horizontal lines."""
    renderer = MessageRenderer()

    formatted = renderer.format_tool_block(
        "read",
        {"file_path": "/test.py"},
        "Read 10 lines"
    )

    # May contain simple separator but not fancy borders
    line_chars = [c for c in formatted if c in "─━-"]
    # If separators exist, they should be simple
    assert "╭" not in formatted


def test_tool_result_no_emoji_prefix():
    """Tool results don't use emoji prefixes."""
    renderer = MessageRenderer()

    success_result = renderer.format_tool_result_line("Success", True)
    error_result = renderer.format_tool_result_line("Failed", False)

    # No emojis
    assert "✅" not in success_result
    assert "❌" not in error_result

"""Test minimal tool block formatting."""
from basket_tui.core.message_renderer import MessageRenderer


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


def test_thinking_block_no_emoji():
    """Thinking blocks use plain text, no emoji."""
    renderer = MessageRenderer()

    formatted = renderer.render_thinking_text("Analyzing the code...")
    formatted_str = str(formatted)

    # No thinking emoji
    assert "💭" not in formatted_str

    # Should contain the thinking text
    assert "Analyzing" in formatted_str or "thinking" in formatted_str.lower()


def test_system_message_no_emoji():
    """System messages use plain text info prefix."""
    renderer = MessageRenderer()

    formatted = renderer.render_system_message("Operation completed")
    formatted_str = str(formatted)

    # No info emoji
    assert "ℹ️" not in formatted_str

    # Should contain the message
    assert "Operation completed" in formatted_str

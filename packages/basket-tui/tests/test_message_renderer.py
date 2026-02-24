"""
Tests for MessageRenderer class
"""

import pytest
from rich.text import Text
from rich.markdown import Markdown
from basket_tui.core.message_renderer import MessageRenderer


def test_render_user_message():
    """Test rendering user messages."""
    renderer = MessageRenderer()
    result = renderer.render_user_message("Hello, world!")

    assert isinstance(result, Text)
    assert "You: Hello, world!" in str(result)
    assert result.style == "bold"


def test_render_system_message_string():
    """Test rendering system message from string."""
    renderer = MessageRenderer()
    result = renderer.render_system_message("System notification")

    assert isinstance(result, Text)
    # No "Info:" prefix in minimal style
    assert "System notification" in str(result)
    assert result.style == "dim"


def test_render_system_message_rich_object():
    """Test rendering system message that's already a Rich renderable."""
    renderer = MessageRenderer()
    markdown = Markdown("**Bold text**")
    result = renderer.render_system_message(markdown)

    # Should return the same object
    assert result is markdown


def test_render_assistant_text():
    """Test rendering streaming assistant text."""
    renderer = MessageRenderer()
    result = renderer.render_assistant_text("Streaming text...")

    assert isinstance(result, Text)
    assert "Streaming text..." in str(result)


def test_render_assistant_markdown():
    """Test rendering finalized assistant markdown."""
    renderer = MessageRenderer()
    result = renderer.render_assistant_markdown("# Heading\n\nParagraph")

    assert isinstance(result, Markdown)


def test_render_thinking_text():
    """Test rendering thinking text."""
    renderer = MessageRenderer()
    result = renderer.render_thinking_text("Analyzing code...")

    assert isinstance(result, Text)
    assert "Thinking..." in str(result)
    assert "Analyzing code..." in str(result)


def test_format_tool_block_with_args():
    """Test formatting tool block with arguments."""
    renderer = MessageRenderer()
    tool_name = "read_file"
    args = {"path": "/test/file.py", "encoding": "utf-8"}
    result_text = "执行中..."

    result = renderer.format_tool_block(tool_name, args, result_text)

    assert "Read_file:" in result
    assert "path" in result or "encoding" in result or "/test/file.py" in result
    assert "执行中..." in result


def test_format_tool_block_no_args():
    """Test formatting tool block without arguments."""
    renderer = MessageRenderer()
    tool_name = "list_files"
    args = {}
    result_text = "完成"

    result = renderer.format_tool_block(tool_name, args, result_text)

    assert "List_files:" in result
    assert "完成" in result


def test_format_tool_result_line_success():
    """Test formatting successful tool result."""
    renderer = MessageRenderer()
    result = renderer.format_tool_result_line("Operation completed", success=True)

    assert result == "Operation completed"
    assert "Error:" not in result


def test_format_tool_result_line_failure():
    """Test formatting failed tool result."""
    renderer = MessageRenderer()
    result = renderer.format_tool_result_line("File not found", success=False)

    assert "Error:" in result
    assert "File not found" in result


def test_message_renderer_is_stateless():
    """Test that MessageRenderer has no state and can be reused."""
    renderer = MessageRenderer()

    # Call multiple methods
    result1 = renderer.render_user_message("First message")
    result2 = renderer.render_user_message("Second message")

    # Should produce independent results
    assert "First message" in str(result1)
    assert "Second message" in str(result2)
    assert result1 != result2

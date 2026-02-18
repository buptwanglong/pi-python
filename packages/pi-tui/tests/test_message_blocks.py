"""
Tests for message block widgets (ThinkingBlock, ToolBlock)
"""

import pytest
from rich.text import Text
from pi_tui.components.message_blocks import ThinkingBlock, ToolBlock


def test_thinking_block_initialization():
    """Test ThinkingBlock initializes correctly."""
    block = ThinkingBlock()

    assert block is not None
    assert block.thinking_text == ""
    assert "message-block" in block.classes
    assert "message-system" in block.classes


def test_thinking_block_append_thinking():
    """Test appending thinking text to ThinkingBlock."""
    block = ThinkingBlock()

    block.append_thinking("Analyzing code...")
    assert block.thinking_text == "Analyzing code..."

    block.append_thinking(" Found 3 functions.")
    assert block.thinking_text == "Analyzing code... Found 3 functions."


def test_tool_block_initialization():
    """Test ToolBlock initializes correctly."""
    tool_name = "read_file"
    args = {"path": "/test/file.py"}

    block = ToolBlock(tool_name, args)

    assert block is not None
    assert block.tool_name == tool_name
    assert block.tool_args == args
    assert "message-block" in block.classes
    assert "tool-block" in block.classes


def test_tool_block_stores_tool_info():
    """Test ToolBlock stores tool name and arguments."""
    tool_name = "execute_command"
    args = {"command": "ls -la", "cwd": "/tmp"}

    block = ToolBlock(tool_name, args)

    assert block.tool_name == "execute_command"
    assert block.tool_args["command"] == "ls -la"
    assert block.tool_args["cwd"] == "/tmp"


def test_tool_block_update_result_success():
    """Test updating ToolBlock with successful result."""
    block = ToolBlock("read_file", {"path": "/test.py"})

    # Initial content should show 执行中...
    initial_content = str(block.renderable)
    assert "执行中..." in initial_content

    # Update with success result
    block.update_result("File read successfully", success=True)

    # Should not have error prefix
    updated_content = str(block.renderable)
    assert "File read successfully" in updated_content
    assert "Error:" not in updated_content


def test_tool_block_update_result_failure():
    """Test updating ToolBlock with failed result."""
    block = ToolBlock("read_file", {"path": "/nonexistent.py"})

    # Update with failure result
    block.update_result("File not found", success=False)

    # Should have error prefix
    updated_content = str(block.renderable)
    assert "Error:" in updated_content
    assert "File not found" in updated_content


def test_tool_block_preserves_tool_info_after_update():
    """Test ToolBlock preserves tool name and args after update."""
    tool_name = "write_file"
    args = {"path": "/output.txt", "content": "test"}

    block = ToolBlock(tool_name, args)
    block.update_result("Write successful", success=True)

    # Tool info should still be accessible
    assert block.tool_name == tool_name
    assert block.tool_args == args


def test_thinking_block_multiple_appends():
    """Test multiple appends to ThinkingBlock accumulate correctly."""
    block = ThinkingBlock()

    texts = [
        "Step 1: Loading data",
        "Step 2: Processing",
        "Step 3: Complete"
    ]

    for text in texts:
        block.append_thinking(text)

    # All text should be accumulated
    for text in texts:
        assert text in block.thinking_text

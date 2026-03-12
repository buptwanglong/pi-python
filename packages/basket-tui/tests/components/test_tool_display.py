"""
Tests for ToolDisplay Widget

ToolDisplay shows tool execution with status indicators.
"""

import pytest
from basket_tui.components.tool_display import ToolDisplay


class TestToolDisplay:
    """Test suite for ToolDisplay Widget"""

    @pytest.mark.asyncio
    async def test_initial_state(self):
        """ToolDisplay should start with empty state"""
        widget = ToolDisplay()
        assert widget.tool_name == ""
        assert widget.tool_args == {}
        assert widget.tool_result is None
        assert widget.is_running is False
        assert widget.has_error is False

    @pytest.mark.asyncio
    async def test_reactive_properties(self):
        """All key properties should be reactive"""
        widget = ToolDisplay()
        assert hasattr(widget.__class__, "tool_name")
        assert hasattr(widget.__class__, "tool_args")
        assert hasattr(widget.__class__, "tool_result")
        assert hasattr(widget.__class__, "is_running")
        assert hasattr(widget.__class__, "has_error")

    @pytest.mark.asyncio
    async def test_show_tool_call(self):
        """show_tool_call should set tool state to running"""
        widget = ToolDisplay()
        widget.show_tool_call("bash", {"command": "ls"})

        assert widget.tool_name == "bash"
        assert widget.tool_args == {"command": "ls"}
        assert widget.is_running is True
        assert widget.has_error is False
        assert widget.tool_result is None

    @pytest.mark.asyncio
    async def test_show_result_success(self):
        """show_result should set result and stop running"""
        widget = ToolDisplay()
        widget.show_tool_call("bash", {"command": "ls"})

        widget.show_result("file1.txt\nfile2.txt", error=False)

        assert widget.tool_result == "file1.txt\nfile2.txt"
        assert widget.is_running is False
        assert widget.has_error is False

    @pytest.mark.asyncio
    async def test_show_result_error(self):
        """show_result with error should set has_error"""
        widget = ToolDisplay()
        widget.show_tool_call("bash", {"command": "ls"})

        widget.show_result("Command failed", error=True)

        assert widget.tool_result == "Command failed"
        assert widget.is_running is False
        assert widget.has_error is True

    @pytest.mark.asyncio
    async def test_format_args_preview_single(self):
        """_format_args_preview should show single arg"""
        widget = ToolDisplay()
        preview = widget._format_args_preview({"command": "ls"})
        assert "command" in preview

    @pytest.mark.asyncio
    async def test_format_args_preview_multiple(self):
        """_format_args_preview should show first 2 args"""
        widget = ToolDisplay()
        preview = widget._format_args_preview(
            {"arg1": "val1", "arg2": "val2", "arg3": "val3"}
        )
        assert "arg1" in preview
        assert "arg2" in preview
        assert "..." in preview  # More than 2 args

    @pytest.mark.asyncio
    async def test_format_args_preview_empty(self):
        """_format_args_preview should handle empty args"""
        widget = ToolDisplay()
        preview = widget._format_args_preview({})
        assert preview == ""

    @pytest.mark.asyncio
    async def test_truncate_short_text(self):
        """_truncate should not truncate short text"""
        widget = ToolDisplay()
        text = "Short text"
        result = widget._truncate(text, 100)
        assert result == text

    @pytest.mark.asyncio
    async def test_truncate_long_text(self):
        """_truncate should truncate long text"""
        widget = ToolDisplay()
        text = "A" * 300
        result = widget._truncate(text, 100)
        assert len(result) <= 103  # 100 + "..."
        assert result.endswith("...")

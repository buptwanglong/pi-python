"""
Tests for the observation formatting layer.
"""

import json

import pytest
from pydantic import BaseModel, Field

from basket_agent.observation_formatter import (
    DEFAULT_HEAD_LINES,
    DEFAULT_MAX_CHARS,
    DEFAULT_TAIL_LINES,
    TOOL_FORMATTERS,
    _format_with_head_tail,
    format_bash_result,
    format_default,
    format_edit_result,
    format_grep_result,
    format_observation,
    format_read_result,
    strip_ansi,
)


# ---------------------------------------------------------------------------
# strip_ansi
# ---------------------------------------------------------------------------


class TestStripAnsi:
    def test_removes_color_codes(self):
        text = "\x1B[31mERROR\x1B[0m: something failed"
        assert strip_ansi(text) == "ERROR: something failed"

    def test_removes_bold_and_underline(self):
        text = "\x1B[1m\x1B[4mBold Underline\x1B[0m"
        assert strip_ansi(text) == "Bold Underline"

    def test_preserves_plain_text(self):
        text = "no ansi codes here"
        assert strip_ansi(text) == "no ansi codes here"

    def test_removes_cursor_movement(self):
        text = "\x1B[2J\x1B[Hscreen cleared"
        assert strip_ansi(text) == "screen cleared"

    def test_empty_string(self):
        assert strip_ansi("") == ""


# ---------------------------------------------------------------------------
# _format_with_head_tail
# ---------------------------------------------------------------------------


class TestFormatWithHeadTail:
    def test_short_text_unchanged(self):
        text = "\n".join(f"line {i}" for i in range(10))
        assert _format_with_head_tail(text, head=40, tail=20) == text

    def test_exactly_at_limit_unchanged(self):
        text = "\n".join(f"line {i}" for i in range(60))
        assert _format_with_head_tail(text, head=40, tail=20) == text

    def test_over_limit_truncated(self):
        lines = [f"line {i}" for i in range(200)]
        result = _format_with_head_tail("\n".join(lines), head=40, tail=20)

        assert "line 0" in result
        assert "line 39" in result
        assert "line 199" in result
        assert "line 180" in result
        assert "[... 140 lines omitted ...]" in result
        # Lines in the middle should NOT be present
        assert "line 100" not in result


# ---------------------------------------------------------------------------
# format_bash_result
# ---------------------------------------------------------------------------


class TestFormatBashResult:
    def test_short_output_unchanged(self):
        text = "total 32\n-rw-r--r-- 1 user group 1234 Mar 21 README.md"
        assert format_bash_result(text) == text

    def test_long_output_truncated(self):
        lines = [f"commit abc{i}" for i in range(200)]
        result = format_bash_result("\n".join(lines))

        assert f"commit abc0" in result
        assert f"commit abc{DEFAULT_HEAD_LINES - 1}" in result
        assert f"commit abc199" in result
        omitted = 200 - DEFAULT_HEAD_LINES - DEFAULT_TAIL_LINES
        assert f"[... {omitted} lines omitted ...]" in result

    def test_strips_ansi_codes(self):
        text = "\x1B[32m+ added\x1B[0m\n\x1B[31m- removed\x1B[0m"
        result = format_bash_result(text)
        assert "\x1B[" not in result
        assert "+ added" in result
        assert "- removed" in result

    def test_strips_ansi_then_truncates(self):
        lines = [f"\x1B[33mline {i}\x1B[0m" for i in range(200)]
        result = format_bash_result("\n".join(lines))
        assert "\x1B[" not in result
        assert "[... " in result


# ---------------------------------------------------------------------------
# format_read_result
# ---------------------------------------------------------------------------


class TestFormatReadResult:
    def test_short_file_unchanged(self):
        text = "\n".join(f"  {i}: code" for i in range(30))
        assert format_read_result(text) == text

    def test_long_file_truncated(self):
        lines = [f"  {i}: code line" for i in range(500)]
        result = format_read_result("\n".join(lines))
        # head=50, tail=20, so 500 - 70 = 430 omitted
        assert "[... 430 lines omitted ...]" in result
        assert "  0: code line" in result
        assert "  499: code line" in result


# ---------------------------------------------------------------------------
# format_grep_result
# ---------------------------------------------------------------------------


class TestFormatGrepResult:
    def test_few_matches_unchanged(self):
        lines = [f"file.py:10: match {i}" for i in range(20)]
        text = "\n".join(lines)
        assert format_grep_result(text) == text

    def test_exactly_50_matches_unchanged(self):
        lines = [f"file.py:{i}: match" for i in range(50)]
        text = "\n".join(lines)
        assert format_grep_result(text) == text

    def test_over_50_matches_capped(self):
        lines = [f"file.py:{i}: match" for i in range(120)]
        result = format_grep_result("\n".join(lines))
        assert "[... 70 more matches omitted ...]" in result
        assert "file.py:0: match" in result
        assert "file.py:49: match" in result
        assert "file.py:50: match" not in result


# ---------------------------------------------------------------------------
# format_edit_result
# ---------------------------------------------------------------------------


class TestFormatEditResult:
    def test_short_passthrough(self):
        text = "File saved successfully."
        assert format_edit_result(text) == text

    def test_exactly_500_chars_unchanged(self):
        text = "x" * 500
        assert format_edit_result(text) == text

    def test_long_truncation(self):
        text = "x" * 1000
        result = format_edit_result(text)
        assert len(result) < 1000
        assert result.startswith("x" * 500)
        assert "[... output truncated (edit/write confirmation only) ...]" in result


# ---------------------------------------------------------------------------
# format_default
# ---------------------------------------------------------------------------


class TestFormatDefault:
    def test_under_limit_unchanged(self):
        text = "short result"
        assert format_default(text) == text

    def test_exactly_at_limit_unchanged(self):
        text = "a" * DEFAULT_MAX_CHARS
        assert format_default(text) == text

    def test_over_limit_truncated(self):
        text = "a" * 10000
        result = format_default(text)
        assert len(result) < 10000
        head_chars = DEFAULT_MAX_CHARS * 2 // 3
        tail_chars = DEFAULT_MAX_CHARS // 3
        omitted = 10000 - head_chars - tail_chars
        assert f"[... {omitted} chars omitted ...]" in result

    def test_preserves_head_and_tail(self):
        # Build a string where head and tail have identifiable content
        head_part = "HEAD_" * 1000  # 5000 chars
        tail_part = "_TAIL" * 1000  # 5000 chars
        text = head_part + tail_part
        result = format_default(text)
        assert result.startswith("HEAD_")
        assert result.endswith("_TAIL")


# ---------------------------------------------------------------------------
# format_observation: dispatch and serialization
# ---------------------------------------------------------------------------


class TestFormatObservation:
    def test_with_pydantic_model(self):
        class FileInfo(BaseModel):
            path: str = Field(..., description="File path")
            size: int = Field(..., description="File size")

        model = FileInfo(path="/tmp/test.py", size=42)
        result = format_observation("unknown_tool", model)
        # Should be JSON-serialized
        assert "/tmp/test.py" in result
        assert "42" in result

    def test_with_dict(self):
        data = {"key": "value", "count": 10}
        result = format_observation("unknown_tool", data)
        parsed = json.loads(result)
        assert parsed == data

    def test_with_list(self):
        data = [1, 2, 3]
        result = format_observation("unknown_tool", data)
        assert result == "[1, 2, 3]"

    def test_unknown_tool_uses_default(self):
        result = format_observation("some_new_tool", "short text")
        assert result == "short text"

    def test_bash_dispatch(self):
        lines = [f"\x1B[32mline {i}\x1B[0m" for i in range(200)]
        result = format_observation("bash", "\n".join(lines))
        # Should strip ANSI and truncate
        assert "\x1B[" not in result
        assert "[... " in result

    def test_read_dispatch(self):
        lines = [f"  {i}: code" for i in range(200)]
        result = format_observation("read", "\n".join(lines))
        # head=50, tail=20, 200 - 70 = 130 omitted
        assert "[... 130 lines omitted ...]" in result

    def test_grep_dispatch(self):
        lines = [f"file.py:{i}: match" for i in range(100)]
        result = format_observation("grep", "\n".join(lines))
        assert "[... 50 more matches omitted ...]" in result

    def test_edit_dispatch(self):
        result = format_observation("edit", "File updated.")
        assert result == "File updated."

    def test_write_dispatch(self):
        result = format_observation("write", "File created.")
        assert result == "File created."

    def test_string_passthrough(self):
        """String results should not be double-serialized."""
        result = format_observation("bash", "simple output")
        assert result == "simple output"

    def test_non_serializable_fallback(self):
        """Non-JSON-serializable objects should fall back to str()."""

        class Custom:
            def __str__(self):
                return "custom_repr"

        result = format_observation("unknown_tool", Custom())
        assert result == "custom_repr"


# ---------------------------------------------------------------------------
# TOOL_FORMATTERS registry
# ---------------------------------------------------------------------------


class TestToolFormattersRegistry:
    def test_known_tools_registered(self):
        assert "bash" in TOOL_FORMATTERS
        assert "read" in TOOL_FORMATTERS
        assert "grep" in TOOL_FORMATTERS
        assert "edit" in TOOL_FORMATTERS
        assert "write" in TOOL_FORMATTERS

    def test_write_uses_edit_formatter(self):
        assert TOOL_FORMATTERS["write"] is TOOL_FORMATTERS["edit"]

    def test_all_formatters_are_callable(self):
        for name, fn in TOOL_FORMATTERS.items():
            assert callable(fn), f"Formatter for '{name}' is not callable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

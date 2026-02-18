"""
Unit tests for TUI mode _format_tool_result.
"""

import pytest
from pi_coding_agent.modes.tui import _format_tool_result


def test_format_tool_result_none():
    """None result returns generic success message."""
    assert _format_tool_result("any_tool", None) == "Tool executed successfully (no output)"


def test_format_tool_result_bash_success():
    """Bash tool: stdout, exit code, no timeout."""
    result = {"stdout": "hello\n", "stderr": "", "exit_code": 0, "timeout": False}
    out = _format_tool_result("bash", result)
    assert "exit 0" in out
    assert "hello" in out
    assert "⏱️" not in out


def test_format_tool_result_bash_timeout():
    """Bash tool: timeout shown."""
    result = {"stdout": "", "stderr": "", "exit_code": -1, "timeout": True}
    out = _format_tool_result("bash", result)
    assert "⏱️" in out or "timed out" in out
    assert "exit" in out.lower() and "-1" in out


def test_format_tool_result_bash_truncation():
    """Bash tool: long stdout truncated to 1000 chars."""
    long_stdout = "x" * 600
    result = {"stdout": long_stdout, "stderr": "", "exit_code": 0, "timeout": False}
    out = _format_tool_result("bash", result)
    # 600 chars is under 1000 limit, so no truncation
    assert "x" in out
    assert "exit 0" in out


def test_format_tool_result_read():
    """Read tool: file path, lines, content preview."""
    result = {
        "file_path": "/tmp/foo.txt",
        "lines": 5,
        "content": "line1\nline2\nline3\nline4\nline5",
    }
    out = _format_tool_result("read", result)
    assert "📄" not in out  # No emojis in minimal format
    assert "5 lines" in out
    assert "/tmp/foo.txt" in out
    assert "line1" in out


def test_format_tool_result_read_long_preview():
    """Read tool: content preview shows first 5 lines."""
    result = {"file_path": "f", "lines": 1, "content": "a" * 250}
    out = _format_tool_result("read", result)
    # Single line content, no truncation needed for first 5 lines
    assert "Read 1 lines" in out
    assert "f" in out


def test_format_tool_result_write_success():
    """Write tool: success."""
    result = {"file_path": "/path/to/file.py", "success": True}
    out = _format_tool_result("write", result)
    assert "✍️" not in out  # No emojis in minimal format
    assert "Wrote file" in out
    assert "/path/to/file.py" in out


def test_format_tool_result_write_failure():
    """Write tool: failure with error message."""
    result = {"file_path": "x", "success": False, "error": "Permission denied"}
    out = _format_tool_result("write", result)
    assert "❌" not in out  # No emojis in minimal format
    assert "Permission denied" in out


def test_format_tool_result_edit_success():
    """Edit tool: success with replacement count."""
    result = {"success": True, "replacements_made": 3, "file_path": "foo.py"}
    out = _format_tool_result("edit", result)
    assert "✏️" not in out  # No emojis in minimal format
    assert "3 replacement" in out
    assert "foo.py" in out


def test_format_tool_result_edit_failure():
    """Edit tool: failure."""
    result = {"success": False, "error": "Pattern not found", "file_path": "x"}
    out = _format_tool_result("edit", result)
    assert "❌" not in out  # No emojis in minimal format
    assert "Pattern not found" in out


def test_format_tool_result_grep():
    """Grep tool: match count and sample matches."""
    result = {
        "total_matches": 10,
        "truncated": True,
        "matches": [
            {"file_path": "a.py", "line_number": 1},
            {"file_path": "b.py", "line_number": 2},
        ],
    }
    out = _format_tool_result("grep", result)
    assert "🔍" not in out  # No emojis in minimal format
    assert "10 match" in out
    assert "a.py" in out
    assert "b.py" in out


def test_format_tool_result_unknown_dict_fallback():
    """Unknown tool with dict result uses str() fallback."""
    result = {"status": "ok", "data": "something"}
    out = _format_tool_result("unknown_tool", result)
    # Fallback: str(result), truncated if > 300 chars
    assert "status" in out or "ok" in out


def test_format_tool_result_non_dict_fallback():
    """Non-dict result: str() truncated to 500."""
    out = _format_tool_result("tool", "short")
    assert out == "short"

    long_str = "a" * 600
    out = _format_tool_result("tool", long_str)
    # Should be truncated at 500 chars + truncation message
    assert len(out) < 600
    assert "truncated" in out

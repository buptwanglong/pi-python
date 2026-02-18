"""Test minimal formatting style matching Claude Code."""
import pytest
from pi_coding_agent.modes.tui import _format_tool_result


def test_bash_minimal_format():
    """Bash tool shows command description and clean output."""
    result = {
        "stdout": "Hello World\nLine 2\nLine 3",
        "stderr": "",
        "exit_code": 0,
        "timeout": False,
    }

    formatted = _format_tool_result("bash", result)

    # Should NOT contain emojis
    assert "⏱️" not in formatted
    assert "📄" not in formatted
    assert "✍️" not in formatted

    # Should be clean and simple
    assert "Exit code: 0" in formatted or "exit 0" in formatted.lower()
    assert "Hello World" in formatted


def test_read_minimal_format():
    """Read tool shows file path and content preview cleanly."""
    result = {
        "lines": 100,
        "file_path": "/path/to/file.py",
        "content": "import asyncio\nimport logging\n# more content...",
    }

    formatted = _format_tool_result("read", result)

    # No emoji decorations
    assert "📄" not in formatted

    # Clean file path display
    assert "/path/to/file.py" in formatted


def test_write_minimal_format():
    """Write tool shows simple success/error message."""
    result = {
        "file_path": "/path/to/new_file.py",
        "success": True,
    }

    formatted = _format_tool_result("write", result)

    assert "✍️" not in formatted
    assert "/path/to/new_file.py" in formatted


def test_edit_minimal_format():
    """Edit tool shows replacements count cleanly."""
    result = {
        "success": True,
        "replacements_made": 3,
        "file_path": "/path/to/file.py",
    }

    formatted = _format_tool_result("edit", result)

    assert "✏️" not in formatted
    assert "3" in formatted  # replacement count


def test_grep_minimal_format():
    """Grep tool shows match count and file list."""
    result = {
        "total_matches": 47,
        "truncated": True,
        "matches": [
            {"file_path": "test1.py", "line_number": 10},
            {"file_path": "test2.py", "line_number": 25},
        ],
    }

    formatted = _format_tool_result("grep", result)

    assert "🔍" not in formatted
    assert "47" in formatted  # match count
    assert "test1.py" in formatted

"""Integration test for minimal style TUI."""
import pytest
from pi_coding_agent.modes.tui import _format_tool_result


def test_full_minimal_style_no_decorations():
    """Verify no emojis or complex decorations in any tool output."""

    # All emoji characters we want to avoid
    emoji_chars = ["💭", "✅", "❌", "📄", "✍️", "✏️", "🔍", "🔧", "ℹ️", "⏱️", "📤"]

    # Test all tool types
    test_cases = [
        ("bash", {"stdout": "test", "exit_code": 0, "stderr": "", "timeout": False}),
        ("read", {"lines": 10, "file_path": "/test.py", "content": "test content"}),
        ("write", {"file_path": "/test.py", "success": True}),
        ("edit", {"success": True, "replacements_made": 2, "file_path": "/test.py"}),
        ("grep", {"total_matches": 5, "truncated": False, "matches": []}),
    ]

    for tool_name, result in test_cases:
        formatted = _format_tool_result(tool_name, result)

        # Assert no emoji characters present
        for emoji in emoji_chars:
            assert emoji not in formatted, f"Found emoji {emoji} in {tool_name} output"

        # Should still contain key information
        assert len(formatted) > 0, f"{tool_name} output is empty"


def test_minimal_style_readability():
    """Verify output is still readable and informative."""

    bash_result = {
        "stdout": "File created successfully\nDone!",
        "stderr": "",
        "exit_code": 0,
        "timeout": False,
    }

    formatted = _format_tool_result("bash", bash_result)

    # Key info should be present
    assert "exit 0" in formatted.lower() or "exit code: 0" in formatted
    assert "File created successfully" in formatted

    # Should be concise
    assert len(formatted.split("\n")) < 10  # Not too verbose


def test_error_cases_still_clear():
    """Verify errors are still clearly communicated."""

    bash_error = {
        "stdout": "",
        "stderr": "Command not found",
        "exit_code": 127,
        "timeout": False,
    }

    formatted = _format_tool_result("bash", bash_error)

    # Error should be obvious
    assert "127" in formatted
    assert "Command not found" in formatted

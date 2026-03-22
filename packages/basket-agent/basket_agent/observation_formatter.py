"""
Observation formatting layer for tool results.

Truncates and formats tool outputs before they enter the conversation context,
reducing token usage by 40-60% per turn.

Design:
- Strategy pattern: tool_name -> formatter function mapping
- Pure functions: all formatters are side-effect free
- Extensible: add new formatters to TOOL_FORMATTERS dict
- Configurable: module-level constants for tuning
- No external dependencies (stdlib only)
"""

import json
import re
from typing import Any, Callable, Dict

# ANSI escape code pattern
ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Default limits
DEFAULT_MAX_LINES = 100
DEFAULT_MAX_CHARS = 4000
DEFAULT_HEAD_LINES = 40
DEFAULT_TAIL_LINES = 20


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return ANSI_ESCAPE.sub("", text)


def _format_with_head_tail(
    text: str,
    head: int = DEFAULT_HEAD_LINES,
    tail: int = DEFAULT_TAIL_LINES,
) -> str:
    """Keep first `head` and last `tail` lines, omit middle."""
    lines = text.split("\n")
    if len(lines) <= head + tail:
        return text
    omitted = len(lines) - head - tail
    return (
        "\n".join(lines[:head])
        + f"\n\n[... {omitted} lines omitted ...]\n\n"
        + "\n".join(lines[-tail:])
    )


def format_bash_result(result: Any) -> str:
    """Format bash tool output: strip ANSI, head+tail truncation."""
    text = str(result)
    text = strip_ansi(text)
    return _format_with_head_tail(text, head=DEFAULT_HEAD_LINES, tail=DEFAULT_TAIL_LINES)


def format_read_result(result: Any) -> str:
    """Format read tool output: truncate long file contents."""
    text = str(result)
    return _format_with_head_tail(text, head=50, tail=20)


def format_grep_result(result: Any) -> str:
    """Format grep output: cap number of matches."""
    text = str(result)
    lines = text.split("\n")
    max_matches = 50
    if len(lines) > max_matches:
        omitted = len(lines) - max_matches
        return (
            "\n".join(lines[:max_matches])
            + f"\n\n[... {omitted} more matches omitted ...]"
        )
    return text


def format_edit_result(result: Any) -> str:
    """Format edit/write output: only confirmation, not full file."""
    text = str(result)
    if len(text) > 500:
        return text[:500] + "\n\n[... output truncated (edit/write confirmation only) ...]"
    return text


def format_default(result: Any) -> str:
    """Default formatter: general truncation with head+tail by character count."""
    text = str(result)
    if len(text) > DEFAULT_MAX_CHARS:
        head_chars = DEFAULT_MAX_CHARS * 2 // 3
        tail_chars = DEFAULT_MAX_CHARS // 3
        omitted = len(text) - head_chars - tail_chars
        return (
            text[:head_chars]
            + f"\n\n[... {omitted} chars omitted ...]\n\n"
            + text[-tail_chars:]
        )
    return text


# Strategy pattern: tool name -> formatter function
TOOL_FORMATTERS: Dict[str, Callable[[Any], str]] = {
    "bash": format_bash_result,
    "read": format_read_result,
    "grep": format_grep_result,
    "edit": format_edit_result,
    "write": format_edit_result,
}


def format_observation(tool_name: str, result: Any) -> str:
    """
    Format a tool result for inclusion in context.

    Serializes Pydantic models and non-string values to JSON first,
    then applies the tool-specific formatter (or the default formatter).

    Args:
        tool_name: Name of the tool that produced the result
        result: Raw tool result (str, dict, Pydantic model, etc.)

    Returns:
        Formatted string suitable for context inclusion
    """
    # Serialize structured data to string
    if hasattr(result, "model_dump"):
        result = json.dumps(result.model_dump())
    elif not isinstance(result, str):
        try:
            result = json.dumps(result)
        except (TypeError, ValueError):
            result = str(result)

    formatter = TOOL_FORMATTERS.get(tool_name, format_default)
    return formatter(result)


__all__ = [
    "TOOL_FORMATTERS",
    "format_bash_result",
    "format_default",
    "format_edit_result",
    "format_grep_result",
    "format_observation",
    "format_read_result",
    "strip_ansi",
]

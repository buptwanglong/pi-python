"""TUI interaction mode (deprecated — use basket tui or basket tui-native)."""

import logging
from typing import Any, Optional, Tuple

from .base import InteractionMode

logger = logging.getLogger(__name__)

_MSG = (
    "Textual TUI was removed. Use 'basket tui' or 'basket tui-native' "
    "to run the terminal-native TUI with the gateway."
)

# Max lengths for tool result display (used by format_tool_result)
_TOOL_RESULT_STDOUT_MAX = 1000
_TOOL_RESULT_FALLBACK_MAX = 500
_TOOL_RESULT_DICT_STR_MAX = 300


def format_tool_result(tool_name: str, result: Any) -> str:
    """
    Format tool result for TUI display (minimal style, no emojis).

    Args:
        tool_name: Name of the tool (bash, read, write, edit, grep, etc.)
        result: Raw result from tool (dict or other).

    Returns:
        Human-readable string for display.
    """
    if result is None:
        return "Tool executed successfully (no output)"

    if not isinstance(result, dict):
        s = str(result)
        if len(s) <= _TOOL_RESULT_FALLBACK_MAX:
            return s
        return s[:_TOOL_RESULT_FALLBACK_MAX] + "... (truncated)"

    if tool_name == "bash":
        stdout = result.get("stdout", "") or ""
        stderr = result.get("stderr", "") or ""
        exit_code = result.get("exit_code", 0)
        timeout = result.get("timeout", False)
        if len(stdout) > _TOOL_RESULT_STDOUT_MAX:
            stdout = stdout[:_TOOL_RESULT_STDOUT_MAX] + "... (truncated)"
        parts = [f"exit {exit_code}"]
        if timeout:
            parts.append("(timed out)")
        if stdout:
            parts.append(stdout.rstrip())
        if stderr:
            parts.append(stderr.rstrip())
        return "\n".join(parts)

    if tool_name == "read":
        file_path = result.get("file_path", "")
        lines = result.get("lines", 0)
        content = result.get("content", "")
        return f"Read {lines} lines from {file_path}\n{content}"

    if tool_name == "write":
        file_path = result.get("file_path", "")
        if result.get("success"):
            return f"Wrote file: {file_path}"
        return result.get("error", "Write failed") or f"Write failed: {file_path}"

    if tool_name == "edit":
        file_path = result.get("file_path", "")
        if result.get("success"):
            n = result.get("replacements_made", 0)
            return f"{n} replacement(s) in {file_path}"
        return result.get("error", "Edit failed") or f"Edit failed: {file_path}"

    if tool_name == "grep":
        total = result.get("total_matches", 0)
        matches = result.get("matches", [])
        line = f"{total} match(es)"
        if matches:
            preview = " ".join(m.get("file_path", "") for m in matches[:10])
            line += f" — {preview}"
        return line

    # Unknown tool: str(dict), truncated
    s = str(result)
    if len(s) <= _TOOL_RESULT_DICT_STR_MAX:
        return s
    return s[:_TOOL_RESULT_DICT_STR_MAX] + "... (truncated)"


# Alias for tests/docs that used _format_tool_result
_format_tool_result = format_tool_result


async def run_tui_mode(coding_agent: Any, max_cols: Optional[int] = None) -> None:
    """Deprecated. Use ``basket tui`` or ``basket tui-native`` instead."""
    raise NotImplementedError(_MSG)


class TUIMode(InteractionMode):
    """TUI interaction mode (deprecated).

    Use the CLI: ``basket tui`` or ``basket tui-native`` instead.
    """

    def __init__(self, agent: Any, max_columns: Optional[int] = None) -> None:
        super().__init__(agent)
        self.max_columns = max_columns

    def setup_publisher_adapter(self) -> Tuple[Any, Any]:
        raise NotImplementedError(_MSG)

    async def run(self) -> None:
        raise NotImplementedError(_MSG)

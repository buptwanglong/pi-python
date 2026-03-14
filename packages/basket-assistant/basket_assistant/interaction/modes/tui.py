"""TUI interaction mode."""

import logging
from typing import Any, Optional, Tuple

from basket_tui.app import PiCodingAgentApp

from basket_assistant.core.events.publisher import EventPublisher
from basket_assistant.adapters.tui import TUIAdapter

from .base import InteractionMode

logger = logging.getLogger(__name__)


class TUIMode(InteractionMode):
    """TUI interaction mode with Textual UI.

    This mode provides a terminal UI interface with:
    - Textual-based UI with markdown rendering
    - Multi-line input support
    - Streaming display of agent output
    - Event bus integration for reactive updates

    Example:
        >>> mode = TUIMode(agent, max_columns=120)
        >>> await mode.initialize()
        >>> await mode.run()
    """

    def __init__(self, agent: Any, max_columns: Optional[int] = None) -> None:
        """Initialize TUI mode.

        Args:
            agent: AssistantAgent instance
            max_columns: Maximum columns for text wrapping (None = no limit)
        """
        super().__init__(agent)
        self.max_columns = max_columns

        # Create TUI app early (before initialize) so it's available
        self.tui_app = PiCodingAgentApp(
            coding_agent=agent,
            max_cols=max_columns
        )

    def setup_publisher_adapter(self) -> Tuple[Any, Any]:
        """Set up publisher and TUI adapter.

        Returns:
            Tuple of (EventPublisher, TUIAdapter)
        """
        publisher = EventPublisher(self.agent)
        adapter = TUIAdapter(publisher, self.tui_app.event_bus)
        return publisher, adapter

    async def _on_user_input(self, event: Any) -> None:
        """Handle user input from TUI.

        Args:
            event: UserInputEvent with text attribute
        """
        user_input = event.text.strip()

        # Ignore empty input
        if not user_input:
            return

        # Process and run agent
        await self.process_and_run_agent(user_input, stream=True)

    async def run(self) -> None:
        """Run the TUI event loop.

        This method:
        1. Sets up input handler for TUI events
        2. Starts the Textual app
        3. Runs until user quits the TUI

        The TUI handles all user interaction through its event bus.
        """
        logger.info("Starting TUI mode")

        # Set input handler
        self.tui_app.set_input_handler(self._on_user_input)

        # Run TUI app (blocks until quit)
        await self.tui_app.run_async()

        logger.info("TUI mode ended")


# Standalone function for backward compatibility and tests

# Max lengths for tool result display
_TOOL_RESULT_STDOUT_MAX = 1000
_TOOL_RESULT_FALLBACK_MAX = 500
_TOOL_RESULT_DICT_STR_MAX = 300


def format_tool_result(tool_name: str, result: Any) -> str:
    """
    Format tool result for TUI display (minimal style, no emojis).

    This function is used by tests and backward compatibility.

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
            preview = " ".join(
                m.get("file_path", "") for m in matches[:10]
            )
            line += f" — {preview}"
        return line

    # Unknown tool: str(dict), truncated
    s = str(result)
    if len(s) <= _TOOL_RESULT_DICT_STR_MAX:
        return s
    return s[:_TOOL_RESULT_DICT_STR_MAX] + "... (truncated)"


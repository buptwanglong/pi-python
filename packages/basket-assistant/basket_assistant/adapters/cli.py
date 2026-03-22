"""CLI adapter for printing events to stdout."""

import logging
from typing import Any, Dict, List

from basket_agent.types import AgentEventToolCallStart, AgentEventToolCallEnd

from .base import EventAdapter

logger = logging.getLogger(__name__)


# Tool name -> list of argument keys to show in verbose output
_TOOL_ARG_KEYS: Dict[str, List[str]] = {
    "bash": ["command"],
    "read": ["file_path"],
    "write": ["file_path"],
    "edit": ["file_path", "old_string", "new_string"],
    "grep": ["pattern", "path"],
    "web_search": ["query"],
    "web_fetch": ["url"],
    "ask_user_question": ["question"],
    "task": ["subagent_type", "prompt"],
    "skill": ["skill_id", "message"],
}


def _format_tool_args(tool_name: str, args: Dict[str, Any], max_len: int = 80) -> str:
    """Format tool arguments for display.

    Args:
        tool_name: Name of the tool
        args: Tool arguments dict
        max_len: Maximum length for each argument value

    Returns:
        Formatted string like "command='ls -la'"
    """
    if not args:
        return ""

    keys = _TOOL_ARG_KEYS.get(tool_name, [])
    if not keys:
        # Show first key
        keys = list(args.keys())[:1]

    parts = []
    for key in keys:
        if key in args:
            value = args[key]
            if isinstance(value, str) and len(value) > max_len:
                value = value[:max_len - 3] + "..."
            parts.append(f"{key}={value!r}")

    return " ".join(parts)


class CLIAdapter(EventAdapter):
    """CLI adapter that prints events to stdout.

    This adapter is used in interactive CLI mode to display LLM output and
    tool calls as they happen.

    Args:
        publisher: The EventPublisher to subscribe to
        verbose: Whether to print verbose tool call information
    """

    def __init__(self, publisher: Any, verbose: bool = False):
        """Initialize the CLI adapter.

        Args:
            publisher: The EventPublisher to subscribe to
            verbose: Whether to print verbose tool call information
        """
        self.verbose = verbose
        super().__init__(publisher)

    def _setup_subscriptions(self) -> None:
        """Subscribe to events we care about."""
        self.publisher.subscribe("text_delta", self._on_text_delta)
        self.publisher.subscribe("agent_tool_call_start", self._on_tool_call_start)
        self.publisher.subscribe("agent_tool_call_end", self._on_tool_call_end)

    def _on_text_delta(self, event: Any) -> None:
        """Handle text_delta event."""
        if hasattr(event, "delta") and event.delta:
            print(event.delta, end="", flush=True)

    def _on_tool_call_start(self, event: AgentEventToolCallStart) -> None:
        """Handle tool_call_start event."""
        logger.info("Tool call: %s", event.tool_name)

        if self.verbose:
            args_str = _format_tool_args(event.tool_name, event.arguments or {})
            if args_str:
                print(f"\n[Tool: {event.tool_name} {args_str}]", flush=True)
            else:
                print(f"\n[Tool: {event.tool_name}]", flush=True)

    def _on_tool_call_end(self, event: AgentEventToolCallEnd) -> None:
        """Handle tool_call_end event."""
        if event.error:
            print(f"\n[Error: {event.error}]", flush=True)
            logger.warning("Tool call failed: %s - %s", event.tool_name, event.error)

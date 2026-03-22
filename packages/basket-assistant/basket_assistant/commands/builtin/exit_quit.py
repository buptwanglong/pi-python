"""Builtin /exit and /quit commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from basket_assistant.commands.registry import CommandRegistry


def handle_exit(agent: Any, args: str) -> tuple[bool, str]:
    """Handle /exit and /quit — session ends via ProcessResult(action=\"exit\")."""
    return True, ""


def register(registry: CommandRegistry, agent: Any) -> None:
    """Register /exit and /quit with the command registry."""

    def run(args: str) -> tuple[bool, str]:
        return handle_exit(agent, args)

    registry.register(
        name="exit",
        handler=run,
        description="Exit the assistant",
        usage="/exit",
        aliases=["quit", "/exit", "/quit"],
    )

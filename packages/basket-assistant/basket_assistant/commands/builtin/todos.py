"""Builtin /todos command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from basket_assistant.commands.registry import CommandRegistry


def handle_todos(agent: Any, args: str) -> tuple[bool, str]:
    """Handle /todos command."""
    args = args.strip().lower()

    if args == "":
        agent._todo_show_full = not agent._todo_show_full
        mode = "full" if agent._todo_show_full else "compact"
        print(f"Todo list display mode: {mode}")
        return True, ""
    if args == "on":
        agent._todo_show_full = True
        print("Todo list display mode: full")
        return True, ""
    if args == "off":
        agent._todo_show_full = False
        print("Todo list display mode: compact")
        return True, ""
    return False, "Usage: /todos [on|off]"


def register(registry: CommandRegistry, agent: Any) -> None:
    """Register /todos with the command registry."""

    def run(args: str) -> tuple[bool, str]:
        return handle_todos(agent, args)

    registry.register(
        name="todos",
        handler=run,
        description="Toggle or set todo list display mode",
        usage="/todos [on|off]",
        aliases=["todos", "/todos"],
    )

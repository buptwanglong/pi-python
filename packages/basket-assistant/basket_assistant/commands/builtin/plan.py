"""Builtin /plan command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from basket_assistant.commands.registry import CommandRegistry


def handle_plan(agent: Any, args: str) -> tuple[bool, str]:
    """Handle /plan command."""
    args = args.strip().lower()

    if args == "":
        agent.plan_mode = not agent.plan_mode
        status = "enabled" if agent.plan_mode else "disabled"
        print(f"Plan mode: {status}")
        return True, ""
    if args == "on":
        agent.plan_mode = True
        print("Plan mode: enabled")
        return True, ""
    if args == "off":
        agent.plan_mode = False
        print("Plan mode: disabled")
        return True, ""
    return False, "Usage: /plan [on|off]"


def register(registry: CommandRegistry, agent: Any) -> None:
    """Register /plan with the command registry."""

    def run(args: str) -> tuple[bool, str]:
        return handle_plan(agent, args)

    registry.register(
        name="plan",
        handler=run,
        description="Toggle or set plan mode",
        usage="/plan [on|off]",
        aliases=["plan", "/plan"],
    )

"""Builtin /settings command."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from basket_assistant.commands.registry import CommandRegistry


def handle_settings(agent: Any, args: str) -> tuple[bool, str]:
    """Handle /settings command."""
    settings_dict = agent.settings.to_dict()
    formatted = json.dumps(settings_dict, indent=2)
    print(f"Current settings:\n{formatted}")
    return True, ""


def register(registry: CommandRegistry, agent: Any) -> None:
    """Register /settings with the command registry."""

    def run(args: str) -> tuple[bool, str]:
        return handle_settings(agent, args)

    registry.register(
        name="settings",
        handler=run,
        description="Show current settings",
        usage="/settings",
        aliases=["settings", "/settings"],
    )

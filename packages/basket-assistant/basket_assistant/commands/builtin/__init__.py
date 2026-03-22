"""Builtin interactive slash-commands: one module per command, each with ``register``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import (
    clear,
    compact,
    exit_quit,
    model,
    plan,
    plugin,
    session_open,
    sessions,
    settings,
    todos,
)
from . import help as help_cmd

if TYPE_CHECKING:
    from basket_assistant.commands.registry import CommandRegistry


def register_builtin_commands(registry: CommandRegistry, agent: Any) -> None:
    """Register all builtin commands with the registry."""
    help_cmd.register(registry, agent)
    settings.register(registry, agent)
    todos.register(registry, agent)
    plan.register(registry, agent)
    sessions.register(registry, agent)
    session_open.register(registry, agent)
    clear.register(registry, agent)
    compact.register(registry, agent)
    model.register(registry, agent)
    plugin.register(registry, agent)
    exit_quit.register(registry, agent)


__all__ = ["register_builtin_commands"]

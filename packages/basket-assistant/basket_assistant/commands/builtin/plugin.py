"""Builtin /plugin command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from basket_assistant.agent._protocol import AssistantAgentProtocol
    from basket_assistant.commands.registry import CommandRegistry


async def handle_plugin(agent: AssistantAgentProtocol, args: str) -> tuple[bool, str]:
    """Handle /plugin command — manage installed plugins."""
    parts = args.strip().split(maxsplit=1)
    if not parts:
        return False, (
            "Usage: /plugin <list|install|uninstall>\n"
            "  /plugin list                     List installed plugins\n"
            "  /plugin install <source> [ref]   Install from local dir, .zip/.tar, https URL, or git URL\n"
            "                                   Optional ref: second token or URL#tag (git only)\n"
            "  /plugin uninstall <name>         Uninstall by name"
        )

    subcmd = parts[0].lower()
    subcmd_args = parts[1] if len(parts) > 1 else ""

    from basket_assistant.plugins.commands import (
        plugin_install,
        plugin_list,
        plugin_uninstall,
    )

    progress_sink = getattr(agent, "_plugin_install_progress_sink", None)

    if subcmd == "list":
        result = await plugin_list()
        if not result.plugins:
            return True, "No plugins installed."
        lines = [f"{len(result.plugins)} plugin(s) installed:"]
        for p in result.plugins:
            desc = f" — {p.description}" if p.description else ""
            lines.append(f"  {p.name} v{p.version}{desc}")
        return True, "\n".join(lines)

    if subcmd == "install":
        if not subcmd_args.strip():
            return (
                False,
                "Usage: /plugin install <path|zip|https-url|git-url> [git-ref]",
            )
        result = await plugin_install(
            source=subcmd_args.strip(),
            progress_sink=progress_sink if callable(progress_sink) else None,
        )
        if result.success:
            if progress_sink is not None and callable(progress_sink):
                return True, ""
            return True, result.message
        return False, result.error

    if subcmd == "uninstall":
        if not subcmd_args.strip():
            return False, "Usage: /plugin uninstall <name>"
        result = await plugin_uninstall(name=subcmd_args.strip())
        if result.success:
            return True, result.message
        return False, result.error

    return False, (
        f"Unknown subcommand: {subcmd}\n"
        "Usage: /plugin <list|install|uninstall>"
    )


def register(registry: CommandRegistry, agent: AssistantAgentProtocol) -> None:
    """Register /plugin with the command registry."""

    async def run(args: str) -> tuple[bool, str]:
        return await handle_plugin(agent, args)

    registry.register(
        name="plugin",
        handler=run,
        description="Manage installed plugins",
        usage="/plugin <list|install|uninstall>",
        aliases=["plugin", "/plugin"],
    )

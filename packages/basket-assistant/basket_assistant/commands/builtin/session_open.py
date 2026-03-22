"""Builtin /open command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from basket_assistant.commands.registry import CommandRegistry


async def handle_open(agent: Any, args: str) -> tuple[bool, str]:
    """Handle /open command."""
    session_id = args.strip()

    if not session_id:
        return False, "Usage: /open <session_id>"

    if agent.session_manager is None:
        return False, "Session management not available"

    try:
        messages = await agent.session_manager.load_session(session_id)
        agent.load_history(messages)
        print(f"Switched to session: {session_id}")
        return True, ""
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Failed to load session: {e}"


def register(registry: CommandRegistry, agent: Any) -> None:
    """Register /open with the command registry."""

    async def run(args: str) -> tuple[bool, str]:
        return await handle_open(agent, args)

    registry.register(
        name="open",
        handler=run,
        description="Switch to a different session",
        usage="/open <session_id>",
        aliases=["open", "/open"],
    )

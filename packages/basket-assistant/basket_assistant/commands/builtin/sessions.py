"""Builtin /sessions command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from basket_assistant.commands.registry import CommandRegistry
    from basket_assistant.agent._protocol import AssistantAgentProtocol


async def handle_sessions(agent: AssistantAgentProtocol, args: str) -> tuple[bool, str]:
    """Handle /sessions command."""
    if agent.session_manager is None:
        return False, "Session management not available"

    sessions = await agent.session_manager.list_sessions()

    if not sessions:
        print("No sessions found.")
        return True, ""

    print("Available sessions:")
    for session in sessions:
        session_id = session.get("id", "unknown")
        created_at = session.get("created_at", "unknown")
        print(f"  {session_id} (created: {created_at})")

    return True, ""


def register(registry: CommandRegistry, agent: Any) -> None:
    """Register /sessions with the command registry."""

    async def run(args: str) -> tuple[bool, str]:
        return await handle_sessions(agent, args)

    registry.register(
        name="sessions",
        handler=run,
        description="List all available sessions",
        usage="/sessions",
        aliases=["sessions", "/sessions"],
    )

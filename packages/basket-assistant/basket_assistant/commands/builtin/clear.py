"""Builtin /clear command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from basket_assistant.agent._protocol import AssistantAgentProtocol
    from basket_assistant.commands.registry import CommandRegistry


async def handle_clear(agent: AssistantAgentProtocol, args: str) -> tuple[bool, str]:
    """Handle /clear command — reset conversation context."""
    old_msg_count = len(agent.context.messages)

    agent.context.messages = []
    agent._current_todos = []
    agent._pending_asks = []

    if agent.session_manager is not None:
        try:
            model_id = agent.model.model_id
            new_session_id = await agent.session_manager.create_session(
                model_id=model_id,
            )
            agent._session_id = new_session_id
            print(
                f"Context cleared ({old_msg_count} messages removed). "
                f"New session: {new_session_id}"
            )
        except Exception as e:
            agent._session_id = None
            print(
                f"Context cleared ({old_msg_count} messages removed). "
                f"Warning: failed to create new session: {e}"
            )
    else:
        agent._session_id = None
        print(f"Context cleared ({old_msg_count} messages removed).")

    return True, ""


def register(registry: CommandRegistry, agent: AssistantAgentProtocol) -> None:
    """Register /clear with the command registry."""

    async def run(args: str) -> tuple[bool, str]:
        return await handle_clear(agent, args)

    registry.register(
        name="clear",
        handler=run,
        description="Clear conversation context and start fresh",
        usage="/clear",
        aliases=["clear", "/clear"],
    )

"""Builtin /compact command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from basket_assistant.agent._protocol import AssistantAgentProtocol
    from basket_assistant.commands.registry import CommandRegistry


async def handle_compact(agent: AssistantAgentProtocol, args: str) -> tuple[bool, str]:
    """Handle /compact command — compress conversation context."""
    from basket_agent.context_manager import compact_context, estimate_context_tokens

    context_window = agent.model.context_window

    before_msgs = len(agent.context.messages)
    before_tokens = estimate_context_tokens(agent.context)

    new_context, was_compacted = compact_context(
        agent.context, context_window
    )

    if not was_compacted:
        usage_pct = (before_tokens / context_window * 100) if context_window else 0
        print(
            f"No compaction needed. Context: {before_msgs} messages, "
            f"~{before_tokens:,} tokens ({usage_pct:.0f}% of {context_window:,} window)."
        )
        return True, ""

    agent.context = new_context

    after_msgs = len(new_context.messages)
    after_tokens = estimate_context_tokens(new_context)
    saved_msgs = before_msgs - after_msgs
    saved_tokens = before_tokens - after_tokens
    usage_pct = (after_tokens / context_window * 100) if context_window else 0

    print(
        f"Context compacted: {before_msgs} → {after_msgs} messages "
        f"(-{saved_msgs}), ~{before_tokens:,} → ~{after_tokens:,} tokens "
        f"(-{saved_tokens:,}). Now at {usage_pct:.0f}% of {context_window:,} window."
    )
    return True, ""


def register(registry: CommandRegistry, agent: AssistantAgentProtocol) -> None:
    """Register /compact with the command registry."""

    async def run(args: str) -> tuple[bool, str]:
        return await handle_compact(agent, args)

    registry.register(
        name="compact",
        handler=run,
        description="Compress conversation context to free up space",
        usage="/compact",
        aliases=["compact", "/compact"],
    )

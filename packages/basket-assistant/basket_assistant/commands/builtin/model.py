"""Builtin /model command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from basket_assistant.agent._protocol import AssistantAgentProtocol
    from basket_assistant.commands.registry import CommandRegistry


async def handle_model(agent: AssistantAgentProtocol, args: str) -> tuple[bool, str]:
    """Handle /model command — show current model or switch to a new one."""
    args = args.strip()

    if not args:
        provider = agent.model.provider
        model_id = agent.model.model_id
        ctx_window = getattr(agent.model, "context_window", "unknown")
        print(f"Current model: {provider}/{model_id} (context_window={ctx_window})")
        return True, ""

    parts = args.split()
    model_spec = parts[0]

    if "/" not in model_spec:
        return False, (
            "Usage: /model <provider>/<model_id> [--context-window <int>]\n"
            "Example: /model openai/gpt-4o"
        )

    provider, model_id = model_spec.split("/", 1)
    if not provider or not model_id:
        return False, (
            "Usage: /model <provider>/<model_id> [--context-window <int>]\n"
            "Example: /model openai/gpt-4o"
        )

    context_window = agent.model.context_window
    max_tokens = agent.model.max_tokens
    base_url = getattr(agent.model, "base_url", None) or getattr(
        agent.model, "baseUrl", None
    )

    i = 1
    while i < len(parts):
        if parts[i] == "--context-window" and i + 1 < len(parts):
            try:
                context_window = int(parts[i + 1])
            except ValueError:
                return False, f"Invalid context-window value: {parts[i + 1]}"
            i += 2
        else:
            i += 1

    try:
        from basket_ai.api import get_model

        model_kwargs = {
            "context_window": context_window,
            "max_tokens": max_tokens,
        }
        if base_url:
            model_kwargs["base_url"] = str(base_url)

        new_model = get_model(provider, model_id, **model_kwargs)

        old_provider = agent.model.provider
        old_model_id = agent.model.model_id

        agent.model = new_model
        if hasattr(agent, "agent") and hasattr(agent.agent, "model"):
            agent.agent.model = new_model

        print(
            f"Model switched: {old_provider}/{old_model_id} → {provider}/{model_id} "
            f"(context_window={context_window})"
        )
        return True, ""

    except Exception as e:
        return False, f"Failed to switch model: {e}"


def register(registry: CommandRegistry, agent: AssistantAgentProtocol) -> None:
    """Register /model with the command registry."""

    async def run(args: str) -> tuple[bool, str]:
        return await handle_model(agent, args)

    registry.register(
        name="model",
        handler=run,
        description="Show current model or switch to a different one",
        usage="/model [provider/model_id] [--context-window N]",
        aliases=["model", "/model"],
    )

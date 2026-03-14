"""Resolve LLM config for a named agent (multi-agent)."""

from __future__ import annotations

from basket_assistant.core import AgentConfigResolver, SettingsManager


def get_agent_config(agent_name: str | None = None) -> dict[str, str | int | None]:
    """
    Load settings and return model config for the given agent.

    Args:
        agent_name: Agent name (None = main/default agent, reads BASKET_AGENT env if None)

    Returns:
        Dict with provider, model_id, base_url, context_window, max_tokens
    """
    settings_manager = SettingsManager()
    settings = settings_manager.load()

    resolver = AgentConfigResolver(settings)
    agent_key = resolver.resolve_agent_key(agent_name)

    return resolver.get_model_config(agent_key)


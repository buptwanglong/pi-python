"""Resolve LLM config for a named agent (multi-agent)."""

from __future__ import annotations

from basket_assistant.core.agent_config import AgentConfig
from basket_assistant.core.settings import load_settings


def get_agent_config(agent_name: str | None = None) -> AgentConfig:
    """Load settings and return config for the given agent (None = main/default agent).
    If agent_name is None, uses env BASKET_AGENT (set by CLI --agent) when present.
    """
    import os

    if agent_name is None:
        agent_name = os.environ.get("BASKET_AGENT") or None
    settings = load_settings()
    return settings.resolve_agent(agent_name)

"""
AgentConfigResolver: resolves agent configuration and model selection
for multi-agent support.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from .models import Settings


class AgentConfigResolver:
    """Resolves agent configuration and model selection for multi-agent support."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def resolve_agent_key(self, agent_name: Optional[str] = None) -> str:
        """
        Resolve agent name to agent key.

        Args:
            agent_name: Agent name from CLI/env or None for default

        Returns:
            Agent key (default_agent if agent_name is None/empty)
        """
        # Check environment variable first
        if agent_name is None:
            agent_name = os.environ.get("BASKET_AGENT") or None

        # Use default_agent if no agent_name specified
        return (agent_name or "").strip() or self.settings.default_agent or "default"

    def has_agent_model_override(self, agent_key: str) -> bool:
        """Check if agent has a model override in settings."""
        if agent_key not in self.settings.agents:
            return False
        agent_cfg = self.settings.agents[agent_key]
        return (
            agent_cfg.model is not None
            and isinstance(agent_cfg.model, dict)
            and len(agent_cfg.model) > 0
        )

    def get_model_config(self, agent_key: str) -> Dict[str, Any]:
        """
        Get model configuration for agent.

        Args:
            agent_key: Agent key

        Returns:
            Dict with provider, model_id, base_url, context_window, max_tokens
        """
        # Check for agent-specific model override
        if self.has_agent_model_override(agent_key):
            agent_model = self.settings.agents[agent_key].model or {}
            top = self.settings.model
            return {
                "provider": agent_model.get("provider", top.provider),
                "model_id": agent_model.get("model_id", top.model_id),
                "base_url": agent_model.get("base_url") or top.base_url,
                "context_window": agent_model.get("context_window", top.context_window),
                "max_tokens": agent_model.get("max_tokens", top.max_tokens),
            }

        # Use top-level model settings
        return {
            "provider": self.settings.model.provider,
            "model_id": self.settings.model.model_id,
            "base_url": self.settings.model.base_url,
            "context_window": self.settings.model.context_window,
            "max_tokens": self.settings.model.max_tokens,
        }

    def get_sessions_dir(self, agent_key: str) -> Path:
        """
        Get sessions directory for agent.

        Args:
            agent_key: Agent key

        Returns:
            Path to sessions directory (per-agent or global)
        """
        if agent_key and agent_key in self.settings.agents:
            # Per-agent sessions: agents/<name>/sessions/
            from ..agent.prompts import get_agent_root

            agent_root = get_agent_root(self.settings, agent_key)
            return agent_root / "sessions"

        # Global sessions directory
        return Path(self.settings.sessions_dir).expanduser()

# Patch module: multi-agent settings support.
# Integrate into settings.py: add AgentConfig, agents dict, default_agent, resolve_agent.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentConfig:
    """Per-agent LLM config (provider, base_url, api_key, etc.)."""
    provider: str = "openai"
    base_url: str = ""
    api_key: str = ""
    model: str | None = None
    temperature: float | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AgentConfig":
        return cls(
            provider=d.get("provider", "openai"),
            base_url=d.get("base_url", ""),
            api_key=d.get("api_key", ""),
            model=d.get("model"),
            temperature=d.get("temperature"),
        )


def migrate_legacy_to_agents(raw: dict[str, Any]) -> dict[str, Any]:
    """If raw has top-level api_key/base_url but no agents, build agents[\"default\"]."""
    if "agents" in raw and raw["agents"]:
        return raw
    if not raw.get("api_key") and not raw.get("base_url"):
        return raw
    agents: dict[str, Any] = {
        "default": {
            "provider": raw.get("provider", "openai"),
            "base_url": raw.get("base_url", ""),
            "api_key": raw.get("api_key", ""),
            "model": raw.get("model"),
            "temperature": raw.get("temperature"),
        }
    }
    out = dict(raw)
    out["agents"] = agents
    out["default_agent"] = out.get("default_agent", "default")
    return out

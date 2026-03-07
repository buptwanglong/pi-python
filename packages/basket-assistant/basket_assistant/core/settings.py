"""Load and resolve settings (multi-agent: agents + default_agent main agent)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from basket_assistant.core.agent_config import (
    AgentConfig,
    migrate_legacy_to_agents,
    resolve_agent_config,
)

# Default config path: env BASKET_SETTINGS_PATH or ~/.basket/settings.json
def _default_settings_path() -> Path:
    env = os.environ.get("BASKET_SETTINGS_PATH")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".basket" / "settings.json"


@dataclass
class Settings:
    """Settings with multi-agent: agents dict and default_agent (main agent)."""

    agents: dict[str, AgentConfig] = field(default_factory=dict)
    default_agent: str = "default"
    workspace: str | None = None
    # Legacy top-level options (optional; often mirrored in agents)
    provider: str = "openai"
    base_url: str = ""
    api_key: str = ""
    model: str | None = None
    temperature: float | None = None

    def resolve_agent(self, name: str | None = None) -> AgentConfig:
        """Resolve agent by name; None or empty uses default_agent (main agent)."""
        return resolve_agent_config(self.agents, self.default_agent, name)

    @property
    def main_agent_config(self) -> AgentConfig:
        """Config for the main (default) agent."""
        return self.agents[self.default_agent]


def load_settings(path: Path | str | None = None) -> Settings:
    """Load settings.json; requires agents and default_agent (main agent). Migrates legacy top-level api_key/base_url into agents[\"default\"]."""
    path = Path(path) if path else _default_settings_path()
    if not path.exists():
        raise FileNotFoundError(f"Settings file not found: {path}")
    with open(path, encoding="utf-8") as f:
        raw: dict[str, Any] = json.load(f)
    raw = migrate_legacy_to_agents(raw)
    if not raw.get("agents") or not isinstance(raw["agents"], dict):
        raise ValueError("settings.json must have non-empty 'agents' (main agent and others).")
    default_agent = raw.get("default_agent")
    if not default_agent or not isinstance(default_agent, str):
        raise ValueError("settings.json must have 'default_agent' (main agent name).")
    agents: dict[str, AgentConfig] = {}
    for name, cfg in raw["agents"].items():
        if not isinstance(cfg, dict):
            continue
        agents[name] = AgentConfig.from_dict(cfg)
    if default_agent not in agents:
        raise ValueError(f"default_agent {default_agent!r} must exist in agents: {list(agents.keys())}")
    main = agents[default_agent]
    return Settings(
        agents=agents,
        default_agent=default_agent,
        workspace=raw.get("workspace"),
        provider=main.provider,
        base_url=main.base_url,
        api_key=main.api_key,
        model=main.model,
        temperature=main.temperature,
    )

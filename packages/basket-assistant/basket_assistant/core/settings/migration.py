"""
Legacy settings migration and settings loading from JSON files.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

from .models import AgentConfig, Settings

logger = logging.getLogger(__name__)


def migrate_legacy_to_agents(raw: dict[str, Any]) -> dict[str, Any]:
    """If raw has top-level api_key/base_url but no agents, build agents["default"]."""
    if raw.get("agents") and isinstance(raw["agents"], dict):
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


def resolve_agent_config(
    agents: dict[str, AgentConfig],
    default_agent: str,
    name: str | None,
) -> AgentConfig:
    """Resolve agent name to config; name None or empty uses default_agent (main agent)."""
    key = (name or "").strip() or default_agent
    if key not in agents:
        raise KeyError(f"Unknown agent: {key!r}. Known: {list(agents.keys())}")
    return agents[key]


def load_settings(path: Path | str | None = None) -> Settings:
    """
    Load settings from JSON file with validation.

    Validates that 'agents' and 'default_agent' exist and are valid.

    Args:
        path: Optional path to settings file (uses default if None)

    Returns:
        Settings instance

    Raises:
        FileNotFoundError: If settings file doesn't exist
        ValueError: If agents or default_agent are missing/invalid
    """
    if path is None:
        env_path = os.environ.get("BASKET_SETTINGS_PATH")
        path = Path(env_path).expanduser() if env_path else Path.home() / ".basket" / "settings.json"
    else:
        path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Settings file not found: {path}")

    with open(path, encoding="utf-8") as f:
        raw: dict[str, Any] = json.load(f)

    raw = migrate_legacy_to_agents(raw)

    if not raw.get("agents") or not isinstance(raw["agents"], dict):
        raise ValueError(
            "settings.json must have non-empty 'agents' (main agent and others)."
        )

    default_agent = raw.get("default_agent")
    if not default_agent or not isinstance(default_agent, str):
        raise ValueError("settings.json must have 'default_agent' (main agent name).")

    agents_configs: Dict[str, Dict[str, Any]] = {}
    for name, cfg in raw["agents"].items():
        if not isinstance(cfg, dict):
            continue
        agents_configs[name] = {"model": cfg}

    raw["agents"] = agents_configs

    if default_agent not in agents_configs:
        raise ValueError(
            f"default_agent {default_agent!r} must exist in agents: {list(agents_configs.keys())}"
        )

    return Settings(**raw)

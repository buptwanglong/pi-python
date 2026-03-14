"""
Full settings schema for AssistantAgent: Pydantic models and SettingsManager.
Used by AssistantAgent, configuration subsystem (SubAgentConfig), and tests.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)

DEFAULT_TRAJECTORY_DIR = "~/.basket/trajectories"


# ========================================================================
# Agent Config (Simple multi-agent support)
# ========================================================================


class AgentConfig(BaseModel):
    """Per-agent LLM config: provider, base_url, api_key, etc."""

    provider: str = "openai"
    base_url: str = ""
    api_key: str = ""
    model: Optional[str] = None
    temperature: Optional[float] = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AgentConfig":
        """Create AgentConfig from dict (for legacy migration)."""
        return cls(
            provider=d.get("provider", "openai"),
            base_url=d.get("base_url", ""),
            api_key=d.get("api_key", ""),
            model=d.get("model"),
            temperature=d.get("temperature"),
        )


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


# ========================================================================
# Settings Models
# ========================================================================


class ModelSettings(BaseModel):
    """Model configuration settings."""

    provider: str = "openai"
    model_id: str = "gpt-4o-mini"
    temperature: float = 0.7
    """Maximum output tokens per response (max_tokens / max_output_tokens)."""
    max_tokens: int = 4096
    """Model context window size in tokens (input + output limit)."""
    context_window: int = 128000
    base_url: Optional[str] = None


class AgentSettings(BaseModel):
    """Agent behavior settings."""

    max_turns: int = 10
    auto_save: bool = True
    verbose: bool = False


class PermissionsSettings(BaseModel):
    """Permission mode settings (e.g. plan mode = read-only)."""

    default_mode: Literal["default", "plan"] = "default"


class SubAgentConfig(BaseModel):
    """Configuration for a subagent (used by the Task tool).
    System prompt comes from workspace (AGENTS.md, IDENTITY.md, etc.); display label from AGENTS.md first line.
    """

    model_config = {"extra": "ignore"}  # allow old configs with description/prompt to load

    model: Optional[Dict[str, Any]] = Field(None, description="Optional model override")
    tools: Optional[Dict[str, bool]] = Field(None, description="Tool name -> enabled")
    agent_dir: Optional[str] = Field(
        None,
        description="Agent root directory (parent of workspace/, sessions/); when set, workspace_dir defaults to agent_dir/workspace if workspace_dir is unset",
    )
    workspace_dir: Optional[str] = Field(
        None,
        description="Workspace directory for OpenClaw-style md files; when unset, uses agent_dir/workspace or ~/.basket/agents/<name>/workspace",
    )


class Settings(BaseModel):
    """Global settings for the coding agent (Pydantic schema)."""

    model: ModelSettings = Field(default_factory=ModelSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    permissions: PermissionsSettings = Field(default_factory=PermissionsSettings)
    api_keys: Dict[str, str] = Field(default_factory=dict)
    sessions_dir: str = "~/.basket/sessions"
    trajectory_dir: Optional[str] = Field(
        default=None,
        description="Directory for trajectory recording; default filled at load time with ~/.basket/trajectories. Set to empty to disable.",
    )
    skills_dirs: List[str] = Field(default_factory=list)
    skills_include: List[str] = Field(default_factory=list)
    agents: Dict[str, SubAgentConfig] = Field(default_factory=dict)
    agents_dirs: List[str] = Field(default_factory=list)
    default_agent: Optional[str] = Field(
        None,
        description="Main agent name. When set and present in agents with model, main agent uses that model; otherwise uses top-level model.",
    )
    workspace_dir: Optional[str] = None
    skip_bootstrap: bool = False
    web_search_provider: Optional[str] = None
    serve: Optional[Dict[str, Any]] = None
    relay_url: Optional[str] = None
    hooks: Optional[Dict[str, List[Dict[str, Any]]]] = None
    custom: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _fill_trajectory_dir_default(self) -> "Settings":
        """Set trajectory_dir to default at config time when None (not when reading)."""
        if self.trajectory_dir is None:
            object.__setattr__(self, "trajectory_dir", DEFAULT_TRAJECTORY_DIR)
        return self

    def resolve_agent(self, name: str | None = None) -> AgentConfig:
        """
        Resolve agent by name (for backward compatibility with tests).

        Args:
            name: Agent name (None uses default_agent)

        Returns:
            AgentConfig for the specified agent
        """
        # Convert SubAgentConfig to AgentConfig for multi-agent settings
        if not self.agents:
            # No agents configured, return default
            return AgentConfig(
                provider=self.model.provider,
                base_url=self.model.base_url or "",
                api_key="",
                model=self.model.model_id,
                temperature=self.model.temperature,
            )

        # Use default_agent if name is None or empty
        key = (name or "").strip() or self.default_agent or "default"

        if key not in self.agents:
            raise KeyError(f"Unknown agent: {key!r}. Known: {list(self.agents.keys())}")

        # Get SubAgentConfig and convert to simple AgentConfig
        subagent = self.agents[key]
        if subagent.model and isinstance(subagent.model, dict):
            # Agent has model override
            return AgentConfig(
                provider=subagent.model.get("provider", self.model.provider),
                base_url=subagent.model.get("base_url", self.model.base_url or ""),
                api_key=subagent.model.get("api_key", ""),
                model=subagent.model.get("model_id", self.model.model_id),
                temperature=subagent.model.get("temperature", self.model.temperature),
            )

        # No model override, use top-level settings
        return AgentConfig(
            provider=self.model.provider,
            base_url=self.model.base_url or "",
            api_key="",
            model=self.model.model_id,
            temperature=self.model.temperature,
        )


# ========================================================================
# Agent Config Resolver
# ========================================================================


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


# ========================================================================
# Settings Manager
# ========================================================================


class SettingsManager:
    """Load/save settings from JSON. Accepts config dir or path to settings.json."""

    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = Path.home() / ".basket"
        self.config_dir = Path(config_dir)
        if self.config_dir.suffix == ".json" or (self.config_dir.exists() and self.config_dir.is_file()):
            self.config_file = self.config_dir
            self.config_dir = self.config_dir.parent
        else:
            self.config_file = self.config_dir / "settings.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> Settings:
        if not self.config_file.exists():
            return Settings()
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Settings(**data)
        except Exception as e:
            logger.warning("Failed to load settings, using defaults: %s", e)
            return Settings()

    def save(self, settings: Settings) -> None:
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(settings.model_dump(), f, indent=2)

    def update(self, **kwargs: Any) -> Settings:
        settings = self.load()
        for key, value in kwargs.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        self.save(settings)
        return settings

    def get(self, key: str, default: Any = None) -> Any:
        settings = self.load()
        value: Any = settings
        for part in key.split("."):
            if hasattr(value, part):
                value = getattr(value, part)
            elif isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        settings = self.load()
        parts = key.split(".")
        target: Any = settings
        for part in parts[:-1]:
            if hasattr(target, part):
                target = getattr(target, part)
            elif isinstance(target, dict):
                if part not in target:
                    target[part] = {}
                target = target[part]
        final_key = parts[-1]
        if hasattr(target, final_key):
            setattr(target, final_key, value)
        elif isinstance(target, dict):
            target[final_key] = value
        self.save(settings)

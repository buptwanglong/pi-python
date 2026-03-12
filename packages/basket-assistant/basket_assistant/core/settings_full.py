"""
Full settings schema for AssistantAgent: Pydantic models and SettingsManager.
Used by AssistantAgent, agents_loader (SubAgentConfig), and tests.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)

DEFAULT_TRAJECTORY_DIR = "~/.basket/trajectories"


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

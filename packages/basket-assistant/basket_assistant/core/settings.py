"""
Settings management for the coding agent.

Handles loading and saving user settings.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ModelSettings(BaseModel):
    """Model configuration settings."""

    provider: str = "openai"
    model_id: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 4096
    base_url: Optional[str] = None  # Override API base URL (e.g. custom Anthropic endpoint)


class AgentSettings(BaseModel):
    """Agent behavior settings."""

    max_turns: int = 10
    auto_save: bool = True
    verbose: bool = False


class SubAgentConfig(BaseModel):
    """Configuration for a subagent (used by the Task tool)."""

    description: str = Field(..., description="Short description for the Task tool list")
    prompt: str = Field(..., description="System prompt for this subagent")
    model: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional override: e.g. {\"provider\": \"openai\", \"model_id\": \"gpt-4o-mini\"}",
    )
    tools: Optional[Dict[str, bool]] = Field(
        None,
        description="Optional: tool name -> enabled; unset = all tools like main agent",
    )


class Settings(BaseModel):
    """Global settings for the coding agent."""

    model: ModelSettings = Field(default_factory=ModelSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    api_keys: Dict[str, str] = Field(default_factory=dict)
    sessions_dir: str = "~/.basket/sessions"
    trajectory_dir: Optional[str] = "~/.basket/trajectories"  # Record task trajectories for RL/tuning; set to null/empty to disable
    skills_dirs: List[str] = Field(default_factory=list)  # Empty => use ~/.basket/skills and ./.basket/skills
    skills_include: List[str] = Field(default_factory=list)  # Empty => load all; else only these skill ids
    agents: Dict[str, SubAgentConfig] = Field(default_factory=dict)  # Subagents for Task tool
    agents_dirs: List[str] = Field(default_factory=list)  # Empty => ~/.basket/agents and ./.basket/agents
    # Opaque channel config for basket serve; schema owned by basket-gateway/channels, assistant only passes through
    serve: Optional[Dict[str, Any]] = None
    custom: Dict[str, Any] = Field(default_factory=dict)


class SettingsManager:
    """
    Manages loading and saving settings.

    Settings are stored in JSON format at ~/.basket/settings.json
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize settings manager.

        Args:
            config_dir: Configuration directory (default: ~/.basket)
        """
        if config_dir is None:
            config_dir = Path.home() / ".basket"

        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "settings.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> Settings:
        """
        Load settings from file.

        Returns:
            Settings object (defaults if file doesn't exist)
        """
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
        """
        Save settings to file.

        Args:
            settings: Settings to save
        """
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(settings.model_dump(), f, indent=2)

    def update(self, **kwargs: Any) -> Settings:
        """
        Update settings and save.

        Args:
            **kwargs: Settings fields to update

        Returns:
            Updated settings
        """
        settings = self.load()

        for key, value in kwargs.items():
            if hasattr(settings, key):
                setattr(settings, key, value)

        self.save(settings)
        return settings

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value.

        Args:
            key: Setting key (supports dot notation, e.g., "model.provider")
            default: Default value if key doesn't exist

        Returns:
            Setting value or default
        """
        settings = self.load()

        # Support dot notation
        parts = key.split(".")
        value: Any = settings

        for part in parts:
            if hasattr(value, part):
                value = getattr(value, part)
            elif isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set a setting value.

        Args:
            key: Setting key (supports dot notation)
            value: Value to set
        """
        settings = self.load()

        # Support dot notation
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


__all__ = [
    "ModelSettings",
    "AgentSettings",
    "SubAgentConfig",
    "Settings",
    "SettingsManager",
]

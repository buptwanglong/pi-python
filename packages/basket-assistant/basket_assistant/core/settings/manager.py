"""
SettingsManager: load/save settings from JSON files.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from .models import Settings

logger = logging.getLogger(__name__)


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

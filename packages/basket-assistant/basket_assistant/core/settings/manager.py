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
        valid_updates = {k: v for k, v in kwargs.items() if hasattr(settings, k)}
        settings = settings.model_copy(update=valid_updates)
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

        if len(parts) == 1:
            # Top-level field — immutable copy
            if hasattr(settings, parts[0]):
                settings = settings.model_copy(update={parts[0]: value})
            self.save(settings)
            return

        # Walk down the nested path, collecting (parent_model, attr_name) pairs
        # so we can rebuild immutably from the leaf back to the root.
        from pydantic import BaseModel as _BM

        ancestors: list[tuple[Any, str]] = []  # (model, child_attr_name)
        target: Any = settings
        for part in parts[:-1]:
            if isinstance(target, _BM) and hasattr(target, part):
                ancestors.append((target, part))
                target = getattr(target, part)
            elif isinstance(target, dict):
                if part not in target:
                    target[part] = {}
                ancestors.append((target, part))
                target = target[part]
            else:
                # Path segment not found — nothing to set
                self.save(settings)
                return

        final_key = parts[-1]
        # Apply the leaf update
        if isinstance(target, _BM) and hasattr(target, final_key):
            target = target.model_copy(update={final_key: value})
        elif isinstance(target, dict):
            target = {**target, final_key: value}
        else:
            self.save(settings)
            return

        # Rebuild ancestors from leaf back to root
        for parent, attr_name in reversed(ancestors):
            if isinstance(parent, _BM):
                target = parent.model_copy(update={attr_name: target})
            elif isinstance(parent, dict):
                parent[attr_name] = target
                target = parent

        settings = target  # type: ignore[assignment]
        self.save(settings)

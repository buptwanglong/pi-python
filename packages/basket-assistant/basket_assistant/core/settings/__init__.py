"""
Settings subpackage: Pydantic models, migration, resolver, and manager.

Re-exports all public symbols for backward compatibility.
"""

from .manager import SettingsManager
from .migration import load_settings, migrate_legacy_to_agents, resolve_agent_config
from .models import (
    DEFAULT_TRAJECTORY_DIR,
    AgentConfig,
    AgentSettings,
    ModelSettings,
    PermissionsSettings,
    Settings,
    SubAgentConfig,
)
from .resolver import AgentConfigResolver

__all__ = [
    "AgentConfig",
    "AgentConfigResolver",
    "AgentSettings",
    "DEFAULT_TRAJECTORY_DIR",
    "ModelSettings",
    "PermissionsSettings",
    "Settings",
    "SettingsManager",
    "SubAgentConfig",
    "load_settings",
    "migrate_legacy_to_agents",
    "resolve_agent_config",
]

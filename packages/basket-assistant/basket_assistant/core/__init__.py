"""
Core modules for the coding agent.
"""

from .messages import MessageTree, MessageTreeNode
from .session_manager import SessionEntry, SessionManager, SessionMetadata
from .configuration import AgentLoader
from .settings import (
    AgentConfig,
    AgentConfigResolver,
    AgentSettings,
    ModelSettings,
    PermissionsSettings,
    Settings,
    SettingsManager,
    SubAgentConfig,
)

# Compatibility wrapper for old API
def load_agents_from_dirs(dirs):
    """Deprecated: Use AgentLoader.load_from_dirs() instead"""
    return AgentLoader.load_from_dirs(dirs)
from .skills_loader import (
    get_skill_base_dir,
    get_skill_full_content,
    get_skill_references_index,
    get_skill_scripts_index,
    get_skills_index,
)
from .theme import Theme, ThemeColors, ThemeManager
from .task_model import TaskRecord

__all__ = [
    # Session management
    "SessionEntry",
    "SessionManager",
    "SessionMetadata",
    # Message trees
    "MessageTree",
    "MessageTreeNode",
    # Settings
    "Settings",
    "SettingsManager",
    "ModelSettings",
    "AgentSettings",
    "PermissionsSettings",
    "SubAgentConfig",
    "AgentConfig",
    "AgentConfigResolver",
    # Themes
    "Theme",
    "ThemeColors",
    "ThemeManager",
    # Agents
    "load_agents_from_dirs",
    # Skills
    "get_skill_base_dir",
    "get_skill_full_content",
    "get_skill_references_index",
    "get_skill_scripts_index",
    "get_skills_index",
    # Task
    "TaskRecord",
]

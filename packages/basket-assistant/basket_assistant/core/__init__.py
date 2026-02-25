"""
Core modules for the coding agent.
"""

from .messages import MessageTree, MessageTreeNode
from .session_manager import SessionEntry, SessionManager, SessionMetadata
from .agents_loader import load_agents_from_dirs
from .settings import AgentSettings, ModelSettings, Settings, SettingsManager, SubAgentConfig
from .skills_loader import get_skill_base_dir, get_skill_full_content, get_skills_index
from .theme import Theme, ThemeColors, ThemeManager

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
    "SubAgentConfig",
    # Themes
    "Theme",
    "ThemeColors",
    "ThemeManager",
    # Agents
    "load_agents_from_dirs",
    # Skills
    "get_skill_base_dir",
    "get_skill_full_content",
    "get_skills_index",
]

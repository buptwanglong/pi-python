"""
Core modules for the coding agent.
"""

from .messages import MessageTree, MessageTreeNode
from .session_manager import SessionEntry, SessionManager, SessionMetadata
from .settings import AgentSettings, ModelSettings, Settings, SettingsManager
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
    # Themes
    "Theme",
    "ThemeColors",
    "ThemeManager",
]

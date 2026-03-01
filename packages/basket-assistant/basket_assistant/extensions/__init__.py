"""
Extensions System

Provides extensibility for Pi Coding Agent via:
- Custom tools
- Slash commands
- Event handlers
- Dynamic loading
- Subprocess-based hooks (HookRunner)
"""

from .api import ExtensionAPI
from .hook_runner import HookRunner
from .loader import ExtensionLoader

__all__ = ["ExtensionAPI", "ExtensionLoader", "HookRunner"]

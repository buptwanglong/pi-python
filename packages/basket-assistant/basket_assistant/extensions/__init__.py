"""
Extensions System

Provides extensibility for Pi Coding Agent via:
- Custom tools
- Slash commands
- Event handlers
- Dynamic loading
"""

from .api import ExtensionAPI
from .loader import ExtensionLoader

__all__ = ["ExtensionAPI", "ExtensionLoader"]

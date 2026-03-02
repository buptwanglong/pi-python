"""
Pluggable memory backends for AI assistants.
Use create_backends_from_config() and MemoryManager for multi-backend add/search.
"""

from .backends.base import MemoryBackend
from .backends.noop import NoopBackend
from .factory import create_backends_from_config
from .manager import MemoryManager, messages_to_dicts
from .types import MemoryItem

__all__ = [
    "MemoryBackend",
    "MemoryItem",
    "MemoryManager",
    "NoopBackend",
    "create_backends_from_config",
    "messages_to_dicts",
]

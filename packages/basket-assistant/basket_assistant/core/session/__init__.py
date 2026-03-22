"""
Session management subpackage.

Re-exports all public symbols for backward compatibility:
    from basket_assistant.core.session import SessionManager, SessionEntry, ...
"""

from .models import SessionEntry, SessionMetadata
from .serialization import (
    entry_data_to_message,
    entry_data_to_message_safe,
    message_to_entry_data,
)
from .manager import SessionManager

__all__ = [
    "SessionEntry",
    "SessionMetadata",
    "SessionManager",
    "message_to_entry_data",
    "entry_data_to_message",
    "entry_data_to_message_safe",
]

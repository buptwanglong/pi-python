"""
Shared blackboard for cross-agent communication.

Immutable key-value store that subagents can read from and write to.
Write operations return a new Blackboard instance (frozen Pydantic model).
"""

import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class BlackboardEntry(BaseModel):
    """A single entry in the blackboard."""

    key: str
    value: Any
    author: str  # agent name/id
    timestamp: float

    model_config = ConfigDict(frozen=True)


class Blackboard(BaseModel):
    """
    Immutable key-value store for cross-agent communication.

    All write operations return a new Blackboard instance,
    leaving the original unchanged.
    """

    entries: Dict[str, BlackboardEntry] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)

    def write(self, key: str, value: Any, author: str) -> "Blackboard":
        """Return a new Blackboard with the entry added or updated."""
        new_entry = BlackboardEntry(
            key=key,
            value=value,
            author=author,
            timestamp=time.time(),
        )
        new_entries = {**self.entries, key: new_entry}
        return Blackboard(entries=new_entries)

    def read(self, key: str) -> Optional[Any]:
        """Read a value by key. Returns None if key not found."""
        entry = self.entries.get(key)
        return entry.value if entry else None

    def read_entry(self, key: str) -> Optional[BlackboardEntry]:
        """Read a full entry (with metadata) by key."""
        return self.entries.get(key)

    def keys(self) -> List[str]:
        """Return all keys in the blackboard."""
        return list(self.entries.keys())

    def has_key(self, key: str) -> bool:
        """Check if a key exists in the blackboard."""
        return key in self.entries

    def remove(self, key: str) -> "Blackboard":
        """Return a new Blackboard with the given key removed."""
        new_entries = {k: v for k, v in self.entries.items() if k != key}
        return Blackboard(entries=new_entries)

    def get_by_author(self, author: str) -> Dict[str, BlackboardEntry]:
        """Get all entries written by a specific author."""
        return {k: v for k, v in self.entries.items() if v.author == author}


__all__ = [
    "Blackboard",
    "BlackboardEntry",
]

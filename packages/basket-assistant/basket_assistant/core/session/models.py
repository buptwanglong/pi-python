"""
Session data models.

Pydantic models for session entries and metadata,
plus helper utilities for agent name sanitization.
"""

import uuid
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SessionEntry(BaseModel):
    """A single entry in a session file."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    timestamp: int
    type: str  # "message", "metadata", "branch", etc.
    data: Dict[str, Any] = Field(default_factory=dict)


def _sanitize_agent_name(name: str) -> str:
    """Sanitize agent name for use as a path segment (no path traversal)."""
    if not name:
        return name
    return name.replace("/", "_").replace("\\", "_").replace("..", "_").strip() or "_"


class SessionMetadata(BaseModel):
    """Metadata about a session."""

    session_id: str
    created_at: int
    updated_at: int
    model_id: str
    total_messages: int = 0
    total_tokens: int = 0
    parent_session_id: Optional[str] = None
    agent_name: Optional[str] = None


__all__ = [
    "SessionEntry",
    "SessionMetadata",
    "_sanitize_agent_name",
]

"""
Session manager - JSONL persistence for conversations.

This module handles reading and writing conversation sessions in JSONL format.
Each line is a JSON object representing a session entry (message, metadata, etc.).
"""

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SessionEntry(BaseModel):
    """A single entry in a session file."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    timestamp: int
    type: str  # "message", "metadata", "branch", etc.
    data: Dict[str, Any] = Field(default_factory=dict)


class SessionMetadata(BaseModel):
    """Metadata about a session."""

    session_id: str
    created_at: int
    updated_at: int
    model_id: str
    total_messages: int = 0
    total_tokens: int = 0


class SessionManager:
    """
    Manages conversation sessions with JSONL persistence.

    Sessions are stored as append-only JSONL files where each line
    is a JSON object representing a session entry.
    """

    def __init__(self, sessions_dir: Path):
        """
        Initialize session manager.

        Args:
            sessions_dir: Directory to store session files
        """
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self.sessions_dir / f"{session_id}.jsonl"

    def _get_todos_path(self, session_id: str) -> Path:
        """Get the file path for a session's todo list."""
        return self.sessions_dir / f"{session_id}.todos.json"

    def _get_pending_ask_path(self, session_id: str) -> Path:
        """Get the file path for a session's pending ask list."""
        return self.sessions_dir / f"{session_id}.pending_ask.json"

    async def save_pending_asks(
        self, session_id: str, pending_asks: List[Dict[str, Any]]
    ) -> None:
        """
        Save pending ask list for a session (overwrites existing file).
        Each item must have tool_call_id, question, options.

        Args:
            session_id: Session ID
            pending_asks: List of dicts with tool_call_id, question, options
        """
        path = self._get_pending_ask_path(session_id)
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(pending_asks, ensure_ascii=False, indent=2))

    async def load_pending_asks(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Load pending ask list for a session. Returns [] if file does not exist or is invalid.

        Args:
            session_id: Session ID

        Returns:
            List of dicts with tool_call_id, question, options
        """
        path = self._get_pending_ask_path(session_id)
        if not path.exists():
            return []
        try:
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                content = await f.read()
            if not content.strip():
                return []
            data = json.loads(content)
            if not isinstance(data, list):
                return []
            return [x for x in data if isinstance(x, dict) and "tool_call_id" in x]
        except Exception as e:
            logger.debug("Failed to load pending_asks for %s: %s", session_id, e)
            return []

    async def save_todos(self, session_id: str, todos: List[Dict[str, Any]]) -> None:
        """
        Save todo list for a session (overwrites existing file).

        Args:
            session_id: Session ID
            todos: List of todo items, each dict with id, content, status
        """
        path = self._get_todos_path(session_id)
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(todos, ensure_ascii=False, indent=2))

    async def load_todos(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Load todo list for a session. Returns [] if file does not exist or is invalid.

        Args:
            session_id: Session ID

        Returns:
            List of todo items (dicts with id, content, status)
        """
        path = self._get_todos_path(session_id)
        if not path.exists():
            return []
        try:
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                content = await f.read()
            if not content.strip():
                return []
            data = json.loads(content)
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.debug("Failed to load todos for %s: %s", session_id, e)
            return []

    async def create_session(self, model_id: str) -> str:
        """
        Create a new session.

        Args:
            model_id: ID of the model being used

        Returns:
            Session ID
        """
        import time

        session_id = str(uuid.uuid4())
        timestamp = int(time.time() * 1000)

        # Create initial metadata entry
        metadata = SessionMetadata(
            session_id=session_id,
            created_at=timestamp,
            updated_at=timestamp,
            model_id=model_id,
        )

        entry = SessionEntry(
            id=str(uuid.uuid4()),
            parent_id=None,
            timestamp=timestamp,
            type="metadata",
            data=metadata.model_dump(),
        )

        await self.append_entry(session_id, entry)

        return session_id

    async def append_entry(self, session_id: str, entry: SessionEntry) -> None:
        """
        Append an entry to a session file.

        Args:
            session_id: Session ID
            entry: Entry to append
        """
        path = self._get_session_path(session_id)

        async with aiofiles.open(path, "a", encoding="utf-8") as f:
            line = json.dumps(entry.model_dump()) + "\n"
            await f.write(line)

    async def read_entries(self, session_id: str) -> List[SessionEntry]:
        """
        Read all entries from a session.

        Args:
            session_id: Session ID

        Returns:
            List of session entries
        """
        path = self._get_session_path(session_id)

        if not path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        entries = []
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            async for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    entries.append(SessionEntry(**data))

        return entries

    async def list_sessions(self) -> List[SessionMetadata]:
        """
        List all sessions.

        Returns:
            List of session metadata
        """
        sessions = []

        for path in self.sessions_dir.glob("*.jsonl"):
            session_id = path.stem

            try:
                entries = await self.read_entries(session_id)

                # Find metadata entry
                metadata_entry = next(
                    (e for e in entries if e.type == "metadata"), None
                )

                if metadata_entry:
                    metadata = SessionMetadata(**metadata_entry.data)
                    sessions.append(metadata)
            except Exception as e:
                logger.debug("Skip corrupted session %s: %s", path, e)
                continue

        return sessions

    async def delete_session(self, session_id: str) -> None:
        """
        Delete a session and its todo file.

        Args:
            session_id: Session ID
        """
        path = self._get_session_path(session_id)
        if path.exists():
            path.unlink()
        todos_path = self._get_todos_path(session_id)
        if todos_path.exists():
            todos_path.unlink()
        pending_ask_path = self._get_pending_ask_path(session_id)
        if pending_ask_path.exists():
            pending_ask_path.unlink()

    async def update_metadata(
        self, session_id: str, updates: Dict[str, Any]
    ) -> None:
        """
        Update session metadata.

        This appends a new metadata entry rather than modifying the file.

        Args:
            session_id: Session ID
            updates: Metadata fields to update
        """
        import time

        entries = await self.read_entries(session_id)

        # Find latest metadata
        metadata_entry = next(
            (e for e in reversed(entries) if e.type == "metadata"), None
        )

        if not metadata_entry:
            raise ValueError(f"No metadata found for session {session_id}")

        # Create updated metadata
        metadata = SessionMetadata(**metadata_entry.data)
        for key, value in updates.items():
            setattr(metadata, key, value)

        metadata.updated_at = int(time.time() * 1000)

        # Append new metadata entry
        entry = SessionEntry(
            id=str(uuid.uuid4()),
            parent_id=None,
            timestamp=metadata.updated_at,
            type="metadata",
            data=metadata.model_dump(),
        )

        await self.append_entry(session_id, entry)


__all__ = ["SessionEntry", "SessionMetadata", "SessionManager"]

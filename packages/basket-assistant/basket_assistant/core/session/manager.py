"""
Session manager - JSONL persistence for conversations.

This module handles reading and writing conversation sessions in JSONL format.
Each line is a JSON object representing a session entry (message, metadata, etc.).

For type="message" entries, SessionEntry.data is
{"role": "user"|"assistant"|"toolResult", "payload": <message dict>};
payload uses model_dump(mode="json") so aliases (toolCallId, toolName, etc.) round-trip.
"""

import json
import logging
import uuid
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles

from basket_ai.types import Message

from .models import SessionEntry, SessionMetadata, _sanitize_agent_name
from .serialization import (
    entry_data_to_message,
    entry_data_to_message_safe,
    message_to_entry_data,
)

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages conversation sessions with JSONL persistence.

    Sessions are stored as append-only JSONL files where each line
    is a JSON object representing a session entry.
    """

    def __init__(self, sessions_dir: Path, agent_name: Optional[str] = None):
        """
        Initialize session manager.

        Args:
            sessions_dir: Directory to store session files
            agent_name: Optional main agent name; when set, sessions live under sessions_dir/agent_name
        """
        self.sessions_dir = Path(sessions_dir)
        if agent_name and _sanitize_agent_name(agent_name):
            self.sessions_dir = self.sessions_dir / _sanitize_agent_name(agent_name)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Static methods delegate to module-level functions for backward compat
    # ------------------------------------------------------------------

    @staticmethod
    def message_to_entry_data(message: Message) -> Dict[str, Any]:
        """
        Convert a Message to SessionEntry.data dict.
        data = {"role": ..., "payload": message.model_dump(mode="json")}.
        """
        return message_to_entry_data(message)

    @staticmethod
    def entry_data_to_message(data: Dict[str, Any]) -> Message:
        """
        Deserialize SessionEntry.data to UserMessage, AssistantMessage, or ToolResultMessage.
        Uses payload with populate_by_name so aliases (toolCallId, toolName, etc.) work.
        """
        return entry_data_to_message(data)

    @staticmethod
    def entry_data_to_message_safe(data: Dict[str, Any]) -> Optional[Message]:
        """Like entry_data_to_message but returns None on invalid data (skip bad entries)."""
        return entry_data_to_message_safe(data)

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _get_session_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self.sessions_dir / f"{session_id}.jsonl"

    def _get_todos_path(self, session_id: str) -> Path:
        """Get the file path for a session's todo list."""
        return self.sessions_dir / f"{session_id}.todos.json"

    def _get_pending_ask_path(self, session_id: str) -> Path:
        """Get the file path for a session's pending ask list."""
        return self.sessions_dir / f"{session_id}.pending_ask.json"

    # ------------------------------------------------------------------
    # Side-car persistence (todos, pending asks)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # JSONL I/O
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # High-level API
    # ------------------------------------------------------------------

    async def create_session(
        self,
        model_id: str,
        parent_session_id: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> str:
        """
        Create a new session.

        Args:
            model_id: ID of the model being used
            parent_session_id: Optional parent session ID (for child sessions)
            agent_name: Optional agent name to store in metadata

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        timestamp = int(time.time() * 1000)

        # Create initial metadata entry
        metadata = SessionMetadata(
            session_id=session_id,
            created_at=timestamp,
            updated_at=timestamp,
            model_id=model_id,
            parent_session_id=parent_session_id,
            agent_name=agent_name,
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

    async def ensure_session(
        self,
        session_id: str,
        model_id: str,
        parent_session_id: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> None:
        """
        Ensure a session file exists with metadata. If the file already exists, do nothing.
        Used by gateway (and other modes) when session_id is fixed (e.g. "default").

        Args:
            session_id: Session ID to use
            model_id: ID of the model being used
            parent_session_id: Optional parent session ID (for child sessions)
            agent_name: Optional agent name to store in metadata
        """
        path = self._get_session_path(session_id)
        if path.exists():
            return
        timestamp = int(time.time() * 1000)
        metadata = SessionMetadata(
            session_id=session_id,
            created_at=timestamp,
            updated_at=timestamp,
            model_id=model_id,
            parent_session_id=parent_session_id,
            agent_name=agent_name,
        )
        entry = SessionEntry(
            timestamp=timestamp,
            type="metadata",
            data=metadata.model_dump(),
        )
        await self.append_entry(session_id, entry)

    async def append_messages(self, session_id: str, messages: List[Message]) -> None:
        """
        Append conversation messages to a session as type="message" entries.

        Args:
            session_id: Session ID
            messages: List of UserMessage, AssistantMessage, ToolResultMessage
        """
        for msg in messages:
            ts = getattr(msg, "timestamp", None)
            if ts is None:
                ts = int(time.time() * 1000)
            data = message_to_entry_data(msg)
            entry = SessionEntry(
                timestamp=ts,
                type="message",
                data=data,
            )
            await self.append_entry(session_id, entry)

    async def load_messages(self, session_id: str) -> List[Message]:
        """
        Load all message entries from a session and return as Message list.
        Returns [] if session does not exist or has no message entries.

        Args:
            session_id: Session ID

        Returns:
            List of UserMessage, AssistantMessage, ToolResultMessage in order
        """
        try:
            entries = await self.read_entries(session_id)
        except FileNotFoundError:
            return []
        out: List[Message] = []
        for e in entries:
            if e.type != "message":
                continue
            msg = entry_data_to_message_safe(e.data)
            if msg is not None:
                out.append(msg)
        return out

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
        entries = await self.read_entries(session_id)

        # Find latest metadata
        metadata_entry = next(
            (e for e in reversed(entries) if e.type == "metadata"), None
        )

        if not metadata_entry:
            raise ValueError(f"No metadata found for session {session_id}")

        # Create updated metadata (immutable copy)
        metadata = SessionMetadata(**metadata_entry.data)
        metadata = metadata.model_copy(
            update={**updates, "updated_at": int(time.time() * 1000)}
        )

        # Append new metadata entry
        entry = SessionEntry(
            id=str(uuid.uuid4()),
            parent_id=None,
            timestamp=metadata.updated_at,
            type="metadata",
            data=metadata.model_dump(),
        )

        await self.append_entry(session_id, entry)


__all__ = [
    "SessionManager",
]

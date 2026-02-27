"""
Tests for session manager.
"""

import pytest
from pathlib import Path
import tempfile
import json

from basket_assistant.core.session_manager import (
    SessionManager,
    SessionEntry,
    SessionMetadata,
)


@pytest.fixture
async def temp_sessions_dir():
    """Create a temporary sessions directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
async def session_manager(temp_sessions_dir):
    """Create a session manager instance."""
    return SessionManager(temp_sessions_dir)


@pytest.mark.asyncio
async def test_create_session(session_manager):
    """Test creating a new session."""
    session_id = await session_manager.create_session("gpt-4o-mini")

    assert session_id is not None
    assert len(session_id) > 0

    # Verify session file was created
    session_path = session_manager._get_session_path(session_id)
    assert session_path.exists()


@pytest.mark.asyncio
async def test_append_entry(session_manager):
    """Test appending entries to a session."""
    session_id = await session_manager.create_session("gpt-4o-mini")

    # Append a message entry
    entry = SessionEntry(
        parent_id=None,
        timestamp=1234567890,
        type="message",
        data={"role": "user", "content": "Hello"},
    )

    await session_manager.append_entry(session_id, entry)

    # Read back and verify
    entries = await session_manager.read_entries(session_id)
    assert len(entries) >= 2  # metadata + message

    message_entries = [e for e in entries if e.type == "message"]
    assert len(message_entries) == 1
    assert message_entries[0].data["content"] == "Hello"


@pytest.mark.asyncio
async def test_read_entries(session_manager):
    """Test reading entries from a session."""
    session_id = await session_manager.create_session("gpt-4o-mini")

    # Append multiple entries
    for i in range(3):
        entry = SessionEntry(
            parent_id=None,
            timestamp=1234567890 + i,
            type="message",
            data={"content": f"Message {i}"},
        )
        await session_manager.append_entry(session_id, entry)

    # Read all entries
    entries = await session_manager.read_entries(session_id)

    # Should have metadata + 3 messages
    assert len(entries) >= 4
    message_entries = [e for e in entries if e.type == "message"]
    assert len(message_entries) == 3


@pytest.mark.asyncio
async def test_read_nonexistent_session(session_manager):
    """Test reading a nonexistent session."""
    with pytest.raises(FileNotFoundError):
        await session_manager.read_entries("nonexistent-session-id")


@pytest.mark.asyncio
async def test_list_sessions(session_manager):
    """Test listing all sessions."""
    # Create multiple sessions
    session_ids = []
    for i in range(3):
        session_id = await session_manager.create_session(f"model-{i}")
        session_ids.append(session_id)

    # List sessions
    sessions = await session_manager.list_sessions()

    assert len(sessions) == 3
    assert all(isinstance(s, SessionMetadata) for s in sessions)


@pytest.mark.asyncio
async def test_save_todos_and_load_todos(session_manager):
    """Test saving and loading todos for a session."""
    session_id = await session_manager.create_session("gpt-4o-mini")
    todos = [
        {"id": "1", "content": "First task", "status": "pending"},
        {"id": "2", "content": "Second", "status": "in_progress"},
    ]
    await session_manager.save_todos(session_id, todos)
    loaded = await session_manager.load_todos(session_id)
    assert loaded == todos
    assert session_manager._get_todos_path(session_id).exists()


@pytest.mark.asyncio
async def test_load_todos_nonexistent_returns_empty(session_manager):
    """Load todos for session with no todo file returns []."""
    session_id = await session_manager.create_session("gpt-4o-mini")
    loaded = await session_manager.load_todos(session_id)
    assert loaded == []
    # Session exists but no .todos.json
    assert not session_manager._get_todos_path(session_id).exists()


@pytest.mark.asyncio
async def test_delete_session_removes_todos_file(session_manager):
    """Deleting a session also removes its .todos.json file."""
    session_id = await session_manager.create_session("gpt-4o-mini")
    await session_manager.save_todos(session_id, [{"id": "1", "content": "x", "status": "pending"}])
    todos_path = session_manager._get_todos_path(session_id)
    assert todos_path.exists()
    await session_manager.delete_session(session_id)
    assert not session_manager._get_session_path(session_id).exists()
    assert not todos_path.exists()


@pytest.mark.asyncio
async def test_save_pending_asks_and_load_pending_asks(session_manager):
    """Test saving and loading pending asks (list of tool_call_id, question, options)."""
    session_id = await session_manager.create_session("gpt-4o-mini")
    pending = [
        {"tool_call_id": "call_1", "question": "Q1?", "options": [{"id": "a", "label": "A"}]},
        {"tool_call_id": "call_2", "question": "Q2?", "options": []},
    ]
    await session_manager.save_pending_asks(session_id, pending)
    loaded = await session_manager.load_pending_asks(session_id)
    assert loaded == pending
    assert session_manager._get_pending_ask_path(session_id).exists()


@pytest.mark.asyncio
async def test_load_pending_asks_nonexistent_returns_empty(session_manager):
    """Load pending_asks for session with no file returns []."""
    session_id = await session_manager.create_session("gpt-4o-mini")
    loaded = await session_manager.load_pending_asks(session_id)
    assert loaded == []
    assert not session_manager._get_pending_ask_path(session_id).exists()


@pytest.mark.asyncio
async def test_delete_session_removes_pending_ask_file(session_manager):
    """Deleting a session also removes its .pending_ask.json file."""
    session_id = await session_manager.create_session("gpt-4o-mini")
    await session_manager.save_pending_asks(
        session_id, [{"tool_call_id": "call_x", "question": "Q?", "options": []}]
    )
    pending_path = session_manager._get_pending_ask_path(session_id)
    assert pending_path.exists()
    await session_manager.delete_session(session_id)
    assert not session_manager._get_session_path(session_id).exists()
    assert not pending_path.exists()


@pytest.mark.asyncio
async def test_delete_session(session_manager):
    """Test deleting a session."""
    session_id = await session_manager.create_session("gpt-4o-mini")

    # Verify session exists
    session_path = session_manager._get_session_path(session_id)
    assert session_path.exists()

    # Delete session
    await session_manager.delete_session(session_id)

    # Verify session was deleted
    assert not session_path.exists()


@pytest.mark.asyncio
async def test_update_metadata(session_manager):
    """Test updating session metadata."""
    session_id = await session_manager.create_session("gpt-4o-mini")

    # Update metadata
    await session_manager.update_metadata(
        session_id, {"total_messages": 5, "total_tokens": 1000}
    )

    # Read entries
    entries = await session_manager.read_entries(session_id)

    # Should have 2 metadata entries (initial + update)
    metadata_entries = [e for e in entries if e.type == "metadata"]
    assert len(metadata_entries) == 2

    # Check updated values
    latest_metadata = SessionMetadata(**metadata_entries[-1].data)
    assert latest_metadata.total_messages == 5
    assert latest_metadata.total_tokens == 1000


@pytest.mark.asyncio
async def test_jsonl_format(session_manager):
    """Test that JSONL format is correct."""
    session_id = await session_manager.create_session("gpt-4o-mini")

    entry = SessionEntry(
        parent_id=None,
        timestamp=1234567890,
        type="message",
        data={"content": "Test"},
    )
    await session_manager.append_entry(session_id, entry)

    # Read raw file
    session_path = session_manager._get_session_path(session_id)
    with open(session_path, "r") as f:
        lines = f.readlines()

    # Each line should be valid JSON
    for line in lines:
        line = line.strip()
        if line:
            data = json.loads(line)
            assert "id" in data
            assert "timestamp" in data
            assert "type" in data


@pytest.mark.asyncio
async def test_concurrent_appends(session_manager):
    """Test concurrent appends to a session."""
    import asyncio

    session_id = await session_manager.create_session("gpt-4o-mini")

    # Append entries concurrently
    async def append_message(i):
        entry = SessionEntry(
            parent_id=None,
            timestamp=1234567890 + i,
            type="message",
            data={"content": f"Message {i}"},
        )
        await session_manager.append_entry(session_id, entry)

    await asyncio.gather(*[append_message(i) for i in range(10)])

    # Verify all entries were written
    entries = await session_manager.read_entries(session_id)
    message_entries = [e for e in entries if e.type == "message"]
    assert len(message_entries) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

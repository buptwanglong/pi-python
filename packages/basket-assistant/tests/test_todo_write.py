"""Tests for the todo_write tool (create_todo_write_tool, execute_fn)."""

import pytest

from basket_assistant.tools import TodoItem, TodoWriteParams, create_todo_write_tool


@pytest.fixture
def agent_ref():
    """Agent ref with _current_todos list; _session_id None so persist is not called."""
    ref = __import__("unittest.mock").mock.MagicMock()
    ref._current_todos = []
    ref._session_id = None
    return ref


def test_todo_write_tool_name_and_params(agent_ref):
    """Tool has name todo_write and TodoWriteParams."""
    tool = create_todo_write_tool(agent_ref)
    assert tool["name"] == "todo_write"
    assert tool["parameters"] is TodoWriteParams
    assert "Create or update" in tool["description"]
    assert "When to use" in tool["description"]
    assert "When NOT to use" in tool["description"]


@pytest.mark.asyncio
async def test_todo_write_updates_agent_todos_and_returns_confirmation(agent_ref):
    """execute_fn replaces _current_todos and returns message with count."""
    tool = create_todo_write_tool(agent_ref)
    todos = [
        TodoItem(id="1", content="First task", status="pending"),
        TodoItem(id="2", content="Second task", status="in_progress"),
    ]
    result = await tool["execute_fn"](todos=todos)
    assert agent_ref._current_todos == [
        {"id": "1", "content": "First task", "status": "pending"},
        {"id": "2", "content": "Second task", "status": "in_progress"},
    ]
    assert "Todo list updated (2 items)" in result


@pytest.mark.asyncio
async def test_todo_write_empty_list(agent_ref):
    """Empty list clears _current_todos."""
    agent_ref._current_todos = [{"id": "1", "content": "x", "status": "pending"}]
    tool = create_todo_write_tool(agent_ref)
    result = await tool["execute_fn"](todos=[])
    assert agent_ref._current_todos == []
    assert "0 item" in result or "0 items" in result


@pytest.mark.asyncio
async def test_todo_write_single_item(agent_ref):
    """Single item updates list and returns singular message."""
    tool = create_todo_write_tool(agent_ref)
    result = await tool["execute_fn"](todos=[TodoItem(content="Only one", status="completed")])
    assert len(agent_ref._current_todos) == 1
    assert agent_ref._current_todos[0]["content"] == "Only one"
    assert agent_ref._current_todos[0]["status"] == "completed"
    assert "1 item" in result and "items" not in result or "1 item)" in result


@pytest.mark.asyncio
async def test_todo_write_accepts_list_of_dicts(agent_ref):
    """execute_fn accepts list of dicts (e.g. from JSON tool call)."""
    tool = create_todo_write_tool(agent_ref)
    todos = [
        {"id": "a", "content": "From dict", "status": "in_progress"},
        {"content": "No id", "status": "pending"},
    ]
    result = await tool["execute_fn"](todos=todos)
    assert agent_ref._current_todos[0]["content"] == "From dict"
    assert agent_ref._current_todos[0]["status"] == "in_progress"
    assert agent_ref._current_todos[1]["content"] == "No id"
    assert "2 items" in result


@pytest.mark.asyncio
async def test_todo_write_non_list_returns_error(agent_ref):
    """When todos is not a list, return error message."""
    tool = create_todo_write_tool(agent_ref)
    result = await tool["execute_fn"](todos="not a list")
    assert "Error" in result
    assert "list" in result
    assert agent_ref._current_todos == []  # unchanged


@pytest.mark.asyncio
async def test_todo_write_statuses_preserved(agent_ref):
    """All four statuses are stored correctly."""
    tool = create_todo_write_tool(agent_ref)
    todos = [
        TodoItem(content="p", status="pending"),
        TodoItem(content="i", status="in_progress"),
        TodoItem(content="c", status="completed"),
        TodoItem(content="x", status="cancelled"),
    ]
    await tool["execute_fn"](todos=todos)
    statuses = [t["status"] for t in agent_ref._current_todos]
    assert statuses == ["pending", "in_progress", "completed", "cancelled"]


@pytest.mark.asyncio
async def test_todo_write_persists_to_file_when_session_id_set(tmp_path):
    """When agent has _session_id and session_manager, todos are saved to session file."""
    from basket_assistant.core.session_manager import SessionManager

    session_mgr = SessionManager(tmp_path)
    session_id = await session_mgr.create_session("test-model")
    agent_ref = __import__("unittest.mock").mock.MagicMock()
    agent_ref._current_todos = []
    agent_ref._session_id = session_id
    agent_ref.session_manager = session_mgr

    tool = create_todo_write_tool(agent_ref)
    todos = [
        TodoItem(id="1", content="Persisted task", status="in_progress"),
    ]
    await tool["execute_fn"](todos=todos)

    loaded = await session_mgr.load_todos(session_id)
    assert len(loaded) == 1
    assert loaded[0]["content"] == "Persisted task"
    assert loaded[0]["status"] == "in_progress"
    assert (tmp_path / f"{session_id}.todos.json").exists()

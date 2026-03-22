"""Tests for the todo_write tool (create_todo_write_tool, execute_fn)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from basket_assistant.agent.context import AgentContext
from basket_assistant.tools import TodoItem, TodoWriteParams, create_todo_write_tool


def _make_test_ctx(session_id="test-session"):
    """Build an AgentContext for tests with a captured save_todos list."""
    saved: list[dict] = []

    async def save_todos(todos):
        saved.clear()
        saved.extend(todos)

    ctx = AgentContext(
        session_id=session_id,
        plan_mode=False,
        run_subagent=AsyncMock(),
        get_subagent_configs=MagicMock(return_value={}),
        get_subagent_display_description=MagicMock(return_value=""),
        save_todos=save_todos,
        save_pending_asks=AsyncMock(),
        append_recent_task=MagicMock(),
        update_recent_task=MagicMock(),
        settings=MagicMock(),
        get_skills_dirs=MagicMock(return_value=[]),
        get_plugin_skill_dirs=MagicMock(return_value=[]),
        draft_skill_from_session=AsyncMock(),
        save_pending_skill_draft=AsyncMock(),
    )
    return ctx, saved


@pytest.fixture
def ctx_and_saved():
    """AgentContext with a captured save_todos list."""
    return _make_test_ctx()


def test_todo_write_tool_name_and_params(ctx_and_saved):
    """Tool has name todo_write and TodoWriteParams."""
    ctx, _saved = ctx_and_saved
    tool = create_todo_write_tool(ctx)
    assert tool["name"] == "todo_write"
    assert tool["parameters"] is TodoWriteParams
    assert "Create or update" in tool["description"]
    assert "When to use" in tool["description"]
    assert "When NOT to use" in tool["description"]


@pytest.mark.asyncio
async def test_todo_write_updates_todos_and_returns_confirmation(ctx_and_saved):
    """execute_fn saves todos via ctx and returns message with count."""
    ctx, saved = ctx_and_saved
    tool = create_todo_write_tool(ctx)
    todos = [
        TodoItem(id="1", content="First task", status="pending"),
        TodoItem(id="2", content="Second task", status="in_progress"),
    ]
    result = await tool["execute_fn"](todos=todos)
    assert saved == [
        {"id": "1", "content": "First task", "status": "pending"},
        {"id": "2", "content": "Second task", "status": "in_progress"},
    ]
    assert "Todo list updated (2 items)" in result


@pytest.mark.asyncio
async def test_todo_write_empty_list(ctx_and_saved):
    """Empty list clears saved todos."""
    ctx, saved = ctx_and_saved
    # Pre-populate to verify clearing
    saved.extend([{"id": "1", "content": "x", "status": "pending"}])
    tool = create_todo_write_tool(ctx)
    result = await tool["execute_fn"](todos=[])
    assert saved == []
    assert "0 item" in result or "0 items" in result


@pytest.mark.asyncio
async def test_todo_write_single_item(ctx_and_saved):
    """Single item updates list and returns singular message."""
    ctx, saved = ctx_and_saved
    tool = create_todo_write_tool(ctx)
    result = await tool["execute_fn"](todos=[TodoItem(content="Only one", status="completed")])
    assert len(saved) == 1
    assert saved[0]["content"] == "Only one"
    assert saved[0]["status"] == "completed"
    assert "1 item" in result and "items" not in result or "1 item)" in result


@pytest.mark.asyncio
async def test_todo_write_accepts_list_of_dicts(ctx_and_saved):
    """execute_fn accepts list of dicts (e.g. from JSON tool call)."""
    ctx, saved = ctx_and_saved
    tool = create_todo_write_tool(ctx)
    todos = [
        {"id": "a", "content": "From dict", "status": "in_progress"},
        {"content": "No id", "status": "pending"},
    ]
    result = await tool["execute_fn"](todos=todos)
    assert saved[0]["content"] == "From dict"
    assert saved[0]["status"] == "in_progress"
    assert saved[1]["content"] == "No id"
    assert "2 items" in result


@pytest.mark.asyncio
async def test_todo_write_non_list_returns_error(ctx_and_saved):
    """When todos is not a list, return error message."""
    ctx, saved = ctx_and_saved
    tool = create_todo_write_tool(ctx)
    result = await tool["execute_fn"](todos="not a list")
    assert "Error" in result
    assert "list" in result
    assert saved == []  # unchanged


@pytest.mark.asyncio
async def test_todo_write_statuses_preserved(ctx_and_saved):
    """All four statuses are stored correctly."""
    ctx, saved = ctx_and_saved
    tool = create_todo_write_tool(ctx)
    todos = [
        TodoItem(content="p", status="pending"),
        TodoItem(content="i", status="in_progress"),
        TodoItem(content="c", status="completed"),
        TodoItem(content="x", status="cancelled"),
    ]
    await tool["execute_fn"](todos=todos)
    statuses = [t["status"] for t in saved]
    assert statuses == ["pending", "in_progress", "completed", "cancelled"]


@pytest.mark.asyncio
async def test_todo_write_persists_to_file_when_session_id_set(tmp_path):
    """When save_todos callback persists via SessionManager, todos are saved to session file."""
    from basket_assistant.core.session import SessionManager

    session_mgr = SessionManager(tmp_path)
    session_id = await session_mgr.create_session("test-model")

    # Build a save_todos callback that mirrors real build_tool_context behavior
    current_todos: list[dict] = []

    async def save_todos(todos):
        current_todos.clear()
        current_todos.extend(todos)
        await session_mgr.save_todos(session_id, todos)

    ctx = AgentContext(
        session_id=session_id,
        plan_mode=False,
        run_subagent=AsyncMock(),
        get_subagent_configs=MagicMock(return_value={}),
        get_subagent_display_description=MagicMock(return_value=""),
        save_todos=save_todos,
        save_pending_asks=AsyncMock(),
        append_recent_task=MagicMock(),
        update_recent_task=MagicMock(),
        settings=MagicMock(),
        get_skills_dirs=MagicMock(return_value=[]),
        get_plugin_skill_dirs=MagicMock(return_value=[]),
        draft_skill_from_session=AsyncMock(),
        save_pending_skill_draft=AsyncMock(),
    )

    tool = create_todo_write_tool(ctx)
    todos = [
        TodoItem(id="1", content="Persisted task", status="in_progress"),
    ]
    await tool["execute_fn"](todos=todos)

    loaded = await session_mgr.load_todos(session_id)
    assert len(loaded) == 1
    assert loaded[0]["content"] == "Persisted task"
    assert loaded[0]["status"] == "in_progress"
    assert (tmp_path / f"{session_id}.todos.json").exists()

"""
TodoWrite tool - Manage a structured task list for the current session (OpenCode-style).

Replaces the entire todo list on each call. Used for multi-step task tracking.
"""

from typing import Any, List, Literal

from pydantic import BaseModel, Field

TodoStatus = Literal["pending", "in_progress", "completed", "cancelled"]


class TodoItem(BaseModel):
    """Single todo item."""

    id: str | None = Field(None, description="Optional unique id for the task")
    content: str = Field(..., description="Task description")
    status: TodoStatus = Field(
        ...,
        description="Current state: pending, in_progress, completed, or cancelled",
    )


class TodoWriteParams(BaseModel):
    """Parameters for the TodoWrite tool."""

    todos: List[TodoItem] = Field(
        ...,
        description="Full list of tasks. Each call replaces the entire list.",
    )


def create_todo_write_tool(agent_ref: Any) -> dict:
    """
    Create the todo_write tool. Call from main when registering tools.

    agent_ref must have: _current_todos (list) to store the latest list.

    Returns a dict with name, description, parameters, execute_fn for agent.register_tool().
    """
    description = (
        "Create or update the structured task list for the current session. "
        "Each call replaces the entire list. Use to track progress on multi-step tasks.\n\n"
        "When to use: complex multi-step tasks (3+ steps), non-trivial tasks, user asks for a todo list, "
        "user provides multiple tasks, after new instructions or after completing a step, or when starting a new task (mark as in_progress). "
        "Prefer at most one task in_progress at a time.\n\n"
        "When NOT to use: single straightforward task, trivial task, completable in fewer than 3 steps, or purely conversational requests.\n\n"
        "Parameter: todos = full list of items, each with id (optional), content, status (pending|in_progress|completed|cancelled)."
    )

    async def execute_todo_write(todos: List[Any]) -> str:
        if not isinstance(todos, list):
            return "Error: todos must be a list."
        serialized = []
        for item in todos:
            if isinstance(item, TodoItem):
                serialized.append(item.model_dump())
            elif isinstance(item, dict):
                serialized.append(
                    {
                        "id": item.get("id"),
                        "content": item.get("content", ""),
                        "status": item.get("status", "pending"),
                    }
                )
            else:
                serialized.append({"id": None, "content": str(item), "status": "pending"})
        agent_ref._current_todos = serialized
        session_id = getattr(agent_ref, "_session_id", None)
        if session_id and getattr(agent_ref, "session_manager", None):
            await agent_ref.session_manager.save_todos(session_id, serialized)
        n = len(serialized)
        return f"Todo list updated ({n} item{'s' if n != 1 else ''})."

    return {
        "name": "todo_write",
        "description": description,
        "parameters": TodoWriteParams,
        "execute_fn": execute_todo_write,
    }


__all__ = ["TodoItem", "TodoStatus", "TodoWriteParams", "create_todo_write_tool"]

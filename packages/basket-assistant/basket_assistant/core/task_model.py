"""
Task model for delegated subagent work (Task tool).

Used to represent a single task invocation: task_id, description, subagent_type,
status, optional parent_session_id and result_summary. Not persisted to a
separate store in this phase; Task tool may append to agent._recent_tasks.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class TaskRecord(BaseModel):
    """A single task delegation record (in-memory or for session append)."""

    task_id: str = Field(..., description="Unique task id (e.g. uuid)")
    description: str = Field(..., description="Short task description")
    prompt: str = Field(..., description="Full prompt sent to subagent")
    subagent_type: str = Field(..., description="Name of the subagent used")
    status: Literal["pending", "running", "completed", "failed"] = Field(
        default="pending",
        description="Current status",
    )
    created_at: int = Field(..., description="Timestamp when task was created")
    parent_session_id: Optional[str] = Field(None, description="Parent session id if any")
    result_summary: Optional[str] = Field(
        None,
        description="Last assistant text or truncated result",
    )


__all__ = ["TaskRecord"]

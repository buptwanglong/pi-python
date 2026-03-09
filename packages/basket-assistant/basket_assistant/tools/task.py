"""
Task tool - Delegate work to a subagent by name (OpenCode-style).
"""

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class TaskParams(BaseModel):
    """Parameters for the Task tool."""

    description: str = Field(..., description="Short (3-5 words) description of the task")
    prompt: str = Field(..., description="The task for the subagent to perform")
    subagent_type: str = Field(..., description="The name of the subagent to use (from available list)")


def create_task_tool(agent_ref: Any) -> dict:
    """
    Create the task tool with dynamic description. Call from main when registering tools.

    agent_ref must have: run_subagent(name, prompt) -> str, _get_subagent_configs() -> Dict[str, SubAgentConfig].

    Returns a dict with name, description, parameters, execute_fn for agent.register_tool().
    """
    configs = agent_ref._get_subagent_configs()
    if not configs:
        description = "Delegate a task to a specialized subagent. No subagents configured."
    else:
        lines = [
            "Delegate a complex or multi-step task to a specialized subagent. The subagent runs with its own instructions and tools, then returns a single result.",
            "",
            "When to use: research, codebase exploration, or tasks that fit a subagent's description.",
            "When NOT to use: simple file read/write or single command; use read/write/bash instead.",
            "",
            "Available subagents (pass subagent_type when calling this tool):",
        ]
        for name, cfg in sorted(configs.items()):
            lines.append(f"  - {name}: {cfg.description}")
        description = "\n".join(lines)

    async def execute_task(description: str, prompt: str, subagent_type: str) -> str:
        task_id = str(uuid.uuid4())
        created_at = int(time.time() * 1000)
        parent_session_id = getattr(agent_ref, "_session_id", None)
        # Optional: append to in-memory list for traceability
        recent = getattr(agent_ref, "_recent_tasks", None)
        if recent is not None:
            recent.append({
                "task_id": task_id,
                "description": description,
                "prompt": prompt,
                "subagent_type": subagent_type,
                "status": "running",
                "created_at": created_at,
                "parent_session_id": parent_session_id,
                "result_summary": None,
            })
        try:
            result = await agent_ref.run_subagent(subagent_type, prompt)
            if recent and len(recent) > 0:
                recent[-1]["status"] = "completed"
                recent[-1]["result_summary"] = (result[:500] + "…") if len(result) > 500 else result
            lines = [
                f"task_id: {task_id}",
                "",
                "<task_result>",
                result,
                "</task_result>",
            ]
            return "\n".join(lines)
        except Exception as e:
            if recent and len(recent) > 0:
                recent[-1]["status"] = "failed"
                recent[-1]["result_summary"] = str(e)[:500]
            raise

    return {
        "name": "task",
        "description": description,
        "parameters": TaskParams,
        "execute_fn": execute_task,
    }


__all__ = ["TaskParams", "create_task_tool"]

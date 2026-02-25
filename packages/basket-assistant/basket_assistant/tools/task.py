"""
Task tool - Delegate work to a subagent by name (OpenCode-style).
"""

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
        result = await agent_ref.run_subagent(subagent_type, prompt)
        lines = [
            "task_id: none",
            "",
            "<task_result>",
            result,
            "</task_result>",
        ]
        return "\n".join(lines)

    return {
        "name": "task",
        "description": description,
        "parameters": TaskParams,
        "execute_fn": execute_task,
    }


__all__ = ["TaskParams", "create_task_tool"]

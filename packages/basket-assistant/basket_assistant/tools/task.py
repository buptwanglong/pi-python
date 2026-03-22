"""
Task tools - Delegate work to subagents by name (OpenCode-style).

Includes the single ``task`` tool and the ``parallel_task`` tool that
runs multiple subagent tasks concurrently via ``asyncio.gather``.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, List

from pydantic import BaseModel, Field

from basket_assistant.agent.context import AgentContext


class TaskParams(BaseModel):
    """Parameters for the Task tool."""

    description: str = Field(..., description="Short (3-5 words) description of the task")
    prompt: str = Field(..., description="The task for the subagent to perform")
    subagent_type: str = Field(..., description="The name of the subagent to use (from available list)")


class TaskSpec(BaseModel):
    """Specification for a single task in a parallel batch."""

    description: str = Field(..., description="Short description of the task")
    prompt: str = Field(..., description="The task for the subagent to perform")
    subagent_type: str = Field(..., description="The name of the subagent to use")


class ParallelTaskParams(BaseModel):
    """Parameters for the parallel_task tool."""

    tasks: List[TaskSpec] = Field(
        ..., description="List of tasks to run in parallel. Each needs description, prompt, and subagent_type."
    )


def create_task_tool(ctx: AgentContext) -> dict:
    """
    Create the task tool with dynamic description. Call from main when registering tools.

    ctx must provide: run_subagent, get_subagent_configs, get_subagent_display_description.

    Returns a dict with name, description, parameters, execute_fn for agent.register_tool().
    """
    configs = ctx.get_subagent_configs()
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
            label = ctx.get_subagent_display_description(name, cfg)
            lines.append(f"  - {name}: {label}")
        description = "\n".join(lines)

    async def execute_task(description: str, prompt: str, subagent_type: str) -> str:
        task_id = str(uuid.uuid4())
        created_at = int(time.time() * 1000)
        parent_session_id = ctx.session_id
        # Append to in-memory list for traceability
        task_record = {
            "task_id": task_id,
            "description": description,
            "prompt": prompt,
            "subagent_type": subagent_type,
            "status": "running",
            "created_at": created_at,
            "parent_session_id": parent_session_id,
            "result_summary": None,
        }
        ctx.append_recent_task(task_record)
        try:
            result = await ctx.run_subagent(subagent_type, prompt)
            ctx.update_recent_task(-1, {
                "status": "completed",
                "result_summary": (result[:500] + "…") if len(result) > 500 else result,
            })
            lines = [
                f"task_id: {task_id}",
                "",
                "<task_result>",
                result,
                "</task_result>",
            ]
            return "\n".join(lines)
        except Exception as e:
            ctx.update_recent_task(-1, {
                "status": "failed",
                "result_summary": str(e)[:500],
            })
            raise

    return {
        "name": "task",
        "description": description,
        "parameters": TaskParams,
        "execute_fn": execute_task,
    }


def create_parallel_task_tool(ctx: AgentContext) -> dict:
    """
    Create the parallel_task tool that runs multiple subagent tasks concurrently.

    ctx must provide: run_subagent, get_subagent_configs.

    Returns a dict with name, description, parameters, execute_fn for agent.register_tool().
    """
    configs = ctx.get_subagent_configs()
    if not configs:
        agent_list = "No subagents configured."
    else:
        agent_names = ", ".join(sorted(configs.keys()))
        agent_list = f"Available subagents: {agent_names}"

    description = (
        "Run multiple subagent tasks in parallel. Each task is dispatched to its "
        "specified subagent concurrently via asyncio.gather. Results are returned "
        "in the same order as the input tasks.\n\n"
        "When to use: when you need to delegate 2+ independent tasks that can run "
        "simultaneously (e.g., research in one agent while exploring code in another).\n"
        "When NOT to use: when tasks depend on each other's results.\n\n"
        f"{agent_list}"
    )

    async def execute_parallel_tasks(tasks: List[dict]) -> str:
        """Run all tasks in parallel and return formatted results."""
        # Convert raw dicts to TaskSpec if needed
        specs = [
            TaskSpec(**t) if isinstance(t, dict) else t
            for t in tasks
        ]

        async def _run_single(spec: TaskSpec) -> dict:
            """Run one subagent task, capturing result or error."""
            task_id = str(uuid.uuid4())
            try:
                result = await ctx.run_subagent(
                    spec.subagent_type, spec.prompt
                )
                return {
                    "task_id": task_id,
                    "description": spec.description,
                    "subagent_type": spec.subagent_type,
                    "status": "completed",
                    "result": result,
                    "error": None,
                }
            except Exception as e:
                return {
                    "task_id": task_id,
                    "description": spec.description,
                    "subagent_type": spec.subagent_type,
                    "status": "failed",
                    "result": None,
                    "error": str(e),
                }

        coroutines = [_run_single(spec) for spec in specs]
        results = await asyncio.gather(*coroutines, return_exceptions=True)

        # Format output
        output_parts = [f"Parallel execution: {len(specs)} tasks"]
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                # Unexpected gather-level exception
                output_parts.append(
                    f"\n--- Task {i + 1} ---\n"
                    f"status: failed\n"
                    f"error: {res}"
                )
            else:
                output_parts.append(
                    f"\n--- Task {i + 1}: {res['description']} (task_id: {res['task_id']}) ---\n"
                    f"subagent: {res['subagent_type']}\n"
                    f"status: {res['status']}"
                )
                if res["error"]:
                    output_parts.append(f"error: {res['error']}")
                else:
                    output_parts.append(
                        f"\n<task_result>\n{res['result']}\n</task_result>"
                    )

        return "\n".join(output_parts)

    return {
        "name": "parallel_task",
        "description": description,
        "parameters": ParallelTaskParams,
        "execute_fn": execute_parallel_tasks,
    }


__all__ = [
    "TaskParams",
    "TaskSpec",
    "ParallelTaskParams",
    "create_task_tool",
    "create_parallel_task_tool",
]

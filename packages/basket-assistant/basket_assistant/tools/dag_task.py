"""
dag_task tool — Delegate a graph of interdependent tasks to subagents.

Accepts a DAG definition (nodes + dependencies), validates it, then
executes via the DAGExecutor with parallel scheduling.
"""

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from basket_assistant.agent.context import AgentContext
from ..orchestration.dag import TaskDAG, TaskNode, TaskStatus
from ..orchestration.executor import DAGExecutor

logger = logging.getLogger(__name__)


class DAGNodeSpec(BaseModel):
    """Specification for a single node in the dag_task input."""

    id: str = Field(..., description="Unique node identifier")
    subagent_type: str = Field(..., description="Subagent to run this node")
    prompt: str = Field(..., description="Prompt for the subagent")
    depends_on: List[str] = Field(
        default_factory=list, description="IDs of nodes that must complete first"
    )


class DAGTaskParams(BaseModel):
    """Parameters for the dag_task tool."""

    description: str = Field(
        ..., description="Short (3-10 words) description of the DAG task"
    )
    nodes: List[DAGNodeSpec] = Field(
        ..., description="List of task nodes forming the DAG"
    )


def _build_dag(specs: List[DAGNodeSpec]) -> TaskDAG:
    """Convert a list of DAGNodeSpec into a validated TaskDAG.

    Raises:
        ValueError: On duplicate IDs, missing dependencies, or cycles.
    """
    dag = TaskDAG()

    # First pass: add all nodes
    for spec in specs:
        node = TaskNode(
            id=spec.id,
            subagent_type=spec.subagent_type,
            prompt=spec.prompt,
            depends_on=spec.depends_on,
        )
        dag = dag.add_node(node)

    # Validate dependency references
    all_ids = set(dag.nodes.keys())
    for node in dag.nodes.values():
        missing = set(node.depends_on) - all_ids
        if missing:
            raise ValueError(
                f"Node '{node.id}' depends on unknown node(s): {sorted(missing)}"
            )

    # Validate acyclicity
    if dag.has_cycle():
        raise ValueError("DAG contains a cycle")

    return dag


def create_dag_task_tool(ctx: AgentContext) -> Dict[str, Any]:
    """Create the dag_task tool.

    The tool accepts a DAG definition, validates it, then dispatches
    nodes to subagents in parallel (respecting dependencies).

    Args:
        ctx: AgentContext providing run_subagent callback.

    Returns:
        Tool registration dict (name, description, parameters, execute_fn).
    """

    async def execute_dag_task(description: str, nodes: List[Dict[str, Any]]) -> str:
        task_id = str(uuid.uuid4())
        started_at = time.time()

        # Parse node specs
        specs = [DAGNodeSpec(**n) for n in nodes]

        # Build and validate DAG
        try:
            dag = _build_dag(specs)
        except ValueError as e:
            return f"DAG validation error: {e}"

        # Create executor bound to the agent's run_subagent
        async def run_node(node: TaskNode) -> str:
            return await ctx.run_subagent(node.subagent_type, node.prompt)

        executor = DAGExecutor(run_fn=run_node, max_concurrency=5)
        exec_result = await executor.execute(dag)

        # Format results
        final_dag = exec_result.dag
        lines = [
            f"dag_task_id: {task_id}",
            f"description: {description}",
            f"total_duration: {exec_result.total_duration:.2f}s",
            f"nodes_completed: {exec_result.nodes_completed}",
            f"nodes_failed: {exec_result.nodes_failed}",
            "",
        ]

        topo = final_dag.topological_order() if not final_dag.has_cycle() else list(final_dag.nodes.keys())
        for node_id in topo:
            node = final_dag.nodes[node_id]
            lines.append(f"--- {node_id} [{node.status.value}] ---")
            if node.result:
                truncated = (
                    node.result[:500] + "…" if len(node.result) > 500 else node.result
                )
                lines.append(truncated)
            if node.error:
                lines.append(f"ERROR: {node.error}")
            lines.append("")

        return "\n".join(lines)

    return {
        "name": "dag_task",
        "description": (
            "Execute a directed acyclic graph (DAG) of tasks via subagents. "
            "Nodes run in parallel when their dependencies are met. "
            "Use for complex multi-step workflows with interdependencies."
        ),
        "parameters": DAGTaskParams,
        "execute_fn": execute_dag_task,
    }


# ── Self-registration ──
from ._registry import ToolDefinition, register

register(ToolDefinition(
    name="dag_task",
    description="Execute a directed acyclic graph of subagent tasks.",
    parameters=DAGTaskParams,
    factory=lambda ctx: create_dag_task_tool(ctx)["execute_fn"],
))


__all__ = [
    "DAGNodeSpec",
    "DAGTaskParams",
    "create_dag_task_tool",
]

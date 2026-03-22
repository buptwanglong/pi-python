"""
DAG executor — runs tasks with dependency-aware parallel scheduling.

Uses asyncio.gather with a semaphore for concurrency control.
The executor is stateless: all state lives in the immutable TaskDAG
that is threaded through the execution loop.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Coroutine, Dict

from pydantic import BaseModel, ConfigDict

from .dag import TaskDAG, TaskNode, TaskStatus

logger = logging.getLogger(__name__)


class DAGExecutionResult(BaseModel):
    """Summary of a full DAG execution run."""

    dag: TaskDAG
    total_duration: float
    nodes_completed: int
    nodes_failed: int

    model_config = ConfigDict(frozen=True)


class DAGExecutor:
    """Execute a TaskDAG with parallel scheduling of ready nodes.

    Args:
        run_fn: Async callable that receives a TaskNode and returns a
            result string on success (or raises on failure).
        max_concurrency: Maximum parallel tasks at any point in time.
    """

    def __init__(
        self,
        run_fn: Callable[[TaskNode], Coroutine[Any, Any, str]],
        max_concurrency: int = 5,
    ) -> None:
        self.run_fn = run_fn
        self.max_concurrency = max_concurrency

    async def _run_node(self, node: TaskNode) -> Dict[str, Any]:
        """Run a single node, returning a result dict."""
        try:
            result = await self.run_fn(node)
            return {"node_id": node.id, "result": result, "error": None}
        except Exception as e:
            return {"node_id": node.id, "result": None, "error": str(e)}

    async def execute(self, dag: TaskDAG) -> DAGExecutionResult:
        """Execute the DAG with dependency-aware parallel scheduling.

        Ready nodes are dispatched in parallel (bounded by
        *max_concurrency*).  Dependent nodes wait until their
        predecessors complete.

        Args:
            dag: The task DAG to execute.

        Returns:
            DAGExecutionResult with the final DAG state and summary stats.

        Raises:
            ValueError: If the DAG contains a cycle.
        """
        if dag.has_cycle():
            raise ValueError("Cannot execute DAG with cycles")

        start = time.monotonic()
        current_dag = dag

        while not current_dag.is_complete():
            ready = current_dag.ready_nodes()
            if not ready:
                # No ready nodes but not all complete → deadlock
                logger.error("DAG deadlock: no ready nodes but DAG is not complete")
                break

            # Mark ready nodes as RUNNING
            for node in ready:
                current_dag = current_dag.update_node(
                    node.id, status=TaskStatus.RUNNING
                )

            # Execute with bounded concurrency
            semaphore = asyncio.Semaphore(self.max_concurrency)

            async def _run_with_sem(n: TaskNode) -> Dict[str, Any]:
                async with semaphore:
                    return await self._run_node(n)

            results = await asyncio.gather(
                *[_run_with_sem(n) for n in ready],
                return_exceptions=True,
            )

            # Apply results
            for raw in results:
                if isinstance(raw, BaseException):
                    logger.error("Unexpected exception in gather: %s", raw)
                    continue
                result: Dict[str, Any] = raw
                node_id = result["node_id"]
                if result["error"]:
                    current_dag = current_dag.update_node(
                        node_id,
                        status=TaskStatus.FAILED,
                        error=result["error"],
                    )
                else:
                    current_dag = current_dag.update_node(
                        node_id,
                        status=TaskStatus.COMPLETED,
                        result=result["result"],
                    )

        elapsed = time.monotonic() - start

        completed = sum(
            1 for n in current_dag.nodes.values()
            if n.status == TaskStatus.COMPLETED
        )
        failed = sum(
            1 for n in current_dag.nodes.values()
            if n.status == TaskStatus.FAILED
        )

        return DAGExecutionResult(
            dag=current_dag,
            total_duration=elapsed,
            nodes_completed=completed,
            nodes_failed=failed,
        )


__all__ = [
    "DAGExecutionResult",
    "DAGExecutor",
]

"""Tests for DAG executor — parallel scheduling with dependency awareness."""

import asyncio

import pytest

from basket_assistant.orchestration.dag import TaskDAG, TaskNode, TaskStatus
from basket_assistant.orchestration.executor import DAGExecutionResult, DAGExecutor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_fn(delay: float = 0.0, fail_ids: frozenset[str] | None = None):
    """Create a mock run function.

    Args:
        delay: Artificial delay per node (seconds).
        fail_ids: Set of node IDs that should raise an exception.

    Returns:
        Async callable compatible with DAGExecutor.run_fn.
    """
    fail_ids = fail_ids or frozenset()

    async def run(node: TaskNode) -> str:
        if delay > 0:
            await asyncio.sleep(delay)
        if node.id in fail_ids:
            raise RuntimeError(f"Node {node.id} failed intentionally")
        return f"result-{node.id}"

    return run


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDAGExecutor:
    """Tests for DAGExecutor.execute()."""

    @pytest.mark.asyncio
    async def test_execute_single_node(self):
        dag = TaskDAG()
        dag = dag.add_node(TaskNode(id="a", subagent_type="x", prompt="do stuff"))

        executor = DAGExecutor(run_fn=_make_run_fn())
        result = await executor.execute(dag)

        assert isinstance(result, DAGExecutionResult)
        assert result.nodes_completed == 1
        assert result.nodes_failed == 0
        assert result.dag.nodes["a"].status == TaskStatus.COMPLETED
        assert result.dag.nodes["a"].result == "result-a"
        assert result.total_duration >= 0.0

    @pytest.mark.asyncio
    async def test_execute_parallel_independent_nodes(self):
        dag = TaskDAG()
        dag = dag.add_node(TaskNode(id="a", subagent_type="x", prompt="p1"))
        dag = dag.add_node(TaskNode(id="b", subagent_type="x", prompt="p2"))
        dag = dag.add_node(TaskNode(id="c", subagent_type="x", prompt="p3"))

        executor = DAGExecutor(run_fn=_make_run_fn(delay=0.01))
        result = await executor.execute(dag)

        assert result.nodes_completed == 3
        assert result.nodes_failed == 0
        for nid in ["a", "b", "c"]:
            assert result.dag.nodes[nid].status == TaskStatus.COMPLETED
            assert result.dag.nodes[nid].result == f"result-{nid}"

    @pytest.mark.asyncio
    async def test_execute_sequential_dependent_nodes(self):
        # a -> b -> c
        dag = TaskDAG()
        dag = dag.add_node(TaskNode(id="a", subagent_type="x", prompt="p1"))
        dag = dag.add_node(
            TaskNode(id="b", subagent_type="x", prompt="p2", depends_on=["a"])
        )
        dag = dag.add_node(
            TaskNode(id="c", subagent_type="x", prompt="p3", depends_on=["b"])
        )

        call_order: list[str] = []
        original_fn = _make_run_fn()

        async def tracking_fn(node: TaskNode) -> str:
            call_order.append(node.id)
            return await original_fn(node)

        executor = DAGExecutor(run_fn=tracking_fn)
        result = await executor.execute(dag)

        assert result.nodes_completed == 3
        assert result.nodes_failed == 0
        # Verify sequential ordering: a before b, b before c
        assert call_order.index("a") < call_order.index("b")
        assert call_order.index("b") < call_order.index("c")

    @pytest.mark.asyncio
    async def test_execute_with_failure(self):
        dag = TaskDAG()
        dag = dag.add_node(TaskNode(id="a", subagent_type="x", prompt="p1"))
        dag = dag.add_node(TaskNode(id="b", subagent_type="x", prompt="p2"))

        executor = DAGExecutor(
            run_fn=_make_run_fn(fail_ids=frozenset({"b"}))
        )
        result = await executor.execute(dag)

        assert result.nodes_completed == 1
        assert result.nodes_failed == 1
        assert result.dag.nodes["a"].status == TaskStatus.COMPLETED
        assert result.dag.nodes["b"].status == TaskStatus.FAILED
        assert "intentionally" in (result.dag.nodes["b"].error or "")

    @pytest.mark.asyncio
    async def test_execute_failure_blocks_dependents(self):
        # a -> b(fails) -> c(should not run, stays pending)
        dag = TaskDAG()
        dag = dag.add_node(TaskNode(id="a", subagent_type="x", prompt="p1"))
        dag = dag.add_node(
            TaskNode(id="b", subagent_type="x", prompt="p2", depends_on=["a"])
        )
        dag = dag.add_node(
            TaskNode(id="c", subagent_type="x", prompt="p3", depends_on=["b"])
        )

        executed: list[str] = []

        async def run(node: TaskNode) -> str:
            executed.append(node.id)
            if node.id == "b":
                raise RuntimeError("b broke")
            return f"ok-{node.id}"

        executor = DAGExecutor(run_fn=run)
        result = await executor.execute(dag)

        assert result.dag.nodes["a"].status == TaskStatus.COMPLETED
        assert result.dag.nodes["b"].status == TaskStatus.FAILED
        # c should NOT have been executed (deadlocked, stays pending/running)
        assert "c" not in executed

    @pytest.mark.asyncio
    async def test_deadlock_detection(self):
        # Simulate deadlock: node depends on a failed node
        # After a fails, b can never become ready → deadlock
        dag = TaskDAG()
        dag = dag.add_node(TaskNode(id="a", subagent_type="x", prompt="p1"))
        dag = dag.add_node(
            TaskNode(id="b", subagent_type="x", prompt="p2", depends_on=["a"])
        )

        executor = DAGExecutor(
            run_fn=_make_run_fn(fail_ids=frozenset({"a"}))
        )
        result = await executor.execute(dag)

        # a failed, b never ran (deadlocked)
        assert result.dag.nodes["a"].status == TaskStatus.FAILED
        assert result.dag.nodes["b"].status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_execute_cycle_raises(self):
        node_a = TaskNode(id="a", subagent_type="x", prompt="p", depends_on=["b"])
        node_b = TaskNode(id="b", subagent_type="x", prompt="p", depends_on=["a"])
        dag = TaskDAG(nodes={"a": node_a, "b": node_b})

        executor = DAGExecutor(run_fn=_make_run_fn())
        with pytest.raises(ValueError, match="cycles"):
            await executor.execute(dag)

    @pytest.mark.asyncio
    async def test_execute_diamond_dag(self):
        #   a
        #  / \
        # b   c
        #  \ /
        #   d
        dag = TaskDAG()
        dag = dag.add_node(TaskNode(id="a", subagent_type="x", prompt="p"))
        dag = dag.add_node(
            TaskNode(id="b", subagent_type="x", prompt="p", depends_on=["a"])
        )
        dag = dag.add_node(
            TaskNode(id="c", subagent_type="x", prompt="p", depends_on=["a"])
        )
        dag = dag.add_node(
            TaskNode(id="d", subagent_type="x", prompt="p", depends_on=["b", "c"])
        )

        call_order: list[str] = []

        async def tracking(node: TaskNode) -> str:
            call_order.append(node.id)
            return f"ok-{node.id}"

        executor = DAGExecutor(run_fn=tracking)
        result = await executor.execute(dag)

        assert result.nodes_completed == 4
        assert result.nodes_failed == 0
        # a must be before b and c; b and c must be before d
        assert call_order.index("a") < call_order.index("b")
        assert call_order.index("a") < call_order.index("c")
        assert call_order.index("b") < call_order.index("d")
        assert call_order.index("c") < call_order.index("d")

    @pytest.mark.asyncio
    async def test_concurrency_limit(self):
        """Verify max_concurrency bounds parallel execution."""
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def counting_fn(node: TaskNode) -> str:
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            await asyncio.sleep(0.02)
            async with lock:
                current_concurrent -= 1
            return f"ok-{node.id}"

        dag = TaskDAG()
        for i in range(10):
            dag = dag.add_node(TaskNode(id=f"n{i}", subagent_type="x", prompt="p"))

        executor = DAGExecutor(run_fn=counting_fn, max_concurrency=3)
        result = await executor.execute(dag)

        assert result.nodes_completed == 10
        assert max_concurrent <= 3

    @pytest.mark.asyncio
    async def test_execution_result_is_frozen(self):
        dag = TaskDAG()
        dag = dag.add_node(TaskNode(id="a", subagent_type="x", prompt="p"))

        executor = DAGExecutor(run_fn=_make_run_fn())
        result = await executor.execute(dag)

        with pytest.raises(Exception):
            result.nodes_completed = 999  # type: ignore[misc]

"""Tests for DAG-based task orchestration (immutable task graph)."""

import pytest

from basket_assistant.orchestration.dag import TaskDAG, TaskNode, TaskStatus


class TestTaskNode:
    """TaskNode is a frozen Pydantic model."""

    def test_create_node(self):
        node = TaskNode(id="a", subagent_type="explore", prompt="Find files")
        assert node.id == "a"
        assert node.subagent_type == "explore"
        assert node.status == TaskStatus.PENDING
        assert node.depends_on == []
        assert node.result is None
        assert node.error is None

    def test_node_is_frozen(self):
        node = TaskNode(id="a", subagent_type="explore", prompt="p")
        with pytest.raises(Exception):
            node.status = TaskStatus.RUNNING  # type: ignore[misc]


class TestTaskDAG:
    """TaskDAG immutability and query methods."""

    def test_empty_dag_is_complete(self):
        dag = TaskDAG()
        assert dag.is_complete() is True
        assert dag.ready_nodes() == []

    def test_add_node(self):
        dag = TaskDAG()
        node = TaskNode(id="a", subagent_type="explore", prompt="p")
        new_dag = dag.add_node(node)

        # Original is unchanged (immutability)
        assert "a" not in dag.nodes
        # New DAG has the node
        assert "a" in new_dag.nodes
        assert new_dag.nodes["a"].id == "a"

    def test_add_duplicate_node_raises(self):
        dag = TaskDAG()
        node = TaskNode(id="a", subagent_type="explore", prompt="p")
        dag = dag.add_node(node)
        with pytest.raises(ValueError, match="already exists"):
            dag.add_node(node)

    def test_single_node_ready(self):
        dag = TaskDAG()
        node = TaskNode(id="a", subagent_type="explore", prompt="p")
        dag = dag.add_node(node)

        ready = dag.ready_nodes()
        assert len(ready) == 1
        assert ready[0].id == "a"

    def test_ready_nodes_respects_dependencies(self):
        dag = TaskDAG()
        node_a = TaskNode(id="a", subagent_type="explore", prompt="p1")
        node_b = TaskNode(
            id="b", subagent_type="explore", prompt="p2", depends_on=["a"]
        )
        dag = dag.add_node(node_a).add_node(node_b)

        # Only a is ready (b depends on a)
        ready = dag.ready_nodes()
        assert len(ready) == 1
        assert ready[0].id == "a"

    def test_ready_nodes_after_dependency_completed(self):
        dag = TaskDAG()
        node_a = TaskNode(id="a", subagent_type="explore", prompt="p1")
        node_b = TaskNode(
            id="b", subagent_type="explore", prompt="p2", depends_on=["a"]
        )
        dag = dag.add_node(node_a).add_node(node_b)

        # Complete a
        dag = dag.update_node("a", status=TaskStatus.COMPLETED, result="done")

        ready = dag.ready_nodes()
        assert len(ready) == 1
        assert ready[0].id == "b"

    def test_update_node_immutability(self):
        dag = TaskDAG()
        node = TaskNode(id="a", subagent_type="explore", prompt="p")
        dag = dag.add_node(node)
        original_node = dag.nodes["a"]

        new_dag = dag.update_node("a", status=TaskStatus.RUNNING)

        # Original unchanged
        assert dag.nodes["a"].status == TaskStatus.PENDING
        assert original_node.status == TaskStatus.PENDING
        # New DAG updated
        assert new_dag.nodes["a"].status == TaskStatus.RUNNING

    def test_update_nonexistent_node_raises(self):
        dag = TaskDAG()
        with pytest.raises(ValueError, match="not found"):
            dag.update_node("missing", status=TaskStatus.RUNNING)

    def test_is_complete_all_terminal(self):
        dag = TaskDAG()
        dag = dag.add_node(
            TaskNode(id="a", subagent_type="x", prompt="p", status=TaskStatus.COMPLETED)
        )
        dag = dag.add_node(
            TaskNode(id="b", subagent_type="x", prompt="p", status=TaskStatus.FAILED)
        )
        dag = dag.add_node(
            TaskNode(id="c", subagent_type="x", prompt="p", status=TaskStatus.SKIPPED)
        )
        assert dag.is_complete() is True

    def test_is_complete_with_pending(self):
        dag = TaskDAG()
        dag = dag.add_node(
            TaskNode(id="a", subagent_type="x", prompt="p", status=TaskStatus.COMPLETED)
        )
        dag = dag.add_node(
            TaskNode(id="b", subagent_type="x", prompt="p", status=TaskStatus.PENDING)
        )
        assert dag.is_complete() is False

    def test_has_cycle_no_cycle(self):
        dag = TaskDAG()
        dag = dag.add_node(TaskNode(id="a", subagent_type="x", prompt="p"))
        dag = dag.add_node(
            TaskNode(id="b", subagent_type="x", prompt="p", depends_on=["a"])
        )
        dag = dag.add_node(
            TaskNode(id="c", subagent_type="x", prompt="p", depends_on=["b"])
        )
        assert dag.has_cycle() is False

    def test_has_cycle_detection(self):
        # Create a cycle: a -> b -> c -> a
        # We need to build this carefully since nodes are frozen
        node_a = TaskNode(id="a", subagent_type="x", prompt="p", depends_on=["c"])
        node_b = TaskNode(id="b", subagent_type="x", prompt="p", depends_on=["a"])
        node_c = TaskNode(id="c", subagent_type="x", prompt="p", depends_on=["b"])
        dag = TaskDAG(nodes={"a": node_a, "b": node_b, "c": node_c})
        assert dag.has_cycle() is True

    def test_topological_order_simple_chain(self):
        dag = TaskDAG()
        dag = dag.add_node(TaskNode(id="a", subagent_type="x", prompt="p"))
        dag = dag.add_node(
            TaskNode(id="b", subagent_type="x", prompt="p", depends_on=["a"])
        )
        dag = dag.add_node(
            TaskNode(id="c", subagent_type="x", prompt="p", depends_on=["b"])
        )
        order = dag.topological_order()
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_topological_order_diamond(self):
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
        order = dag.topological_order()
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_topological_order_with_cycle_raises(self):
        node_a = TaskNode(id="a", subagent_type="x", prompt="p", depends_on=["b"])
        node_b = TaskNode(id="b", subagent_type="x", prompt="p", depends_on=["a"])
        dag = TaskDAG(nodes={"a": node_a, "b": node_b})
        with pytest.raises(ValueError, match="cycle"):
            dag.topological_order()

    def test_independent_nodes_all_ready(self):
        dag = TaskDAG()
        dag = dag.add_node(TaskNode(id="a", subagent_type="x", prompt="p1"))
        dag = dag.add_node(TaskNode(id="b", subagent_type="x", prompt="p2"))
        dag = dag.add_node(TaskNode(id="c", subagent_type="x", prompt="p3"))

        ready = dag.ready_nodes()
        assert len(ready) == 3
        ready_ids = {n.id for n in ready}
        assert ready_ids == {"a", "b", "c"}

    def test_dag_is_frozen(self):
        dag = TaskDAG()
        with pytest.raises(Exception):
            dag.nodes = {}  # type: ignore[misc]

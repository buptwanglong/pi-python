"""
DAG-based task orchestration.

Immutable task graph with dependency-aware scheduling.
All update operations return new TaskDAG instances to preserve immutability.
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(str, Enum):
    """Lifecycle status of a task node."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# Terminal statuses: nodes in these states will not be re-scheduled.
_TERMINAL_STATUSES = frozenset({TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED})


class TaskNode(BaseModel):
    """A single task in the DAG.

    Attributes:
        id: Unique identifier for this node.
        subagent_type: Name of the subagent to execute this task.
        prompt: The prompt/instruction for the subagent.
        depends_on: IDs of nodes that must complete before this one runs.
        status: Current lifecycle status.
        result: Output text on success.
        error: Error message on failure.
    """

    id: str
    subagent_type: str
    prompt: str
    depends_on: List[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None

    model_config = ConfigDict(frozen=True)


class TaskDAG(BaseModel):
    """Immutable directed acyclic graph of tasks.

    All mutation methods return *new* TaskDAG instances; the original is
    never modified.  This makes it safe to pass the DAG across async
    boundaries without locking.
    """

    nodes: Dict[str, TaskNode] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)

    # ------------------------------------------------------------------
    # Mutation (returns new DAG)
    # ------------------------------------------------------------------

    def add_node(self, node: TaskNode) -> "TaskDAG":
        """Return a new DAG with *node* added.

        Raises:
            ValueError: If a node with the same id already exists.
        """
        if node.id in self.nodes:
            raise ValueError(f"Node '{node.id}' already exists in DAG")
        new_nodes = {**self.nodes, node.id: node}
        return TaskDAG(nodes=new_nodes)

    def update_node(self, node_id: str, **kwargs) -> "TaskDAG":
        """Return a new DAG with *node_id* updated using *kwargs*.

        Raises:
            ValueError: If node_id is not in the DAG.
        """
        if node_id not in self.nodes:
            raise ValueError(f"Node '{node_id}' not found in DAG")
        old_node = self.nodes[node_id]
        new_node = old_node.model_copy(update=kwargs)
        new_nodes = {**self.nodes, node_id: new_node}
        return TaskDAG(nodes=new_nodes)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def ready_nodes(self) -> List[TaskNode]:
        """Return all PENDING nodes whose dependencies are COMPLETED."""
        ready: List[TaskNode] = []
        for node in self.nodes.values():
            if node.status != TaskStatus.PENDING:
                continue
            deps_met = all(
                self.nodes[dep_id].status == TaskStatus.COMPLETED
                for dep_id in node.depends_on
                if dep_id in self.nodes
            )
            if deps_met:
                ready.append(node)
        return ready

    def is_complete(self) -> bool:
        """Check whether every node is in a terminal state."""
        if not self.nodes:
            return True
        return all(n.status in _TERMINAL_STATUSES for n in self.nodes.values())

    def has_cycle(self) -> bool:
        """Detect cycles using iterative DFS with a recursion-stack set."""
        visited: set[str] = set()
        path: set[str] = set()

        def _dfs(node_id: str) -> bool:
            if node_id in path:
                return True
            if node_id in visited:
                return False
            path.add(node_id)
            visited.add(node_id)
            node = self.nodes.get(node_id)
            if node:
                for dep in node.depends_on:
                    if _dfs(dep):
                        return True
            path.discard(node_id)
            return False

        return any(_dfs(nid) for nid in self.nodes)

    def topological_order(self) -> List[str]:
        """Return node IDs in topological order (dependencies first).

        Raises:
            ValueError: If the DAG contains a cycle.
        """
        if self.has_cycle():
            raise ValueError("DAG contains a cycle")

        visited: set[str] = set()
        order: List[str] = []

        def _dfs(node_id: str) -> None:
            if node_id in visited:
                return
            visited.add(node_id)
            node = self.nodes.get(node_id)
            if node:
                for dep in node.depends_on:
                    _dfs(dep)
            order.append(node_id)

        for nid in self.nodes:
            _dfs(nid)

        return order


__all__ = [
    "TaskDAG",
    "TaskNode",
    "TaskStatus",
]

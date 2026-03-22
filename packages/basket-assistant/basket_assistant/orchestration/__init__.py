"""
DAG-based task orchestration.

Provides an immutable task graph with dependency-aware scheduling.
All mutation operations return new DAG instances.
"""

from .dag import TaskDAG, TaskNode, TaskStatus
from .executor import DAGExecutionResult, DAGExecutor

__all__ = [
    "DAGExecutionResult",
    "DAGExecutor",
    "TaskDAG",
    "TaskNode",
    "TaskStatus",
]

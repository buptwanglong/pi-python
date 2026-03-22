"""
pi-trajectory: task trajectory recording for agent runs (RL and tuning).
"""

from .analysis import (
    AggregateReport,
    ComparisonReport,
    LoopDetection,
    TrajectoryMetrics,
    WastedTurn,
    aggregate_results,
    compare_trajectories,
    compute_metrics,
    detect_loops,
    detect_wasted_turns,
)
from .schema import TaskTrajectory, ToolCallRecord, TurnRecord
from .recorder import TrajectoryRecorder
from .storage import write_trajectory, load_trajectory, load_trajectories

__all__ = [
    "AggregateReport",
    "ComparisonReport",
    "LoopDetection",
    "TaskTrajectory",
    "TrajectoryMetrics",
    "TurnRecord",
    "ToolCallRecord",
    "TrajectoryRecorder",
    "WastedTurn",
    "aggregate_results",
    "compare_trajectories",
    "compute_metrics",
    "detect_loops",
    "detect_wasted_turns",
    "load_trajectory",
    "load_trajectories",
    "write_trajectory",
]

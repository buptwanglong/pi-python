"""
Trajectory analysis toolkit.

Pure functions for computing metrics, detecting patterns, and comparing trajectories.
"""

from collections import Counter
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .schema import TaskTrajectory, ToolCallRecord, TurnRecord


class TrajectoryMetrics(BaseModel):
    """Computed metrics for a single trajectory."""

    total_turns: int = 0
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    tokens_per_turn: float = 0.0
    tool_distribution: Dict[str, int] = Field(default_factory=dict)
    error_count: int = 0
    error_rate: float = 0.0
    duration_seconds: float = 0.0
    unique_tools_used: int = 0

    model_config = ConfigDict(frozen=True)


class LoopDetection(BaseModel):
    """Detected loop pattern in trajectory."""

    pattern: List[str]  # tool names in the repeated pattern
    occurrences: int
    start_turn: int
    end_turn: int

    model_config = ConfigDict(frozen=True)


class WastedTurn(BaseModel):
    """A turn identified as wasted (error + identical retry)."""

    turn_index: int
    tool_name: str
    error: str

    model_config = ConfigDict(frozen=True)


class ComparisonReport(BaseModel):
    """Comparison between two trajectories."""

    a_metrics: TrajectoryMetrics
    b_metrics: TrajectoryMetrics
    cost_diff: float = 0.0
    turns_diff: int = 0
    both_succeeded: bool = False

    model_config = ConfigDict(frozen=True)


class AggregateReport(BaseModel):
    """Aggregated report across multiple eval results."""

    total_instances: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    avg_cost: float = 0.0
    avg_turns: float = 0.0
    avg_duration: float = 0.0
    tool_usage: Dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


def _collect_all_tool_calls(trajectory: TaskTrajectory) -> List[ToolCallRecord]:
    """Collect all tool calls across all turns."""
    calls: List[ToolCallRecord] = []
    for turn in trajectory.turns:
        calls.extend(turn.tool_calls)
    return calls


def compute_metrics(trajectory: TaskTrajectory) -> TrajectoryMetrics:
    """Compute metrics from a trajectory.

    Extracts turn counts, token usage, cost, tool distribution,
    error rate, and duration from a TaskTrajectory.
    """
    all_calls = _collect_all_tool_calls(trajectory)

    # Tool distribution: count calls per tool name
    tool_counter: Counter[str] = Counter()
    error_count = 0
    for call in all_calls:
        tool_counter[call.tool_name] += 1
        if call.error is not None:
            error_count += 1

    total_calls = len(all_calls)
    error_rate = error_count / total_calls if total_calls > 0 else 0.0

    usage = trajectory.total_usage
    input_tokens = int(usage.get("input", 0))
    output_tokens = int(usage.get("output", 0))
    total_tokens = int(usage.get("total_tokens", 0))
    cost_total = float(usage.get("cost_total", 0.0))

    total_turns = trajectory.total_turns or len(trajectory.turns)
    tokens_per_turn = total_tokens / total_turns if total_turns > 0 else 0.0

    duration = trajectory.ended_at - trajectory.started_at

    return TrajectoryMetrics(
        total_turns=total_turns,
        total_cost=cost_total,
        total_input_tokens=input_tokens,
        total_output_tokens=output_tokens,
        total_tokens=total_tokens,
        tokens_per_turn=tokens_per_turn,
        tool_distribution=dict(tool_counter),
        error_count=error_count,
        error_rate=error_rate,
        duration_seconds=duration,
        unique_tools_used=len(tool_counter),
    )


def detect_loops(
    trajectory: TaskTrajectory, threshold: int = 3
) -> List[LoopDetection]:
    """Detect repeated tool call patterns suggesting agent is stuck.

    Scans the sequence of tool calls for repeated sub-sequences of length 1..max_len.
    A pattern is reported when it repeats >= threshold consecutive times.

    Args:
        trajectory: The trajectory to analyze.
        threshold: Minimum consecutive repetitions to flag as a loop.

    Returns:
        List of detected loop patterns.
    """
    # Build flat list of (turn_index, tool_name) from all turns
    tool_sequence: List[tuple[int, str]] = []
    for turn in trajectory.turns:
        for call in turn.tool_calls:
            tool_sequence.append((turn.turn_index, call.tool_name))

    if len(tool_sequence) < threshold:
        return []

    tool_names = [name for _, name in tool_sequence]
    detected: List[LoopDetection] = []
    n = len(tool_names)

    # Check pattern lengths from 1 up to n // threshold
    max_pattern_len = n // threshold
    for pat_len in range(1, max_pattern_len + 1):
        i = 0
        while i <= n - pat_len * threshold:
            pattern = tool_names[i : i + pat_len]
            # Count consecutive repetitions starting at i
            count = 0
            j = i
            while j + pat_len <= n and tool_names[j : j + pat_len] == pattern:
                count += 1
                j += pat_len

            if count >= threshold:
                start_turn = tool_sequence[i][0]
                end_turn = tool_sequence[min(j - 1, n - 1)][0]
                detection = LoopDetection(
                    pattern=pattern,
                    occurrences=count,
                    start_turn=start_turn,
                    end_turn=end_turn,
                )
                # Avoid duplicate detections (sub-patterns of already found ones)
                if detection not in detected:
                    detected.append(detection)
                i = j  # skip past detected loop
            else:
                i += 1

    return detected


def detect_wasted_turns(trajectory: TaskTrajectory) -> List[WastedTurn]:
    """Detect turns where tool errored and was retried identically.

    A wasted turn is identified when:
    1. A tool call in turn N has an error
    2. The next turn (N+1) has a tool call with the same tool_name and arguments

    Returns:
        List of WastedTurn instances for the errored turns that were retried.
    """
    wasted: List[WastedTurn] = []
    turns = trajectory.turns

    for i in range(len(turns) - 1):
        current_turn = turns[i]
        next_turn = turns[i + 1]

        for call in current_turn.tool_calls:
            if call.error is None:
                continue

            # Check if same call exists in next turn
            for next_call in next_turn.tool_calls:
                if (
                    next_call.tool_name == call.tool_name
                    and next_call.arguments == call.arguments
                ):
                    wasted.append(
                        WastedTurn(
                            turn_index=current_turn.turn_index,
                            tool_name=call.tool_name,
                            error=call.error,
                        )
                    )
                    break  # only flag once per errored call

    return wasted


def compare_trajectories(
    a: TaskTrajectory, b: TaskTrajectory
) -> ComparisonReport:
    """Compare two trajectories on the same task.

    Computes metrics for both and reports differences.
    """
    a_metrics = compute_metrics(a)
    b_metrics = compute_metrics(b)

    return ComparisonReport(
        a_metrics=a_metrics,
        b_metrics=b_metrics,
        cost_diff=a_metrics.total_cost - b_metrics.total_cost,
        turns_diff=a_metrics.total_turns - b_metrics.total_turns,
        both_succeeded=a.success and b.success,
    )


def aggregate_results(results: List[Any]) -> AggregateReport:
    """Aggregate multiple eval results into a benchmark report.

    Accepts a list of objects with `success`, `duration_seconds`,
    and optional `trajectory` fields (matching EvalResult shape).
    """
    if not results:
        return AggregateReport()

    total = len(results)
    success_count = sum(1 for r in results if getattr(r, "success", False))
    success_rate = success_count / total

    durations: List[float] = []
    costs: List[float] = []
    turns_list: List[int] = []
    tool_counter: Counter[str] = Counter()

    for r in results:
        duration = getattr(r, "duration_seconds", 0.0)
        durations.append(duration)

        traj = getattr(r, "trajectory", None)
        if traj is not None:
            metrics = compute_metrics(traj)
            costs.append(metrics.total_cost)
            turns_list.append(metrics.total_turns)
            for tool_name, count in metrics.tool_distribution.items():
                tool_counter[tool_name] += count

    avg_cost = sum(costs) / len(costs) if costs else 0.0
    avg_turns = sum(turns_list) / len(turns_list) if turns_list else 0.0
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    return AggregateReport(
        total_instances=total,
        success_count=success_count,
        success_rate=success_rate,
        avg_cost=avg_cost,
        avg_turns=avg_turns,
        avg_duration=avg_duration,
        tool_usage=dict(tool_counter),
    )

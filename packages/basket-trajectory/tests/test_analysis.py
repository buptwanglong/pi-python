"""Tests for trajectory analysis functions."""

import pytest
from typing import Any

from basket_trajectory.schema import (
    TaskTrajectory,
    ToolCallRecord,
    TurnRecord,
)
from basket_trajectory.analysis import (
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


# ── Fixtures ──────────────────────────────────────────────────────────────


def _make_tool_call(
    name: str = "bash",
    call_id: str = "tc1",
    args: dict[str, Any] | None = None,
    error: str | None = None,
) -> ToolCallRecord:
    return ToolCallRecord(
        tool_name=name,
        tool_call_id=call_id,
        arguments=args or {},
        error=error,
    )


def _make_turn(
    index: int,
    tool_calls: list[ToolCallRecord] | None = None,
) -> TurnRecord:
    return TurnRecord(
        turn_index=index,
        input_messages=[],
        assistant_message={"role": "assistant", "content": []},
        tool_calls=tool_calls or [],
    )


def _make_trajectory(
    turns: list[TurnRecord] | None = None,
    success: bool = True,
    started_at: float = 1000.0,
    ended_at: float = 1010.0,
    usage: dict[str, Any] | None = None,
    total_turns: int | None = None,
) -> TaskTrajectory:
    t_list = turns or []
    return TaskTrajectory(
        task_id="test-task",
        started_at=started_at,
        ended_at=ended_at,
        model_provider="anthropic",
        model_id="claude-3",
        success=success,
        user_input="Hello",
        turns=t_list,
        total_turns=total_turns if total_turns is not None else len(t_list),
        total_usage=usage
        or {"input": 100, "output": 200, "total_tokens": 300, "cost_total": 0.05},
    )


# ── compute_metrics ──────────────────────────────────────────────────────


class TestComputeMetrics:
    def test_empty_trajectory(self) -> None:
        traj = _make_trajectory(turns=[], total_turns=0)
        metrics = compute_metrics(traj)
        assert metrics.total_turns == 0
        assert metrics.error_count == 0
        assert metrics.unique_tools_used == 0
        assert metrics.tokens_per_turn == 0.0

    def test_basic_metrics(self) -> None:
        turns = [
            _make_turn(1, [_make_tool_call("bash", "tc1")]),
            _make_turn(2, [_make_tool_call("read", "tc2")]),
            _make_turn(3, [_make_tool_call("bash", "tc3")]),
        ]
        traj = _make_trajectory(
            turns=turns,
            usage={"input": 150, "output": 300, "total_tokens": 450, "cost_total": 0.1},
        )
        metrics = compute_metrics(traj)
        assert metrics.total_turns == 3
        assert metrics.total_input_tokens == 150
        assert metrics.total_output_tokens == 300
        assert metrics.total_tokens == 450
        assert metrics.total_cost == 0.1
        assert metrics.tokens_per_turn == 150.0
        assert metrics.tool_distribution == {"bash": 2, "read": 1}
        assert metrics.unique_tools_used == 2
        assert metrics.error_count == 0
        assert metrics.error_rate == 0.0

    def test_error_rate(self) -> None:
        turns = [
            _make_turn(
                1,
                [
                    _make_tool_call("bash", "tc1", error="command not found"),
                    _make_tool_call("bash", "tc2"),
                ],
            ),
        ]
        traj = _make_trajectory(turns=turns, total_turns=1)
        metrics = compute_metrics(traj)
        assert metrics.error_count == 1
        assert metrics.error_rate == 0.5  # 1 error out of 2 calls

    def test_duration(self) -> None:
        traj = _make_trajectory(started_at=100.0, ended_at=150.0)
        metrics = compute_metrics(traj)
        assert metrics.duration_seconds == 50.0

    def test_frozen(self) -> None:
        traj = _make_trajectory()
        metrics = compute_metrics(traj)
        with pytest.raises(Exception):
            metrics.total_turns = 999  # type: ignore[misc]


# ── detect_loops ─────────────────────────────────────────────────────────


class TestDetectLoops:
    def test_no_loops(self) -> None:
        turns = [
            _make_turn(1, [_make_tool_call("bash", "tc1")]),
            _make_turn(2, [_make_tool_call("read", "tc2")]),
            _make_turn(3, [_make_tool_call("write", "tc3")]),
        ]
        traj = _make_trajectory(turns=turns)
        loops = detect_loops(traj, threshold=3)
        assert loops == []

    def test_simple_loop(self) -> None:
        turns = [
            _make_turn(i, [_make_tool_call("bash", f"tc{i}")])
            for i in range(1, 6)
        ]
        traj = _make_trajectory(turns=turns, total_turns=5)
        loops = detect_loops(traj, threshold=3)
        assert len(loops) >= 1
        loop = loops[0]
        assert loop.pattern == ["bash"]
        assert loop.occurrences >= 3

    def test_multi_tool_loop(self) -> None:
        """Detect a repeating pattern of [bash, read]."""
        turns = []
        for i in range(6):
            idx = i + 1
            if i % 2 == 0:
                turns.append(_make_turn(idx, [_make_tool_call("bash", f"tc{idx}")]))
            else:
                turns.append(_make_turn(idx, [_make_tool_call("read", f"tc{idx}")]))
        traj = _make_trajectory(turns=turns, total_turns=6)
        loops = detect_loops(traj, threshold=3)
        assert any(loop.pattern == ["bash", "read"] for loop in loops)

    def test_threshold_respected(self) -> None:
        """Two repetitions should not trigger with threshold=3."""
        turns = [
            _make_turn(1, [_make_tool_call("bash", "tc1")]),
            _make_turn(2, [_make_tool_call("bash", "tc2")]),
        ]
        traj = _make_trajectory(turns=turns, total_turns=2)
        loops = detect_loops(traj, threshold=3)
        assert loops == []

    def test_empty_trajectory(self) -> None:
        traj = _make_trajectory(turns=[], total_turns=0)
        loops = detect_loops(traj, threshold=3)
        assert loops == []


# ── detect_wasted_turns ──────────────────────────────────────────────────


class TestDetectWastedTurns:
    def test_no_wasted_turns(self) -> None:
        turns = [
            _make_turn(1, [_make_tool_call("bash", "tc1")]),
            _make_turn(2, [_make_tool_call("read", "tc2")]),
        ]
        traj = _make_trajectory(turns=turns)
        wasted = detect_wasted_turns(traj)
        assert wasted == []

    def test_wasted_turn_detected(self) -> None:
        args = {"command": "ls /nonexistent"}
        turns = [
            _make_turn(
                1,
                [_make_tool_call("bash", "tc1", args=args, error="No such directory")],
            ),
            _make_turn(
                2,
                [_make_tool_call("bash", "tc2", args=args)],
            ),
        ]
        traj = _make_trajectory(turns=turns)
        wasted = detect_wasted_turns(traj)
        assert len(wasted) == 1
        assert wasted[0].turn_index == 1
        assert wasted[0].tool_name == "bash"
        assert "No such directory" in wasted[0].error

    def test_different_args_not_wasted(self) -> None:
        turns = [
            _make_turn(
                1,
                [
                    _make_tool_call(
                        "bash", "tc1", args={"command": "ls /a"}, error="fail"
                    )
                ],
            ),
            _make_turn(
                2,
                [_make_tool_call("bash", "tc2", args={"command": "ls /b"})],
            ),
        ]
        traj = _make_trajectory(turns=turns)
        wasted = detect_wasted_turns(traj)
        assert wasted == []

    def test_no_error_not_wasted(self) -> None:
        args = {"command": "echo hello"}
        turns = [
            _make_turn(1, [_make_tool_call("bash", "tc1", args=args)]),
            _make_turn(2, [_make_tool_call("bash", "tc2", args=args)]),
        ]
        traj = _make_trajectory(turns=turns)
        wasted = detect_wasted_turns(traj)
        assert wasted == []

    def test_empty_trajectory(self) -> None:
        traj = _make_trajectory(turns=[], total_turns=0)
        wasted = detect_wasted_turns(traj)
        assert wasted == []

    def test_multiple_wasted_turns(self) -> None:
        args = {"command": "bad_cmd"}
        turns = [
            _make_turn(
                1,
                [_make_tool_call("bash", "tc1", args=args, error="not found")],
            ),
            _make_turn(
                2,
                [_make_tool_call("bash", "tc2", args=args, error="not found")],
            ),
            _make_turn(
                3,
                [_make_tool_call("bash", "tc3", args=args)],
            ),
        ]
        traj = _make_trajectory(turns=turns, total_turns=3)
        wasted = detect_wasted_turns(traj)
        # Turn 1 errored and retried in turn 2, turn 2 errored and retried in turn 3
        assert len(wasted) == 2
        assert wasted[0].turn_index == 1
        assert wasted[1].turn_index == 2


# ── compare_trajectories ────────────────────────────────────────────────


class TestCompareTrajectories:
    def test_compare_same_trajectory(self) -> None:
        traj = _make_trajectory(
            turns=[_make_turn(1, [_make_tool_call("bash", "tc1")])],
            total_turns=1,
        )
        report = compare_trajectories(traj, traj)
        assert report.cost_diff == 0.0
        assert report.turns_diff == 0
        assert report.both_succeeded is True

    def test_compare_different_trajectories(self) -> None:
        traj_a = _make_trajectory(
            turns=[
                _make_turn(1, [_make_tool_call("bash", "tc1")]),
                _make_turn(2, [_make_tool_call("read", "tc2")]),
            ],
            total_turns=2,
            usage={"input": 100, "output": 200, "total_tokens": 300, "cost_total": 0.10},
        )
        traj_b = _make_trajectory(
            turns=[
                _make_turn(1, [_make_tool_call("bash", "tc1")]),
            ],
            total_turns=1,
            usage={"input": 50, "output": 100, "total_tokens": 150, "cost_total": 0.03},
        )
        report = compare_trajectories(traj_a, traj_b)
        assert report.turns_diff == 1  # a has 1 more turn
        assert report.cost_diff == pytest.approx(0.07, abs=1e-9)
        assert report.a_metrics.total_turns == 2
        assert report.b_metrics.total_turns == 1

    def test_both_succeeded(self) -> None:
        traj_a = _make_trajectory(success=True)
        traj_b = _make_trajectory(success=False)
        report = compare_trajectories(traj_a, traj_b)
        assert report.both_succeeded is False

    def test_frozen(self) -> None:
        traj = _make_trajectory()
        report = compare_trajectories(traj, traj)
        with pytest.raises(Exception):
            report.cost_diff = 999.0  # type: ignore[misc]


# ── aggregate_results ────────────────────────────────────────────────────


class _MockEvalResult:
    """Lightweight mock of EvalResult for aggregate_results tests."""

    def __init__(
        self,
        success: bool = True,
        duration_seconds: float = 5.0,
        trajectory: TaskTrajectory | None = None,
    ):
        self.success = success
        self.duration_seconds = duration_seconds
        self.trajectory = trajectory


class TestAggregateResults:
    def test_empty_results(self) -> None:
        report = aggregate_results([])
        assert report.total_instances == 0
        assert report.success_rate == 0.0
        assert report.tool_usage == {}

    def test_all_success(self) -> None:
        traj = _make_trajectory(
            turns=[_make_turn(1, [_make_tool_call("bash", "tc1")])],
            usage={"input": 100, "output": 200, "total_tokens": 300, "cost_total": 0.05},
        )
        results = [
            _MockEvalResult(success=True, duration_seconds=5.0, trajectory=traj),
            _MockEvalResult(success=True, duration_seconds=10.0, trajectory=traj),
        ]
        report = aggregate_results(results)
        assert report.total_instances == 2
        assert report.success_count == 2
        assert report.success_rate == 1.0
        assert report.avg_duration == 7.5
        assert report.avg_cost == 0.05
        assert report.tool_usage == {"bash": 2}

    def test_mixed_success(self) -> None:
        traj = _make_trajectory(success=True)
        results = [
            _MockEvalResult(success=True, duration_seconds=5.0, trajectory=traj),
            _MockEvalResult(success=False, duration_seconds=3.0, trajectory=None),
            _MockEvalResult(success=True, duration_seconds=7.0, trajectory=traj),
        ]
        report = aggregate_results(results)
        assert report.total_instances == 3
        assert report.success_count == 2
        assert report.success_rate == pytest.approx(2 / 3)
        assert report.avg_duration == 5.0

    def test_no_trajectories(self) -> None:
        results = [
            _MockEvalResult(success=True, duration_seconds=1.0, trajectory=None),
            _MockEvalResult(success=False, duration_seconds=2.0, trajectory=None),
        ]
        report = aggregate_results(results)
        assert report.avg_cost == 0.0
        assert report.avg_turns == 0.0
        assert report.tool_usage == {}

    def test_tool_usage_aggregation(self) -> None:
        traj_a = _make_trajectory(
            turns=[
                _make_turn(1, [_make_tool_call("bash", "tc1")]),
                _make_turn(2, [_make_tool_call("read", "tc2")]),
            ],
        )
        traj_b = _make_trajectory(
            turns=[
                _make_turn(1, [_make_tool_call("bash", "tc1")]),
                _make_turn(2, [_make_tool_call("write", "tc2")]),
            ],
        )
        results = [
            _MockEvalResult(success=True, trajectory=traj_a),
            _MockEvalResult(success=True, trajectory=traj_b),
        ]
        report = aggregate_results(results)
        assert report.tool_usage["bash"] == 2
        assert report.tool_usage["read"] == 1
        assert report.tool_usage["write"] == 1

    def test_frozen(self) -> None:
        report = aggregate_results([])
        with pytest.raises(Exception):
            report.total_instances = 999  # type: ignore[misc]


# ── Model frozen checks ─────────────────────────────────────────────────


class TestModelsFrozen:
    def test_loop_detection_frozen(self) -> None:
        ld = LoopDetection(
            pattern=["bash"], occurrences=3, start_turn=1, end_turn=3
        )
        with pytest.raises(Exception):
            ld.occurrences = 5  # type: ignore[misc]

    def test_wasted_turn_frozen(self) -> None:
        wt = WastedTurn(turn_index=1, tool_name="bash", error="fail")
        with pytest.raises(Exception):
            wt.error = "new"  # type: ignore[misc]

    def test_comparison_report_frozen(self) -> None:
        m = TrajectoryMetrics()
        cr = ComparisonReport(a_metrics=m, b_metrics=m)
        with pytest.raises(Exception):
            cr.both_succeeded = True  # type: ignore[misc]

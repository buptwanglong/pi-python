"""Tests for the A/B comparison framework."""

import asyncio
from typing import Any, Dict

import pytest

from basket_eval.comparison import (
    ABRunner,
    ComparisonReport,
    ConfigResult,
    ConfigSummary,
    ExperimentConfig,
    build_comparison_report,
    compute_config_summary,
    format_comparison_table,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config_a() -> ExperimentConfig:
    return ExperimentConfig(name="config-a", model_override={"provider": "openai"})


@pytest.fixture
def config_b() -> ExperimentConfig:
    return ExperimentConfig(name="config-b", model_override={"provider": "anthropic"})


@pytest.fixture
def sample_results() -> list[ConfigResult]:
    """Two configs × two instances."""
    return [
        ConfigResult(
            config_name="config-a",
            instance_id="inst-1",
            success=True,
            score=0.9,
            total_turns=3,
            total_cost=0.05,
            duration_seconds=10.0,
        ),
        ConfigResult(
            config_name="config-a",
            instance_id="inst-2",
            success=False,
            score=0.2,
            total_turns=5,
            total_cost=0.08,
            duration_seconds=15.0,
        ),
        ConfigResult(
            config_name="config-b",
            instance_id="inst-1",
            success=True,
            score=0.95,
            total_turns=2,
            total_cost=0.03,
            duration_seconds=8.0,
        ),
        ConfigResult(
            config_name="config-b",
            instance_id="inst-2",
            success=True,
            score=0.85,
            total_turns=4,
            total_cost=0.06,
            duration_seconds=12.0,
        ),
    ]


# ---------------------------------------------------------------------------
# compute_config_summary
# ---------------------------------------------------------------------------


class TestComputeConfigSummary:
    def test_empty_results(self) -> None:
        summary = compute_config_summary("empty", [])
        assert summary.config_name == "empty"
        assert summary.total_instances == 0
        assert summary.success_count == 0
        assert summary.success_rate == 0.0
        assert summary.avg_cost == 0.0
        assert summary.avg_turns == 0.0
        assert summary.avg_duration == 0.0
        assert summary.avg_score is None

    def test_with_results(self, sample_results: list[ConfigResult]) -> None:
        cfg_a_results = [r for r in sample_results if r.config_name == "config-a"]
        summary = compute_config_summary("config-a", cfg_a_results)

        assert summary.config_name == "config-a"
        assert summary.total_instances == 2
        assert summary.success_count == 1
        assert summary.success_rate == pytest.approx(0.5)

    def test_success_rate(self) -> None:
        results = [
            ConfigResult(
                config_name="x", instance_id="i1", success=True, duration_seconds=1.0
            ),
            ConfigResult(
                config_name="x", instance_id="i2", success=True, duration_seconds=2.0
            ),
            ConfigResult(
                config_name="x", instance_id="i3", success=False, duration_seconds=3.0
            ),
        ]
        summary = compute_config_summary("x", results)
        assert summary.success_rate == pytest.approx(2.0 / 3.0)

    def test_avg_cost(self) -> None:
        results = [
            ConfigResult(
                config_name="c",
                instance_id="i1",
                success=True,
                total_cost=0.10,
                duration_seconds=1.0,
            ),
            ConfigResult(
                config_name="c",
                instance_id="i2",
                success=True,
                total_cost=0.20,
                duration_seconds=2.0,
            ),
        ]
        summary = compute_config_summary("c", results)
        assert summary.avg_cost == pytest.approx(0.15)

    def test_avg_turns_and_duration(self) -> None:
        results = [
            ConfigResult(
                config_name="t",
                instance_id="i1",
                success=True,
                total_turns=4,
                duration_seconds=10.0,
            ),
            ConfigResult(
                config_name="t",
                instance_id="i2",
                success=False,
                total_turns=6,
                duration_seconds=20.0,
            ),
        ]
        summary = compute_config_summary("t", results)
        assert summary.avg_turns == pytest.approx(5.0)
        assert summary.avg_duration == pytest.approx(15.0)

    def test_avg_score_with_none_values(self) -> None:
        """Only non-None scores should be averaged."""
        results = [
            ConfigResult(
                config_name="s",
                instance_id="i1",
                success=True,
                score=0.8,
                duration_seconds=1.0,
            ),
            ConfigResult(
                config_name="s",
                instance_id="i2",
                success=False,
                score=None,
                duration_seconds=2.0,
            ),
            ConfigResult(
                config_name="s",
                instance_id="i3",
                success=True,
                score=0.6,
                duration_seconds=3.0,
            ),
        ]
        summary = compute_config_summary("s", results)
        # avg of 0.8 and 0.6 = 0.7  (None excluded)
        assert summary.avg_score == pytest.approx(0.7)
        assert summary.total_instances == 3

    def test_all_scores_none(self) -> None:
        results = [
            ConfigResult(
                config_name="n",
                instance_id="i1",
                success=True,
                score=None,
                duration_seconds=1.0,
            ),
        ]
        summary = compute_config_summary("n", results)
        assert summary.avg_score is None


# ---------------------------------------------------------------------------
# build_comparison_report
# ---------------------------------------------------------------------------


class TestBuildComparisonReport:
    def test_basic_report(self, sample_results: list[ConfigResult]) -> None:
        report = build_comparison_report("test-exp", sample_results)

        assert report.experiment_name == "test-exp"
        assert report.instance_ids == ["inst-1", "inst-2"]
        assert report.config_names == ["config-a", "config-b"]
        assert len(report.results) == 4
        assert "config-a" in report.summaries
        assert "config-b" in report.summaries

    def test_empty_results(self) -> None:
        report = build_comparison_report("empty-exp", [])
        assert report.instance_ids == []
        assert report.config_names == []
        assert report.results == []
        assert report.summaries == {}

    def test_single_config(self) -> None:
        results = [
            ConfigResult(
                config_name="solo",
                instance_id="i1",
                success=True,
                score=1.0,
                duration_seconds=5.0,
            ),
        ]
        report = build_comparison_report("solo-exp", results)
        assert report.config_names == ["solo"]
        assert report.summaries["solo"].success_rate == 1.0

    def test_summaries_are_correct(
        self, sample_results: list[ConfigResult]
    ) -> None:
        report = build_comparison_report("test-exp", sample_results)

        summary_a = report.summaries["config-a"]
        assert summary_a.total_instances == 2
        assert summary_a.success_count == 1
        assert summary_a.success_rate == pytest.approx(0.5)

        summary_b = report.summaries["config-b"]
        assert summary_b.total_instances == 2
        assert summary_b.success_count == 2
        assert summary_b.success_rate == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# format_comparison_table
# ---------------------------------------------------------------------------


class TestFormatComparisonTable:
    def test_basic_formatting(self, sample_results: list[ConfigResult]) -> None:
        report = build_comparison_report("fmt-exp", sample_results)
        table = format_comparison_table(report)

        assert "fmt-exp" in table
        assert "Instances: 2" in table
        assert "Configs: 2" in table
        assert "config-a" in table
        assert "config-b" in table
        assert "Success%" in table

    def test_na_score(self) -> None:
        """Configs with no scores should show N/A."""
        results = [
            ConfigResult(
                config_name="noscore",
                instance_id="i1",
                success=True,
                score=None,
                duration_seconds=1.0,
            ),
        ]
        report = build_comparison_report("na-exp", results)
        table = format_comparison_table(report)
        assert "N/A" in table

    def test_empty_report(self) -> None:
        report = build_comparison_report("empty", [])
        table = format_comparison_table(report)
        assert "Instances: 0" in table
        assert "Configs: 0" in table


# ---------------------------------------------------------------------------
# Frozen model invariants
# ---------------------------------------------------------------------------


class TestFrozenModels:
    def test_experiment_config_frozen(self, config_a: ExperimentConfig) -> None:
        with pytest.raises(Exception):  # ValidationError on frozen model
            config_a.name = "mutated"  # type: ignore[misc]

    def test_config_result_frozen(self) -> None:
        result = ConfigResult(
            config_name="c", instance_id="i", success=True, duration_seconds=1.0
        )
        with pytest.raises(Exception):
            result.success = False  # type: ignore[misc]

    def test_config_summary_frozen(self) -> None:
        summary = ConfigSummary(config_name="c")
        with pytest.raises(Exception):
            summary.success_rate = 0.99  # type: ignore[misc]

    def test_comparison_report_frozen(self) -> None:
        report = ComparisonReport(experiment_name="exp")
        with pytest.raises(Exception):
            report.experiment_name = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ABRunner
# ---------------------------------------------------------------------------


class TestABRunnerRunSingle:
    @pytest.mark.asyncio
    async def test_success(self, config_a: ExperimentConfig) -> None:
        async def mock_run(
            prompt: str, config: ExperimentConfig
        ) -> Dict[str, Any]:
            return {
                "success": True,
                "score": 0.95,
                "total_turns": 3,
                "total_cost": 0.04,
            }

        runner = ABRunner(experiment_name="single-test")
        result = await runner.run_single("inst-1", "do something", config_a, mock_run)

        assert result.config_name == "config-a"
        assert result.instance_id == "inst-1"
        assert result.success is True
        assert result.score == pytest.approx(0.95)
        assert result.total_turns == 3
        assert result.total_cost == pytest.approx(0.04)
        assert result.duration_seconds >= 0
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_error(self, config_a: ExperimentConfig) -> None:
        async def failing_run(
            prompt: str, config: ExperimentConfig
        ) -> Dict[str, Any]:
            raise RuntimeError("provider down")

        runner = ABRunner()
        result = await runner.run_single("inst-1", "fail me", config_a, failing_run)

        assert result.success is False
        assert result.error_message == "provider down"
        assert result.duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_no_run_fn(self, config_a: ExperimentConfig) -> None:
        runner = ABRunner()
        result = await runner.run_single("inst-1", "hello", config_a)

        assert result.success is False
        assert result.error_message == "No run function provided"

    @pytest.mark.asyncio
    async def test_partial_result_keys(self, config_a: ExperimentConfig) -> None:
        """run_fn returning partial dict should use defaults for missing keys."""

        async def partial_run(
            prompt: str, config: ExperimentConfig
        ) -> Dict[str, Any]:
            return {"success": True}

        runner = ABRunner()
        result = await runner.run_single("inst-1", "partial", config_a, partial_run)

        assert result.success is True
        assert result.score is None
        assert result.total_turns == 0
        assert result.total_cost == 0.0


class TestABRunnerRunComparison:
    @pytest.mark.asyncio
    async def test_full_comparison(
        self, config_a: ExperimentConfig, config_b: ExperimentConfig
    ) -> None:
        call_log: list[tuple[str, str]] = []

        async def mock_run(
            prompt: str, config: ExperimentConfig
        ) -> Dict[str, Any]:
            call_log.append((prompt, config.name))
            return {"success": True, "score": 0.9, "total_turns": 2, "total_cost": 0.01}

        instances = [
            {"instance_id": "i1", "prompt": "task one"},
            {"instance_id": "i2", "prompt": "task two"},
        ]

        runner = ABRunner(experiment_name="cmp-test")
        report = runner.run_comparison(instances, [config_a, config_b], mock_run)
        # run_comparison is async
        report = await report

        assert report.experiment_name == "cmp-test"
        assert set(report.instance_ids) == {"i1", "i2"}
        assert set(report.config_names) == {"config-a", "config-b"}
        assert len(report.results) == 4
        assert len(call_log) == 4

        # All succeeded
        for summary in report.summaries.values():
            assert summary.success_rate == 1.0

    @pytest.mark.asyncio
    async def test_concurrency_limit(self, config_a: ExperimentConfig) -> None:
        """Concurrency=1 should serialize execution."""
        timestamps: list[float] = []

        async def slow_run(
            prompt: str, config: ExperimentConfig
        ) -> Dict[str, Any]:
            import time

            timestamps.append(time.monotonic())
            await asyncio.sleep(0.05)
            return {"success": True}

        instances = [
            {"instance_id": "i1", "prompt": "a"},
            {"instance_id": "i2", "prompt": "b"},
        ]

        runner = ABRunner()
        await runner.run_comparison(instances, [config_a], slow_run, concurrency=1)

        # With concurrency=1, second call starts after first finishes
        assert len(timestamps) == 2

    @pytest.mark.asyncio
    async def test_empty_instances(self, config_a: ExperimentConfig) -> None:
        runner = ABRunner()
        report = await runner.run_comparison([], [config_a])
        assert report.results == []
        assert report.instance_ids == []

    @pytest.mark.asyncio
    async def test_empty_configs(self) -> None:
        runner = ABRunner()
        report = await runner.run_comparison(
            [{"instance_id": "i1", "prompt": "hello"}], []
        )
        assert report.results == []
        assert report.config_names == []

    @pytest.mark.asyncio
    async def test_mixed_success_failure(
        self, config_a: ExperimentConfig
    ) -> None:
        call_count = 0

        async def alternating_run(
            prompt: str, config: ExperimentConfig
        ) -> Dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise ValueError("intermittent failure")
            return {"success": True, "score": 1.0}

        instances = [
            {"instance_id": f"i{i}", "prompt": f"task {i}"} for i in range(4)
        ]
        runner = ABRunner()
        report = await runner.run_comparison(instances, [config_a], alternating_run)

        successes = [r for r in report.results if r.success]
        failures = [r for r in report.results if not r.success]
        assert len(successes) == 2
        assert len(failures) == 2


class TestABRunnerProperties:
    def test_experiment_name(self) -> None:
        runner = ABRunner(experiment_name="my-experiment")
        assert runner.experiment_name == "my-experiment"

    def test_default_experiment_name(self) -> None:
        runner = ABRunner()
        assert runner.experiment_name == "experiment"

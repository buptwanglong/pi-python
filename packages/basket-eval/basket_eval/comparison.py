"""
A/B comparison framework for evaluating agent configurations.

Runs the same tasks across multiple configs and generates comparison reports.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class ExperimentConfig(BaseModel):
    """Configuration for one arm of an A/B experiment."""

    name: str
    model_override: Optional[Dict[str, str]] = None  # {"provider": ..., "model_id": ...}
    prompt_override: Optional[str] = None  # Prefix/suffix to add to task prompt
    tool_override: Optional[List[str]] = None  # Tool names to include (None = all)
    settings_override: Optional[Dict[str, Any]] = None  # Additional settings
    max_turns_override: Optional[int] = None

    model_config = ConfigDict(frozen=True)


class ConfigResult(BaseModel):
    """Result for a single config on a single instance."""

    config_name: str
    instance_id: str
    success: bool
    score: Optional[float] = None
    error_message: Optional[str] = None
    total_turns: int = 0
    total_cost: float = 0.0
    duration_seconds: float = 0.0

    model_config = ConfigDict(frozen=True)


class ConfigSummary(BaseModel):
    """Aggregated summary for one configuration."""

    config_name: str
    total_instances: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    avg_cost: float = 0.0
    avg_turns: float = 0.0
    avg_duration: float = 0.0
    avg_score: Optional[float] = None

    model_config = ConfigDict(frozen=True)


class ComparisonReport(BaseModel):
    """Full comparison report across configs and instances."""

    experiment_name: str
    created_at: float = Field(default_factory=time.time)
    instance_ids: List[str] = Field(default_factory=list)
    config_names: List[str] = Field(default_factory=list)
    results: List[ConfigResult] = Field(default_factory=list)
    summaries: Dict[str, ConfigSummary] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


# Type alias for the pluggable run function.
RunFn = Callable[
    [str, ExperimentConfig],
    Coroutine[Any, Any, Dict[str, Any]],
]


def compute_config_summary(
    config_name: str, results: List[ConfigResult]
) -> ConfigSummary:
    """Compute summary statistics for a single configuration."""
    if not results:
        return ConfigSummary(config_name=config_name)

    success_count = sum(1 for r in results if r.success)
    total = len(results)
    costs = [r.total_cost for r in results]
    turns = [r.total_turns for r in results]
    durations = [r.duration_seconds for r in results]
    scores = [r.score for r in results if r.score is not None]

    return ConfigSummary(
        config_name=config_name,
        total_instances=total,
        success_count=success_count,
        success_rate=success_count / total if total > 0 else 0.0,
        avg_cost=sum(costs) / total if total > 0 else 0.0,
        avg_turns=sum(turns) / total if total > 0 else 0.0,
        avg_duration=sum(durations) / total if total > 0 else 0.0,
        avg_score=sum(scores) / len(scores) if scores else None,
    )


def build_comparison_report(
    experiment_name: str,
    results: List[ConfigResult],
) -> ComparisonReport:
    """Build a full comparison report from individual results."""
    instance_ids = sorted(set(r.instance_id for r in results))
    config_names = sorted(set(r.config_name for r in results))

    summaries: Dict[str, ConfigSummary] = {}
    for cfg_name in config_names:
        cfg_results = [r for r in results if r.config_name == cfg_name]
        summaries[cfg_name] = compute_config_summary(cfg_name, cfg_results)

    return ComparisonReport(
        experiment_name=experiment_name,
        instance_ids=instance_ids,
        config_names=config_names,
        results=results,
        summaries=summaries,
    )


def format_comparison_table(report: ComparisonReport) -> str:
    """Format comparison report as a human-readable table."""
    lines = [
        f"Experiment: {report.experiment_name}",
        f"Instances: {len(report.instance_ids)}",
        f"Configs: {len(report.config_names)}",
        "",
        f"{'Config':<20} {'Success%':>10} {'Avg Cost':>10} "
        f"{'Avg Turns':>10} {'Avg Time':>10} {'Avg Score':>10}",
        "-" * 72,
    ]

    for cfg_name in report.config_names:
        summary = report.summaries[cfg_name]
        score_str = (
            f"{summary.avg_score:.2f}" if summary.avg_score is not None else "N/A"
        )
        lines.append(
            f"{cfg_name:<20} {summary.success_rate * 100:>9.1f}% "
            f"{summary.avg_cost:>10.4f} {summary.avg_turns:>10.1f} "
            f"{summary.avg_duration:>9.1f}s {score_str:>10}"
        )

    return "\n".join(lines)


class ABRunner:
    """
    A/B comparison runner.

    Runs task instances across multiple configurations and compares results.
    Accepts a pluggable ``run_fn`` that executes a prompt under a given config
    and returns a dict with keys: success, score, total_turns, total_cost.
    """

    def __init__(self, experiment_name: str = "experiment") -> None:
        self._experiment_name = experiment_name

    @property
    def experiment_name(self) -> str:
        return self._experiment_name

    async def run_single(
        self,
        instance_id: str,
        prompt: str,
        config: ExperimentConfig,
        run_fn: Optional[RunFn] = None,
    ) -> ConfigResult:
        """Run a single instance with a single config."""
        start_time = time.time()

        try:
            if run_fn is not None:
                result = await run_fn(prompt, config)
                duration = time.time() - start_time
                return ConfigResult(
                    config_name=config.name,
                    instance_id=instance_id,
                    success=result.get("success", False),
                    score=result.get("score"),
                    total_turns=result.get("total_turns", 0),
                    total_cost=result.get("total_cost", 0.0),
                    duration_seconds=duration,
                )
            else:
                # No run_fn provided – nothing to execute.
                duration = time.time() - start_time
                return ConfigResult(
                    config_name=config.name,
                    instance_id=instance_id,
                    success=False,
                    error_message="No run function provided",
                    duration_seconds=duration,
                )
        except Exception as exc:
            duration = time.time() - start_time
            return ConfigResult(
                config_name=config.name,
                instance_id=instance_id,
                success=False,
                error_message=str(exc),
                duration_seconds=duration,
            )

    async def run_comparison(
        self,
        instances: List[Dict[str, str]],  # [{"instance_id": ..., "prompt": ...}]
        configs: List[ExperimentConfig],
        run_fn: Optional[RunFn] = None,
        concurrency: int = 1,
    ) -> ComparisonReport:
        """Run comparison: all instances × all configs.

        Args:
            instances: List of dicts, each with ``instance_id`` and ``prompt``.
            configs: Experiment configurations to compare.
            run_fn: Async callable ``(prompt, config) -> dict``.
            concurrency: Maximum number of concurrent runs.

        Returns:
            A :class:`ComparisonReport` with per-config summaries.
        """
        semaphore = asyncio.Semaphore(max(concurrency, 1))

        async def _run_with_semaphore(
            inst: Dict[str, str], cfg: ExperimentConfig
        ) -> ConfigResult:
            async with semaphore:
                return await self.run_single(
                    inst["instance_id"], inst["prompt"], cfg, run_fn
                )

        tasks = [
            _run_with_semaphore(inst, cfg)
            for inst in instances
            for cfg in configs
        ]

        gathered = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: List[ConfigResult] = []
        for item in gathered:
            if isinstance(item, Exception):
                logger.error("Comparison run error: %s", item)
            elif isinstance(item, ConfigResult):
                all_results.append(item)

        return build_comparison_report(self._experiment_name, all_results)

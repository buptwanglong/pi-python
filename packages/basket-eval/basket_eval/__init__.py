"""
basket-eval: Evaluation framework for basket AI agents.

Provides task instance schema, oracle evaluation, headless runner,
A/B comparison framework, and LLM-as-Judge scoring pipeline.
"""

from .comparison import (
    ABRunner,
    ComparisonReport,
    ConfigResult,
    ConfigSummary,
    ExperimentConfig,
    build_comparison_report,
    compute_config_summary,
    format_comparison_table,
)
from .judge import (
    DimensionScore,
    JudgeConfig,
    JudgeResult,
    ScoringType,
    build_judge_prompt,
    llm_judge,
    parse_judge_response,
)
from .oracles import evaluate_oracle
from .runner import EvalRunner
from .schema import (
    EvalResult,
    OracleType,
    TaskInstance,
    TaskOracle,
    TaskSetup,
)

__all__ = [
    "ABRunner",
    "ComparisonReport",
    "ConfigResult",
    "ConfigSummary",
    "DimensionScore",
    "EvalResult",
    "EvalRunner",
    "ExperimentConfig",
    "JudgeConfig",
    "JudgeResult",
    "OracleType",
    "ScoringType",
    "TaskInstance",
    "TaskOracle",
    "TaskSetup",
    "build_comparison_report",
    "build_judge_prompt",
    "compute_config_summary",
    "evaluate_oracle",
    "format_comparison_table",
    "llm_judge",
    "parse_judge_response",
]

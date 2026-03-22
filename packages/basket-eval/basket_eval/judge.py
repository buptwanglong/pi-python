"""
LLM-as-Judge scoring pipeline.

Uses a strong model to evaluate agent output on subjective criteria.
Supports binary pass/fail, 1-5 scale, and multi-dimension scoring.
"""

import json
import logging
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class ScoringType(str, Enum):
    """Supported scoring modes for judge evaluation."""

    BINARY = "binary"
    SCALE_1_5 = "scale_1_5"
    CUSTOM = "custom"


class JudgeConfig(BaseModel):
    """Configuration for the LLM judge."""

    model_provider: str = "anthropic"
    model_id: str = "claude-sonnet-4-20250514"
    rubric: str
    scoring: ScoringType = ScoringType.BINARY
    dimensions: List[str] = Field(default_factory=list)
    max_tokens: int = 4096
    context_window: int = 200000

    model_config = ConfigDict(frozen=True)


class DimensionScore(BaseModel):
    """Score for a single evaluation dimension."""

    dimension: str
    score: float
    explanation: str

    model_config = ConfigDict(frozen=True)


class JudgeResult(BaseModel):
    """Result from LLM judge evaluation."""

    overall_score: float
    passed: bool
    dimension_scores: List[DimensionScore] = Field(default_factory=list)
    explanation: str = ""
    judge_model: str = ""
    raw_response: Optional[str] = None

    model_config = ConfigDict(frozen=True)


def build_judge_prompt(
    task_description: str,
    task_prompt: str,
    agent_output: str,
    rubric: str,
    scoring: ScoringType,
    dimensions: List[str],
) -> str:
    """Build the evaluation prompt for the judge model.

    Constructs a structured prompt that instructs the judge to evaluate
    the agent's output according to the rubric and scoring type.

    Args:
        task_description: High-level description of what the task is about.
        task_prompt: The exact prompt given to the agent.
        agent_output: The agent's final output to evaluate.
        rubric: Evaluation criteria / grading rubric.
        scoring: How to score (binary, scale, or custom).
        dimensions: Optional list of named dimensions to score individually.

    Returns:
        Formatted prompt string for the judge model.
    """
    prompt = f"""You are an expert evaluator assessing an AI agent's performance on a task.

## Task Description
{task_description}

## Task Prompt Given to Agent
{task_prompt}

## Agent's Final Output
{agent_output}

## Evaluation Rubric
{rubric}

## Scoring Instructions
"""

    if scoring == ScoringType.BINARY:
        prompt += """
Score as PASS or FAIL based on the rubric.
Respond in JSON format:
{"overall_score": 1.0 or 0.0, "passed": true or false, "explanation": "your reasoning"}
"""
    elif scoring == ScoringType.SCALE_1_5:
        prompt += """
Score from 1-5 based on the rubric (1=poor, 5=excellent).
Respond in JSON format:
{"overall_score": <1-5>, "passed": <true if score >= 3, false otherwise>, "explanation": "your reasoning"}
"""
    else:
        prompt += """
Score according to the rubric's custom criteria.
Respond in JSON format:
{"overall_score": <float>, "passed": <boolean>, "explanation": "your reasoning"}
"""

    if dimensions:
        dims_json = json.dumps(dimensions)
        prompt += f"""
Also score each dimension individually: {dims_json}
Include "dimension_scores": [{{"dimension": "name", "score": <float>, "explanation": "why"}}]
"""

    prompt += "\nRespond ONLY with valid JSON."
    return prompt


def _extract_json_from_text(text: str) -> str:
    """Strip markdown code fences and whitespace to expose raw JSON.

    Args:
        text: Raw response text that may contain markdown fences.

    Returns:
        Cleaned text likely to be valid JSON.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json or ```) and last line (```)
        if len(lines) > 2:
            cleaned = "\n".join(lines[1:-1])
        elif len(lines) == 2:
            cleaned = lines[1].rstrip("`")
    return cleaned.strip()


def parse_judge_response(response_text: str, scoring: ScoringType) -> JudgeResult:
    """Parse the judge model's response into a JudgeResult.

    Handles markdown code blocks and gracefully degrades on parse errors.

    Args:
        response_text: Raw text response from the judge model.
        scoring: The scoring type used (for validation context).

    Returns:
        JudgeResult with parsed scores or a failure result on parse error.
    """
    try:
        json_text = _extract_json_from_text(response_text)
        data = json.loads(json_text)

        dimension_scores = [
            DimensionScore(
                dimension=ds["dimension"],
                score=float(ds["score"]),
                explanation=ds.get("explanation", ""),
            )
            for ds in data.get("dimension_scores", [])
        ]

        return JudgeResult(
            overall_score=float(data.get("overall_score", 0)),
            passed=bool(data.get("passed", False)),
            dimension_scores=dimension_scores,
            explanation=data.get("explanation", ""),
            raw_response=response_text,
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        logger.warning("Failed to parse judge response: %s", e)
        return JudgeResult(
            overall_score=0.0,
            passed=False,
            explanation=f"Failed to parse judge response: {e}",
            raw_response=response_text,
        )


async def llm_judge(
    task_description: str,
    task_prompt: str,
    agent_output: str,
    config: JudgeConfig,
) -> JudgeResult:
    """Use a strong model to evaluate agent output.

    Calls the configured LLM provider via basket-ai's streaming API,
    then parses the response into a structured JudgeResult.

    Args:
        task_description: High-level task description.
        task_prompt: The exact prompt the agent received.
        agent_output: The agent's final output text.
        config: Judge configuration (model, rubric, scoring, etc.).

    Returns:
        JudgeResult with scores and explanations.
    """
    from basket_ai.api import get_model, stream
    from basket_ai.types import Context, UserMessage

    model = get_model(
        config.model_provider,
        config.model_id,
        context_window=config.context_window,
        max_tokens=config.max_tokens,
    )

    prompt = build_judge_prompt(
        task_description=task_description,
        task_prompt=task_prompt,
        agent_output=agent_output,
        rubric=config.rubric,
        scoring=config.scoring,
        dimensions=config.dimensions,
    )

    context = Context(
        systemPrompt="You are an expert evaluator. Always respond with valid JSON.",
        messages=[UserMessage(role="user", content=prompt, timestamp=0)],
    )

    try:
        event_stream = await stream(model, context)
        async for _ in event_stream:
            pass
        result = await event_stream.result()

        # Extract text from response content blocks
        response_text = "".join(
            block.text for block in result.content if hasattr(block, "text")
        )

        judge_result = parse_judge_response(response_text, config.scoring)
        return JudgeResult(
            overall_score=judge_result.overall_score,
            passed=judge_result.passed,
            dimension_scores=judge_result.dimension_scores,
            explanation=judge_result.explanation,
            judge_model=f"{config.model_provider}/{config.model_id}",
            raw_response=response_text,
        )
    except Exception as e:
        logger.error("LLM judge error: %s", e)
        return JudgeResult(
            overall_score=0.0,
            passed=False,
            explanation=f"Judge error: {e}",
            judge_model=f"{config.model_provider}/{config.model_id}",
        )


__all__ = [
    "DimensionScore",
    "JudgeConfig",
    "JudgeResult",
    "ScoringType",
    "build_judge_prompt",
    "llm_judge",
    "parse_judge_response",
]

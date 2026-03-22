"""Tests for LLM-as-Judge scoring pipeline."""

import json

import pytest

from basket_eval.judge import (
    DimensionScore,
    JudgeConfig,
    JudgeResult,
    ScoringType,
    build_judge_prompt,
    parse_judge_response,
)


# ---------------------------------------------------------------------------
# build_judge_prompt tests
# ---------------------------------------------------------------------------


class TestBuildJudgePrompt:
    """Tests for build_judge_prompt()."""

    def test_binary_prompt_contains_pass_fail(self):
        prompt = build_judge_prompt(
            task_description="Fix the login bug",
            task_prompt="Please fix the login page",
            agent_output="I fixed the login page.",
            rubric="Check if login works correctly",
            scoring=ScoringType.BINARY,
            dimensions=[],
        )
        assert "PASS" in prompt
        assert "FAIL" in prompt
        assert "Fix the login bug" in prompt
        assert "Please fix the login page" in prompt
        assert "I fixed the login page." in prompt
        assert "Check if login works correctly" in prompt

    def test_scale_prompt_contains_1_to_5(self):
        prompt = build_judge_prompt(
            task_description="Write a poem",
            task_prompt="Write a haiku about coding",
            agent_output="Code flows like water\nBugs hide beneath the surface\nTests reveal the truth",
            rubric="Evaluate creativity and adherence to haiku form",
            scoring=ScoringType.SCALE_1_5,
            dimensions=[],
        )
        assert "1-5" in prompt
        assert "1=poor" in prompt
        assert "5=excellent" in prompt

    def test_custom_prompt_contains_custom_criteria(self):
        prompt = build_judge_prompt(
            task_description="Refactor code",
            task_prompt="Refactor the auth module",
            agent_output="Done refactoring",
            rubric="Custom rubric here",
            scoring=ScoringType.CUSTOM,
            dimensions=[],
        )
        assert "custom criteria" in prompt.lower()

    def test_prompt_with_dimensions_includes_dimension_list(self):
        dims = ["accuracy", "completeness", "style"]
        prompt = build_judge_prompt(
            task_description="Summarize article",
            task_prompt="Summarize the following article",
            agent_output="Here is my summary.",
            rubric="Evaluate the summary quality",
            scoring=ScoringType.BINARY,
            dimensions=dims,
        )
        assert "accuracy" in prompt
        assert "completeness" in prompt
        assert "style" in prompt
        assert "dimension_scores" in prompt

    def test_prompt_without_dimensions_omits_dimension_section(self):
        prompt = build_judge_prompt(
            task_description="Simple task",
            task_prompt="Do something",
            agent_output="Done",
            rubric="Was it done?",
            scoring=ScoringType.BINARY,
            dimensions=[],
        )
        assert "dimension_scores" not in prompt

    def test_prompt_ends_with_json_instruction(self):
        prompt = build_judge_prompt(
            task_description="task",
            task_prompt="prompt",
            agent_output="output",
            rubric="rubric",
            scoring=ScoringType.BINARY,
            dimensions=[],
        )
        assert "Respond ONLY with valid JSON" in prompt


# ---------------------------------------------------------------------------
# parse_judge_response tests
# ---------------------------------------------------------------------------


class TestParseJudgeResponse:
    """Tests for parse_judge_response()."""

    def test_binary_pass(self):
        response = json.dumps({
            "overall_score": 1.0,
            "passed": True,
            "explanation": "The agent completed the task correctly.",
        })
        result = parse_judge_response(response, ScoringType.BINARY)
        assert result.overall_score == 1.0
        assert result.passed is True
        assert "completed the task" in result.explanation
        assert result.raw_response == response

    def test_binary_fail(self):
        response = json.dumps({
            "overall_score": 0.0,
            "passed": False,
            "explanation": "The agent did not address the requirements.",
        })
        result = parse_judge_response(response, ScoringType.BINARY)
        assert result.overall_score == 0.0
        assert result.passed is False
        assert "did not address" in result.explanation

    def test_scale_score(self):
        response = json.dumps({
            "overall_score": 4.0,
            "passed": True,
            "explanation": "Good work overall.",
        })
        result = parse_judge_response(response, ScoringType.SCALE_1_5)
        assert result.overall_score == 4.0
        assert result.passed is True

    def test_with_dimensions(self):
        response = json.dumps({
            "overall_score": 0.8,
            "passed": True,
            "explanation": "Mostly good.",
            "dimension_scores": [
                {"dimension": "accuracy", "score": 0.9, "explanation": "Very accurate"},
                {"dimension": "style", "score": 0.7, "explanation": "Could improve"},
            ],
        })
        result = parse_judge_response(response, ScoringType.BINARY)
        assert len(result.dimension_scores) == 2
        assert result.dimension_scores[0].dimension == "accuracy"
        assert result.dimension_scores[0].score == 0.9
        assert result.dimension_scores[1].dimension == "style"
        assert result.dimension_scores[1].score == 0.7

    def test_invalid_json_returns_failure(self):
        result = parse_judge_response("not valid json at all", ScoringType.BINARY)
        assert result.overall_score == 0.0
        assert result.passed is False
        assert "Failed to parse" in result.explanation
        assert result.raw_response == "not valid json at all"

    def test_markdown_code_block_stripped(self):
        inner = json.dumps({
            "overall_score": 1.0,
            "passed": True,
            "explanation": "Great job!",
        })
        response = f"```json\n{inner}\n```"
        result = parse_judge_response(response, ScoringType.BINARY)
        assert result.overall_score == 1.0
        assert result.passed is True
        assert result.explanation == "Great job!"

    def test_markdown_code_block_no_language(self):
        inner = json.dumps({
            "overall_score": 0.0,
            "passed": False,
            "explanation": "Failed",
        })
        response = f"```\n{inner}\n```"
        result = parse_judge_response(response, ScoringType.BINARY)
        assert result.overall_score == 0.0
        assert result.passed is False

    def test_empty_response(self):
        result = parse_judge_response("", ScoringType.BINARY)
        assert result.overall_score == 0.0
        assert result.passed is False
        assert "Failed to parse" in result.explanation

    def test_partial_json_missing_fields(self):
        response = json.dumps({"overall_score": 3.5})
        result = parse_judge_response(response, ScoringType.SCALE_1_5)
        assert result.overall_score == 3.5
        assert result.passed is False  # default when missing

    def test_dimension_missing_explanation(self):
        response = json.dumps({
            "overall_score": 1.0,
            "passed": True,
            "explanation": "OK",
            "dimension_scores": [
                {"dimension": "clarity", "score": 0.8},
            ],
        })
        result = parse_judge_response(response, ScoringType.BINARY)
        assert len(result.dimension_scores) == 1
        assert result.dimension_scores[0].explanation == ""


# ---------------------------------------------------------------------------
# Model immutability tests
# ---------------------------------------------------------------------------


class TestJudgeModels:
    """Tests for Pydantic model immutability."""

    def test_judge_config_is_frozen(self):
        config = JudgeConfig(rubric="test rubric")
        with pytest.raises(Exception):
            config.rubric = "changed"  # type: ignore[misc]

    def test_judge_result_is_frozen(self):
        result = JudgeResult(overall_score=1.0, passed=True)
        with pytest.raises(Exception):
            result.overall_score = 0.5  # type: ignore[misc]

    def test_dimension_score_is_frozen(self):
        ds = DimensionScore(dimension="test", score=0.9, explanation="good")
        with pytest.raises(Exception):
            ds.score = 0.1  # type: ignore[misc]

    def test_judge_config_defaults(self):
        config = JudgeConfig(rubric="some rubric")
        assert config.model_provider == "anthropic"
        assert config.model_id == "claude-sonnet-4-20250514"
        assert config.scoring == ScoringType.BINARY
        assert config.dimensions == []
        assert config.max_tokens == 4096

    def test_judge_result_defaults(self):
        result = JudgeResult(overall_score=0.5, passed=True)
        assert result.dimension_scores == []
        assert result.explanation == ""
        assert result.judge_model == ""
        assert result.raw_response is None

"""Tests for basket-eval schema models."""

import pytest

from basket_eval.schema import (
    EvalResult,
    OracleType,
    TaskInstance,
    TaskOracle,
    TaskSetup,
)
from basket_trajectory.schema import TaskTrajectory


class TestOracleType:
    def test_enum_values(self) -> None:
        assert OracleType.TEST_PASS == "test_pass"
        assert OracleType.FILE_DIFF == "file_diff"
        assert OracleType.LLM_JUDGE == "llm_judge"
        assert OracleType.CUSTOM_SCRIPT == "custom_script"

    def test_enum_from_string(self) -> None:
        assert OracleType("test_pass") == OracleType.TEST_PASS


class TestTaskSetup:
    def test_defaults(self) -> None:
        setup = TaskSetup()
        assert setup.repo_url is None
        assert setup.base_ref is None
        assert setup.pre_commands == []
        assert setup.working_dir is None
        assert setup.env_vars == {}

    def test_frozen(self) -> None:
        setup = TaskSetup(repo_url="https://github.com/example/repo")
        with pytest.raises(Exception):
            setup.repo_url = "other"  # type: ignore[misc]

    def test_with_all_fields(self) -> None:
        setup = TaskSetup(
            repo_url="https://github.com/example/repo",
            base_ref="main",
            pre_commands=["npm install", "npm build"],
            working_dir="/tmp/work",
            env_vars={"NODE_ENV": "test"},
        )
        assert setup.repo_url == "https://github.com/example/repo"
        assert setup.base_ref == "main"
        assert len(setup.pre_commands) == 2
        assert setup.env_vars["NODE_ENV"] == "test"

    def test_roundtrip(self) -> None:
        setup = TaskSetup(
            repo_url="https://example.com/repo.git",
            pre_commands=["pip install -e ."],
        )
        data = setup.model_dump(mode="json")
        loaded = TaskSetup.model_validate(data)
        assert loaded.repo_url == setup.repo_url
        assert loaded.pre_commands == setup.pre_commands


class TestTaskOracle:
    def test_test_pass_oracle(self) -> None:
        oracle = TaskOracle(
            type=OracleType.TEST_PASS,
            test_command="pytest -v",
            expected_exit_code=0,
        )
        assert oracle.type == OracleType.TEST_PASS
        assert oracle.test_command == "pytest -v"

    def test_file_diff_oracle(self) -> None:
        oracle = TaskOracle(
            type=OracleType.FILE_DIFF,
            expected_files={"main.py": "def hello()"},
        )
        assert oracle.expected_files is not None
        assert "main.py" in oracle.expected_files

    def test_custom_script_oracle(self) -> None:
        oracle = TaskOracle(
            type=OracleType.CUSTOM_SCRIPT,
            script_path="/scripts/check.sh",
            expected_exit_code=0,
        )
        assert oracle.script_path == "/scripts/check.sh"

    def test_frozen(self) -> None:
        oracle = TaskOracle(type=OracleType.TEST_PASS)
        with pytest.raises(Exception):
            oracle.type = OracleType.FILE_DIFF  # type: ignore[misc]

    def test_default_expected_exit_code(self) -> None:
        oracle = TaskOracle(type=OracleType.TEST_PASS)
        assert oracle.expected_exit_code == 0

    def test_roundtrip(self) -> None:
        oracle = TaskOracle(
            type=OracleType.FILE_DIFF,
            expected_files={"a.py": "content"},
        )
        data = oracle.model_dump(mode="json")
        loaded = TaskOracle.model_validate(data)
        assert loaded.type == oracle.type
        assert loaded.expected_files == oracle.expected_files


class TestTaskInstance:
    def test_minimal(self) -> None:
        instance = TaskInstance(
            instance_id="task-001",
            description="Fix the bug",
            prompt="Please fix the bug in main.py",
            oracle=TaskOracle(
                type=OracleType.TEST_PASS,
                test_command="pytest tests/",
            ),
        )
        assert instance.instance_id == "task-001"
        assert instance.timeout_seconds == 300
        assert instance.tags == []
        assert instance.metadata == {}

    def test_full_instance(self) -> None:
        instance = TaskInstance(
            instance_id="task-002",
            description="Add feature X",
            setup=TaskSetup(
                repo_url="https://github.com/ex/repo",
                base_ref="v1.0",
                pre_commands=["pip install -e ."],
                env_vars={"DEBUG": "1"},
            ),
            prompt="Implement feature X",
            oracle=TaskOracle(
                type=OracleType.TEST_PASS,
                test_command="pytest -v",
            ),
            timeout_seconds=600,
            tags=["feature", "python"],
            metadata={"difficulty": "medium"},
        )
        assert instance.setup.repo_url == "https://github.com/ex/repo"
        assert instance.timeout_seconds == 600
        assert "feature" in instance.tags
        assert instance.metadata["difficulty"] == "medium"

    def test_frozen(self) -> None:
        instance = TaskInstance(
            instance_id="t1",
            description="d",
            prompt="p",
            oracle=TaskOracle(type=OracleType.TEST_PASS),
        )
        with pytest.raises(Exception):
            instance.instance_id = "t2"  # type: ignore[misc]

    def test_roundtrip(self) -> None:
        instance = TaskInstance(
            instance_id="task-rt",
            description="Roundtrip test",
            prompt="Do the thing",
            oracle=TaskOracle(
                type=OracleType.CUSTOM_SCRIPT,
                script_path="check.sh",
            ),
            tags=["test"],
        )
        data = instance.model_dump(mode="json")
        loaded = TaskInstance.model_validate(data)
        assert loaded.instance_id == instance.instance_id
        assert loaded.oracle.type == OracleType.CUSTOM_SCRIPT


class TestEvalResult:
    def test_success_result(self) -> None:
        result = EvalResult(
            instance_id="task-001",
            success=True,
            score=1.0,
            duration_seconds=5.2,
            oracle_output="All tests passed",
        )
        assert result.success is True
        assert result.score == 1.0

    def test_failure_result(self) -> None:
        result = EvalResult(
            instance_id="task-001",
            success=False,
            score=0.0,
            error_message="Setup failed",
            duration_seconds=1.0,
        )
        assert result.success is False
        assert result.error_message == "Setup failed"

    def test_with_trajectory(self) -> None:
        traj = TaskTrajectory(
            task_id="task-001",
            started_at=1000.0,
            ended_at=1005.0,
            success=True,
            total_turns=3,
        )
        result = EvalResult(
            instance_id="task-001",
            success=True,
            score=1.0,
            trajectory=traj,
            duration_seconds=5.0,
        )
        assert result.trajectory is not None
        assert result.trajectory.total_turns == 3

    def test_frozen(self) -> None:
        result = EvalResult(instance_id="t1", success=True)
        with pytest.raises(Exception):
            result.success = False  # type: ignore[misc]

    def test_defaults(self) -> None:
        result = EvalResult(instance_id="t1", success=False)
        assert result.score is None
        assert result.error_message is None
        assert result.trajectory is None
        assert result.duration_seconds == 0.0
        assert result.oracle_output is None
        assert result.metadata == {}

    def test_roundtrip(self) -> None:
        result = EvalResult(
            instance_id="task-rt",
            success=True,
            score=0.8,
            oracle_output="mostly correct",
            metadata={"variant": "A"},
        )
        data = result.model_dump(mode="json")
        loaded = EvalResult.model_validate(data)
        assert loaded.instance_id == result.instance_id
        assert loaded.score == result.score

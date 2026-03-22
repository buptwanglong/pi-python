"""Tests for oracle implementations."""

import asyncio
import os
import stat
import pytest

from basket_eval.oracles import (
    evaluate_oracle,
    run_custom_script_oracle,
    run_file_diff_oracle,
    run_test_pass_oracle,
)
from basket_eval.schema import OracleType, TaskInstance, TaskOracle, TaskSetup


def _make_instance(
    oracle: TaskOracle,
    timeout: int = 30,
    instance_id: str = "test-oracle",
) -> TaskInstance:
    """Helper to build a TaskInstance with the given oracle."""
    return TaskInstance(
        instance_id=instance_id,
        description="Oracle test",
        prompt="Do something",
        oracle=oracle,
        timeout_seconds=timeout,
    )


class TestRunTestPassOracle:
    @pytest.mark.asyncio
    async def test_passing_command(self, tmp_path: object) -> None:
        instance = _make_instance(
            TaskOracle(type=OracleType.TEST_PASS, test_command="echo hello")
        )
        passed, output = await run_test_pass_oracle(instance, str(tmp_path))
        assert passed is True
        assert "hello" in output

    @pytest.mark.asyncio
    async def test_failing_command(self, tmp_path: object) -> None:
        instance = _make_instance(
            TaskOracle(type=OracleType.TEST_PASS, test_command="exit 1")
        )
        passed, output = await run_test_pass_oracle(instance, str(tmp_path))
        assert passed is False

    @pytest.mark.asyncio
    async def test_custom_exit_code(self, tmp_path: object) -> None:
        instance = _make_instance(
            TaskOracle(
                type=OracleType.TEST_PASS,
                test_command="exit 42",
                expected_exit_code=42,
            )
        )
        passed, output = await run_test_pass_oracle(instance, str(tmp_path))
        assert passed is True

    @pytest.mark.asyncio
    async def test_no_test_command(self, tmp_path: object) -> None:
        instance = _make_instance(
            TaskOracle(type=OracleType.TEST_PASS, test_command=None)
        )
        passed, output = await run_test_pass_oracle(instance, str(tmp_path))
        assert passed is False
        assert "No test_command" in output

    @pytest.mark.asyncio
    async def test_timeout(self, tmp_path: object) -> None:
        instance = _make_instance(
            TaskOracle(type=OracleType.TEST_PASS, test_command="sleep 60"),
            timeout=1,
        )
        passed, output = await run_test_pass_oracle(instance, str(tmp_path))
        assert passed is False
        assert "timed out" in output


class TestRunFileDiffOracle:
    @pytest.mark.asyncio
    async def test_matching_files(self, tmp_path: object) -> None:
        from pathlib import Path

        work = Path(str(tmp_path))
        (work / "main.py").write_text("def hello():\n    return 'world'\n")
        instance = _make_instance(
            TaskOracle(
                type=OracleType.FILE_DIFF,
                expected_files={"main.py": "def hello()"},
            )
        )
        passed, output = await run_file_diff_oracle(instance, str(work))
        assert passed is True
        assert "match" in output.lower()

    @pytest.mark.asyncio
    async def test_missing_file(self, tmp_path: object) -> None:
        instance = _make_instance(
            TaskOracle(
                type=OracleType.FILE_DIFF,
                expected_files={"nonexistent.py": "content"},
            )
        )
        passed, output = await run_file_diff_oracle(instance, str(tmp_path))
        assert passed is False
        assert "not found" in output.lower()

    @pytest.mark.asyncio
    async def test_content_mismatch(self, tmp_path: object) -> None:
        from pathlib import Path

        work = Path(str(tmp_path))
        (work / "main.py").write_text("def goodbye():\n    pass\n")
        instance = _make_instance(
            TaskOracle(
                type=OracleType.FILE_DIFF,
                expected_files={"main.py": "def hello()"},
            )
        )
        passed, output = await run_file_diff_oracle(instance, str(work))
        assert passed is False
        assert "expected content not found" in output.lower()

    @pytest.mark.asyncio
    async def test_no_expected_files(self, tmp_path: object) -> None:
        instance = _make_instance(
            TaskOracle(type=OracleType.FILE_DIFF, expected_files=None)
        )
        passed, output = await run_file_diff_oracle(instance, str(tmp_path))
        assert passed is False
        assert "No expected_files" in output

    @pytest.mark.asyncio
    async def test_multiple_files(self, tmp_path: object) -> None:
        from pathlib import Path

        work = Path(str(tmp_path))
        (work / "a.py").write_text("alpha content")
        (work / "b.py").write_text("beta content")
        instance = _make_instance(
            TaskOracle(
                type=OracleType.FILE_DIFF,
                expected_files={"a.py": "alpha", "b.py": "beta"},
            )
        )
        passed, output = await run_file_diff_oracle(instance, str(work))
        assert passed is True


class TestRunCustomScriptOracle:
    @pytest.mark.asyncio
    async def test_passing_script(self, tmp_path: object) -> None:
        from pathlib import Path

        work = Path(str(tmp_path))
        script = work / "check.sh"
        script.write_text("#!/bin/bash\nexit 0\n")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)

        instance = _make_instance(
            TaskOracle(
                type=OracleType.CUSTOM_SCRIPT,
                script_path=str(script),
            )
        )
        passed, output = await run_custom_script_oracle(instance, str(work))
        assert passed is True

    @pytest.mark.asyncio
    async def test_failing_script(self, tmp_path: object) -> None:
        from pathlib import Path

        work = Path(str(tmp_path))
        script = work / "check.sh"
        script.write_text("#!/bin/bash\necho 'FAIL'\nexit 1\n")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)

        instance = _make_instance(
            TaskOracle(
                type=OracleType.CUSTOM_SCRIPT,
                script_path=str(script),
            )
        )
        passed, output = await run_custom_script_oracle(instance, str(work))
        assert passed is False
        assert "FAIL" in output

    @pytest.mark.asyncio
    async def test_no_script_path(self, tmp_path: object) -> None:
        instance = _make_instance(
            TaskOracle(type=OracleType.CUSTOM_SCRIPT, script_path=None)
        )
        passed, output = await run_custom_script_oracle(instance, str(tmp_path))
        assert passed is False
        assert "No script_path" in output

    @pytest.mark.asyncio
    async def test_missing_script(self, tmp_path: object) -> None:
        instance = _make_instance(
            TaskOracle(
                type=OracleType.CUSTOM_SCRIPT,
                script_path="/nonexistent/check.sh",
            )
        )
        passed, output = await run_custom_script_oracle(instance, str(tmp_path))
        assert passed is False
        assert "not found" in output.lower()

    @pytest.mark.asyncio
    async def test_relative_script_path(self, tmp_path: object) -> None:
        from pathlib import Path

        work = Path(str(tmp_path))
        script = work / "scripts" / "check.sh"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("#!/bin/bash\nexit 0\n")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)

        instance = _make_instance(
            TaskOracle(
                type=OracleType.CUSTOM_SCRIPT,
                script_path="scripts/check.sh",
            )
        )
        passed, output = await run_custom_script_oracle(instance, str(work))
        assert passed is True


class TestEvaluateOracle:
    @pytest.mark.asyncio
    async def test_test_pass_dispatch(self, tmp_path: object) -> None:
        instance = _make_instance(
            TaskOracle(type=OracleType.TEST_PASS, test_command="echo ok")
        )
        passed, score, output = await evaluate_oracle(instance, str(tmp_path))
        assert passed is True
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_file_diff_dispatch(self, tmp_path: object) -> None:
        from pathlib import Path

        work = Path(str(tmp_path))
        (work / "f.txt").write_text("expected")
        instance = _make_instance(
            TaskOracle(
                type=OracleType.FILE_DIFF,
                expected_files={"f.txt": "expected"},
            )
        )
        passed, score, output = await evaluate_oracle(instance, str(work))
        assert passed is True
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_llm_judge_not_implemented(self, tmp_path: object) -> None:
        instance = _make_instance(
            TaskOracle(
                type=OracleType.LLM_JUDGE,
                judge_rubric="Is the code correct?",
            )
        )
        passed, score, output = await evaluate_oracle(instance, str(tmp_path))
        assert passed is False
        assert score is None
        assert "not yet implemented" in output.lower()

    @pytest.mark.asyncio
    async def test_failure_score_zero(self, tmp_path: object) -> None:
        instance = _make_instance(
            TaskOracle(type=OracleType.TEST_PASS, test_command="exit 1")
        )
        passed, score, output = await evaluate_oracle(instance, str(tmp_path))
        assert passed is False
        assert score == 0.0

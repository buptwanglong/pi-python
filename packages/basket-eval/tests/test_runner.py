"""Tests for the headless evaluation runner."""

import asyncio
import os
import stat
import pytest
from pathlib import Path

from basket_eval.runner import EvalRunner
from basket_eval.schema import (
    EvalResult,
    OracleType,
    TaskInstance,
    TaskOracle,
    TaskSetup,
)


def _make_instance(
    oracle: TaskOracle,
    setup: TaskSetup | None = None,
    timeout: int = 30,
    instance_id: str = "test-runner",
) -> TaskInstance:
    return TaskInstance(
        instance_id=instance_id,
        description="Runner test",
        prompt="Do something",
        oracle=oracle,
        setup=setup or TaskSetup(),
        timeout_seconds=timeout,
    )


class TestEvalRunnerSetup:
    @pytest.mark.asyncio
    async def test_pre_commands_executed(self, tmp_path: Path) -> None:
        marker = tmp_path / "setup_marker.txt"
        instance = _make_instance(
            oracle=TaskOracle(type=OracleType.TEST_PASS, test_command="echo ok"),
            setup=TaskSetup(
                pre_commands=[f"echo 'setup_done' > {marker}"],
                working_dir=str(tmp_path),
            ),
        )
        runner = EvalRunner()
        await runner.setup_environment(instance, str(tmp_path))
        assert marker.exists()
        assert "setup_done" in marker.read_text()

    @pytest.mark.asyncio
    async def test_env_vars_available(self, tmp_path: Path) -> None:
        marker = tmp_path / "env_marker.txt"
        instance = _make_instance(
            oracle=TaskOracle(type=OracleType.TEST_PASS, test_command="echo ok"),
            setup=TaskSetup(
                pre_commands=[f'echo "$MY_TEST_VAR" > {marker}'],
                env_vars={"MY_TEST_VAR": "hello_eval"},
                working_dir=str(tmp_path),
            ),
        )
        runner = EvalRunner()
        await runner.setup_environment(instance, str(tmp_path))
        assert marker.exists()
        assert "hello_eval" in marker.read_text()

    @pytest.mark.asyncio
    async def test_pre_command_failure_raises(self, tmp_path: Path) -> None:
        instance = _make_instance(
            oracle=TaskOracle(type=OracleType.TEST_PASS, test_command="echo ok"),
            setup=TaskSetup(
                pre_commands=["exit 1"],
                working_dir=str(tmp_path),
            ),
        )
        runner = EvalRunner()
        with pytest.raises(RuntimeError, match="Pre-command failed"):
            await runner.setup_environment(instance, str(tmp_path))


class TestEvalRunnerInstance:
    @pytest.mark.asyncio
    async def test_run_passing_instance(self, tmp_path: Path) -> None:
        instance = _make_instance(
            oracle=TaskOracle(type=OracleType.TEST_PASS, test_command="echo pass"),
            setup=TaskSetup(working_dir=str(tmp_path)),
        )
        runner = EvalRunner()
        result = await runner.run_instance(instance)
        assert result.instance_id == "test-runner"
        assert result.success is True
        assert result.score == 1.0
        assert result.duration_seconds > 0

    @pytest.mark.asyncio
    async def test_run_failing_instance(self, tmp_path: Path) -> None:
        instance = _make_instance(
            oracle=TaskOracle(type=OracleType.TEST_PASS, test_command="exit 1"),
            setup=TaskSetup(working_dir=str(tmp_path)),
        )
        runner = EvalRunner()
        result = await runner.run_instance(instance)
        assert result.success is False
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_run_instance_setup_failure(self, tmp_path: Path) -> None:
        instance = _make_instance(
            oracle=TaskOracle(type=OracleType.TEST_PASS, test_command="echo ok"),
            setup=TaskSetup(
                pre_commands=["exit 1"],
                working_dir=str(tmp_path),
            ),
        )
        runner = EvalRunner()
        result = await runner.run_instance(instance)
        assert result.success is False
        assert result.error_message is not None
        assert "Setup failed" in result.error_message

    @pytest.mark.asyncio
    async def test_run_instance_with_temp_dir(self) -> None:
        """When no working_dir set, uses temp directory."""
        instance = _make_instance(
            oracle=TaskOracle(type=OracleType.TEST_PASS, test_command="echo ok"),
        )
        runner = EvalRunner()
        result = await runner.run_instance(instance)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_run_instance_file_diff(self, tmp_path: Path) -> None:
        (tmp_path / "output.txt").write_text("expected output here")
        instance = _make_instance(
            oracle=TaskOracle(
                type=OracleType.FILE_DIFF,
                expected_files={"output.txt": "expected output"},
            ),
            setup=TaskSetup(working_dir=str(tmp_path)),
        )
        runner = EvalRunner()
        result = await runner.run_instance(instance)
        assert result.success is True


class TestEvalRunnerBatch:
    @pytest.mark.asyncio
    async def test_batch_sequential(self, tmp_path: Path) -> None:
        instances = [
            _make_instance(
                oracle=TaskOracle(
                    type=OracleType.TEST_PASS,
                    test_command=f"echo task_{i}",
                ),
                setup=TaskSetup(working_dir=str(tmp_path)),
                instance_id=f"task-{i}",
            )
            for i in range(3)
        ]
        runner = EvalRunner()
        results = await runner.run_batch(instances, concurrency=1)
        assert len(results) == 3
        assert all(r.success for r in results)
        assert {r.instance_id for r in results} == {"task-0", "task-1", "task-2"}

    @pytest.mark.asyncio
    async def test_batch_parallel(self, tmp_path: Path) -> None:
        instances = [
            _make_instance(
                oracle=TaskOracle(
                    type=OracleType.TEST_PASS,
                    test_command="echo ok",
                ),
                setup=TaskSetup(working_dir=str(tmp_path)),
                instance_id=f"par-{i}",
            )
            for i in range(5)
        ]
        runner = EvalRunner()
        results = await runner.run_batch(instances, concurrency=3)
        assert len(results) == 5
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_batch_empty(self) -> None:
        runner = EvalRunner()
        results = await runner.run_batch([], concurrency=1)
        assert results == []

    @pytest.mark.asyncio
    async def test_batch_mixed_results(self, tmp_path: Path) -> None:
        instances = [
            _make_instance(
                oracle=TaskOracle(
                    type=OracleType.TEST_PASS,
                    test_command="echo pass",
                ),
                setup=TaskSetup(working_dir=str(tmp_path)),
                instance_id="pass-task",
            ),
            _make_instance(
                oracle=TaskOracle(
                    type=OracleType.TEST_PASS,
                    test_command="exit 1",
                ),
                setup=TaskSetup(working_dir=str(tmp_path)),
                instance_id="fail-task",
            ),
        ]
        runner = EvalRunner()
        results = await runner.run_batch(instances, concurrency=2)
        assert len(results) == 2
        success_ids = {r.instance_id for r in results if r.success}
        failure_ids = {r.instance_id for r in results if not r.success}
        assert success_ids == {"pass-task"}
        assert failure_ids == {"fail-task"}

    @pytest.mark.asyncio
    async def test_batch_concurrency_clamp(self, tmp_path: Path) -> None:
        """Concurrency < 1 should be clamped to 1."""
        instances = [
            _make_instance(
                oracle=TaskOracle(
                    type=OracleType.TEST_PASS,
                    test_command="echo ok",
                ),
                setup=TaskSetup(working_dir=str(tmp_path)),
                instance_id="clamp-task",
            ),
        ]
        runner = EvalRunner()
        results = await runner.run_batch(instances, concurrency=0)
        assert len(results) == 1
        assert results[0].success is True

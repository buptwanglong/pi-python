"""Headless evaluation runner."""

import asyncio
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from basket_trajectory.schema import TaskTrajectory

from .oracles import evaluate_oracle
from .schema import EvalResult, TaskInstance

logger = logging.getLogger(__name__)


class EvalRunner:
    """Runs task instances headlessly and evaluates results.

    Handles environment setup (clone repo, checkout ref, run pre-commands),
    executes the oracle, and collects results. Does NOT run the agent itself -
    the caller is responsible for agent execution and passing the working
    directory where the agent produced its output.
    """

    def __init__(self, settings: Optional[Dict[str, Any]] = None) -> None:
        self.settings = settings or {}

    async def setup_environment(
        self, instance: TaskInstance, work_dir: str
    ) -> None:
        """Setup the environment for a task instance.

        Steps:
        1. Clone repo if specified
        2. Checkout base_ref if specified
        3. Run pre_commands in sequence
        4. Set env vars
        """
        setup = instance.setup
        env = {**os.environ, **setup.env_vars}

        if setup.repo_url:
            logger.info("Cloning %s into %s", setup.repo_url, work_dir)
            proc = await asyncio.create_subprocess_exec(
                "git", "clone", setup.repo_url, ".",
                cwd=work_dir,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=instance.timeout_seconds
            )
            if proc.returncode != 0:
                output = stdout.decode("utf-8", errors="replace") if stdout else ""
                raise RuntimeError(f"git clone failed (rc={proc.returncode}): {output}")

        if setup.base_ref:
            logger.info("Checking out %s", setup.base_ref)
            proc = await asyncio.create_subprocess_exec(
                "git", "checkout", setup.base_ref,
                cwd=work_dir,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=instance.timeout_seconds
            )
            if proc.returncode != 0:
                output = stdout.decode("utf-8", errors="replace") if stdout else ""
                raise RuntimeError(
                    f"git checkout failed (rc={proc.returncode}): {output}"
                )

        for cmd in setup.pre_commands:
            logger.info("Running pre-command: %s", cmd)
            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=work_dir,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=instance.timeout_seconds
            )
            if proc.returncode != 0:
                output = stdout.decode("utf-8", errors="replace") if stdout else ""
                raise RuntimeError(
                    f"Pre-command failed (rc={proc.returncode}): {output}"
                )

    async def run_instance(self, instance: TaskInstance) -> EvalResult:
        """Run a single task instance: setup environment, then evaluate.

        Creates a temp directory, sets up the environment, runs oracle
        evaluation, and returns the result.
        """
        start_time = time.time()

        with tempfile.TemporaryDirectory(prefix="basket_eval_") as tmp_dir:
            work_dir = instance.setup.working_dir or tmp_dir

            # Ensure working dir exists
            Path(work_dir).mkdir(parents=True, exist_ok=True)

            try:
                await self.setup_environment(instance, work_dir)
            except Exception as e:
                duration = time.time() - start_time
                logger.error("Setup failed for %s: %s", instance.instance_id, e)
                return EvalResult(
                    instance_id=instance.instance_id,
                    success=False,
                    score=0.0,
                    error_message=f"Setup failed: {e}",
                    duration_seconds=duration,
                )

            try:
                passed, score, output = await evaluate_oracle(instance, work_dir)
            except Exception as e:
                duration = time.time() - start_time
                logger.error("Oracle failed for %s: %s", instance.instance_id, e)
                return EvalResult(
                    instance_id=instance.instance_id,
                    success=False,
                    score=0.0,
                    error_message=f"Oracle failed: {e}",
                    duration_seconds=duration,
                )

            duration = time.time() - start_time
            return EvalResult(
                instance_id=instance.instance_id,
                success=passed,
                score=score,
                oracle_output=output,
                duration_seconds=duration,
            )

    async def run_batch(
        self, instances: List[TaskInstance], concurrency: int = 1
    ) -> List[EvalResult]:
        """Run multiple task instances, optionally in parallel.

        Args:
            instances: List of task instances to evaluate.
            concurrency: Max number of concurrent evaluations. Default 1 (sequential).

        Returns:
            List of EvalResult in the same order as input instances.
        """
        if concurrency < 1:
            concurrency = 1

        semaphore = asyncio.Semaphore(concurrency)
        results: List[EvalResult] = []

        async def _run_with_semaphore(inst: TaskInstance) -> EvalResult:
            async with semaphore:
                return await self.run_instance(inst)

        tasks = [_run_with_semaphore(inst) for inst in instances]
        results = await asyncio.gather(*tasks)
        return list(results)

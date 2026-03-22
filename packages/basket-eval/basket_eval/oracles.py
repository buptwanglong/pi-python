"""Oracle implementations for task evaluation."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from .schema import OracleType, TaskInstance

logger = logging.getLogger(__name__)


async def run_test_pass_oracle(
    instance: TaskInstance, working_dir: str
) -> tuple[bool, str]:
    """Run a test command and check exit code.

    Returns (success, output_text).
    """
    oracle = instance.oracle
    if not oracle.test_command:
        return False, "No test_command specified in oracle"

    try:
        proc = await asyncio.create_subprocess_shell(
            oracle.test_command,
            cwd=working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout_bytes, _ = await asyncio.wait_for(
            proc.communicate(), timeout=instance.timeout_seconds
        )
        output = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        passed = proc.returncode == oracle.expected_exit_code
        return passed, output
    except asyncio.TimeoutError:
        return False, f"Test command timed out after {instance.timeout_seconds}s"
    except Exception as e:
        return False, f"Test command failed: {e}"


async def run_file_diff_oracle(
    instance: TaskInstance, working_dir: str
) -> tuple[bool, str]:
    """Compare expected files against actual files.

    Checks that each expected file exists and its content contains
    the expected substring.

    Returns (success, output_text).
    """
    oracle = instance.oracle
    if not oracle.expected_files:
        return False, "No expected_files specified in oracle"

    mismatches: list[str] = []
    work_path = Path(working_dir)

    for file_path, expected_content in oracle.expected_files.items():
        full_path = work_path / file_path
        if not full_path.exists():
            mismatches.append(f"File not found: {file_path}")
            continue

        try:
            actual_content = full_path.read_text(encoding="utf-8")
        except Exception as e:
            mismatches.append(f"Cannot read {file_path}: {e}")
            continue

        if expected_content not in actual_content:
            mismatches.append(
                f"File {file_path}: expected content not found. "
                f"Expected substring: {expected_content!r:.200}"
            )

    if mismatches:
        return False, "\n".join(mismatches)
    return True, "All expected files match"


async def run_custom_script_oracle(
    instance: TaskInstance, working_dir: str
) -> tuple[bool, str]:
    """Run a custom script and check exit code.

    Returns (success, output_text).
    """
    oracle = instance.oracle
    if not oracle.script_path:
        return False, "No script_path specified in oracle"

    script = Path(oracle.script_path)
    if not script.is_absolute():
        script = Path(working_dir) / script

    if not script.exists():
        return False, f"Script not found: {script}"

    try:
        proc = await asyncio.create_subprocess_exec(
            str(script),
            cwd=working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout_bytes, _ = await asyncio.wait_for(
            proc.communicate(), timeout=instance.timeout_seconds
        )
        output = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        passed = proc.returncode == oracle.expected_exit_code
        return passed, output
    except asyncio.TimeoutError:
        return False, f"Custom script timed out after {instance.timeout_seconds}s"
    except Exception as e:
        return False, f"Custom script failed: {e}"


async def evaluate_oracle(
    instance: TaskInstance, working_dir: str
) -> tuple[bool, Optional[float], str]:
    """Evaluate using the appropriate oracle type.

    Returns (success, score, output_text).
    Score is 1.0 for success, 0.0 for failure (simple binary).
    """
    oracle_type = instance.oracle.type

    if oracle_type == OracleType.TEST_PASS:
        passed, output = await run_test_pass_oracle(instance, working_dir)
    elif oracle_type == OracleType.FILE_DIFF:
        passed, output = await run_file_diff_oracle(instance, working_dir)
    elif oracle_type == OracleType.CUSTOM_SCRIPT:
        passed, output = await run_custom_script_oracle(instance, working_dir)
    elif oracle_type == OracleType.LLM_JUDGE:
        # LLM judge requires external integration; return not-implemented
        return False, None, "LLM_JUDGE oracle not yet implemented"
    else:
        return False, None, f"Unknown oracle type: {oracle_type}"

    score = 1.0 if passed else 0.0
    return passed, score, output

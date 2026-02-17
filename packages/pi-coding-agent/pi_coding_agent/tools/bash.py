"""
Bash tool - Execute shell commands.

Runs bash commands with timeout and output capture.
"""

import asyncio
import subprocess
from typing import Optional

from pydantic import BaseModel, Field


class BashParams(BaseModel):
    """Parameters for the Bash tool."""

    command: str = Field(..., description="Shell command to execute")
    timeout: int = Field(120, description="Timeout in seconds (default: 120)")


class BashResult(BaseModel):
    """Result from executing a bash command."""

    stdout: str
    stderr: str
    exit_code: int
    command: str
    timeout: bool = False


async def execute_bash(command: str, timeout: int = 120) -> BashResult:
    """
    Execute a bash command.

    Args:
        command: Shell command to execute
        timeout: Timeout in seconds

    Returns:
        BashResult with stdout, stderr, and exit code
    """
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode or 0
            timed_out = False
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            stdout = ""
            stderr = f"Command timed out after {timeout} seconds"
            exit_code = -1
            timed_out = True

    except Exception as e:
        stdout = ""
        stderr = f"Failed to execute command: {e}"
        exit_code = -1
        timed_out = False

    return BashResult(
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        command=command,
        timeout=timed_out,
    )


# Tool definition for pi-agent
BASH_TOOL = {
    "name": "bash",
    "description": "Execute shell commands. Returns stdout, stderr, and exit code. Use for git, npm, pytest, etc.",
    "parameters": BashParams,
    "execute_fn": execute_bash,
}


__all__ = ["BashParams", "BashResult", "execute_bash", "BASH_TOOL"]

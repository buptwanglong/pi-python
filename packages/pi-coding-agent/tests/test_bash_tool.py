"""
Tests for the Bash tool.
"""

import pytest
import sys

from pi_coding_agent.tools.bash import execute_bash, BashParams, BashResult


@pytest.mark.asyncio
async def test_bash_simple_command():
    """Test executing a simple command."""
    result = await execute_bash("echo 'Hello, World!'")

    assert result.exit_code == 0
    assert "Hello, World!" in result.stdout
    assert result.stderr == ""
    assert not result.timeout


@pytest.mark.asyncio
async def test_bash_with_exit_code():
    """Test command with non-zero exit code."""
    result = await execute_bash("exit 42")

    assert result.exit_code == 42


@pytest.mark.asyncio
async def test_bash_stderr_output():
    """Test command that writes to stderr."""
    result = await execute_bash("echo 'error message' >&2")

    assert result.exit_code == 0
    assert "error message" in result.stderr


@pytest.mark.asyncio
async def test_bash_multiline_output():
    """Test command with multiline output."""
    result = await execute_bash("printf 'Line 1\\nLine 2\\nLine 3'")

    assert result.exit_code == 0
    assert "Line 1" in result.stdout
    assert "Line 2" in result.stdout
    assert "Line 3" in result.stdout


@pytest.mark.asyncio
async def test_bash_with_pipes():
    """Test command with pipes."""
    result = await execute_bash("echo 'hello world' | tr 'a-z' 'A-Z'")

    assert result.exit_code == 0
    assert "HELLO WORLD" in result.stdout


@pytest.mark.asyncio
async def test_bash_working_directory():
    """Test that bash runs in current directory."""
    result = await execute_bash("pwd")

    assert result.exit_code == 0
    assert len(result.stdout.strip()) > 0


@pytest.mark.asyncio
@pytest.mark.slow
async def test_bash_timeout():
    """Test command timeout."""
    # Command that sleeps for 5 seconds, but timeout after 1 second
    result = await execute_bash("sleep 5", timeout=1)

    assert result.exit_code == -1
    assert result.timeout
    assert "timed out" in result.stderr


@pytest.mark.asyncio
async def test_bash_environment_variables():
    """Test accessing environment variables."""
    result = await execute_bash("echo $HOME")

    assert result.exit_code == 0
    assert len(result.stdout.strip()) > 0


@pytest.mark.asyncio
async def test_bash_command_not_found():
    """Test running a nonexistent command."""
    result = await execute_bash("nonexistent_command_12345")

    assert result.exit_code != 0
    # Depending on shell, error might be in stdout or stderr
    assert ("not found" in result.stderr.lower() or
            "not found" in result.stdout.lower() or
            result.exit_code == 127)


@pytest.mark.asyncio
async def test_bash_python_command():
    """Test running python command."""
    result = await execute_bash("python3 --version")

    assert result.exit_code == 0
    assert "Python" in result.stdout or "Python" in result.stderr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

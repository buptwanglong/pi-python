"""
Tests for structured tool retry with exponential backoff.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from basket_agent.retry import (
    DEFAULT_RETRYABLE_PATTERNS,
    RetryPolicy,
    execute_with_retry,
    is_retryable_error,
)
from basket_agent.types import AgentTool, ToolExecutor
from basket_ai.types import ToolCall


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool_call(name: str = "test_tool", **kwargs) -> ToolCall:
    return ToolCall(
        type="toolCall",
        id="call_001",
        name=name,
        arguments=kwargs,
    )


def _make_agent_tool(
    name: str = "test_tool",
    executor_fn=None,
) -> AgentTool:
    if executor_fn is None:
        async def _noop():
            return "ok"
        executor_fn = _noop
    executor = ToolExecutor(name, f"{name} tool", executor_fn)
    return AgentTool(name=name, description=f"{name} tool", parameters={}, executor=executor)


# ---------------------------------------------------------------------------
# is_retryable_error
# ---------------------------------------------------------------------------

class TestIsRetryableError:
    """Tests for the is_retryable_error pure function."""

    def test_matches_timeout_case_insensitive(self):
        policy = RetryPolicy()
        assert is_retryable_error("Request Timeout after 30s", policy) is True

    def test_matches_connection_error(self):
        policy = RetryPolicy()
        assert is_retryable_error("ConnectionRefusedError: port 8080", policy) is True

    def test_matches_rate_limit(self):
        policy = RetryPolicy()
        assert is_retryable_error("rate_limit exceeded, retry after 1s", policy) is True

    def test_matches_http_429(self):
        policy = RetryPolicy()
        assert is_retryable_error("HTTP 429 Too Many Requests", policy) is True

    def test_matches_http_503(self):
        policy = RetryPolicy()
        assert is_retryable_error("503 Service Unavailable", policy) is True

    def test_matches_http_502(self):
        policy = RetryPolicy()
        assert is_retryable_error("502 Bad Gateway", policy) is True

    def test_no_match_for_value_error(self):
        policy = RetryPolicy()
        assert is_retryable_error("ValueError: invalid argument", policy) is False

    def test_no_match_for_permission_denied(self):
        policy = RetryPolicy()
        assert is_retryable_error("PermissionError: access denied", policy) is False

    def test_custom_patterns(self):
        policy = RetryPolicy(retryable_patterns=frozenset({"custom_error"}))
        assert is_retryable_error("custom_error happened", policy) is True
        assert is_retryable_error("timeout error", policy) is False

    def test_empty_patterns_never_matches(self):
        policy = RetryPolicy(retryable_patterns=frozenset())
        assert is_retryable_error("timeout", policy) is False

    def test_all_default_patterns(self):
        """Each default pattern should match a string containing it."""
        policy = RetryPolicy()
        for pattern in DEFAULT_RETRYABLE_PATTERNS:
            assert is_retryable_error(f"error: {pattern} occurred", policy) is True


# ---------------------------------------------------------------------------
# RetryPolicy validation
# ---------------------------------------------------------------------------

class TestRetryPolicy:
    """Tests for RetryPolicy model validation."""

    def test_defaults(self):
        p = RetryPolicy()
        assert p.max_retries == 2
        assert p.backoff_base == 1.0
        assert p.retryable_patterns == DEFAULT_RETRYABLE_PATTERNS

    def test_frozen(self):
        p = RetryPolicy()
        with pytest.raises(Exception):
            p.max_retries = 5

    def test_max_retries_bounds(self):
        RetryPolicy(max_retries=0)
        RetryPolicy(max_retries=5)
        with pytest.raises(Exception):
            RetryPolicy(max_retries=-1)
        with pytest.raises(Exception):
            RetryPolicy(max_retries=6)

    def test_backoff_base_positive(self):
        with pytest.raises(Exception):
            RetryPolicy(backoff_base=0)
        with pytest.raises(Exception):
            RetryPolicy(backoff_base=-1.0)


# ---------------------------------------------------------------------------
# execute_with_retry
# ---------------------------------------------------------------------------

class TestExecuteWithRetry:
    """Tests for the execute_with_retry function."""

    @pytest.mark.asyncio
    async def test_no_retry_on_success(self):
        """Tool succeeds on first try — no retries, no delay."""
        call_count = 0

        async def succeed():
            nonlocal call_count
            call_count += 1
            return "result"

        tool = _make_agent_tool(executor_fn=succeed)
        tc = _make_tool_call()

        result, error = await execute_with_retry(tc, tool)

        assert result == "result"
        assert error is None
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_error(self):
        """Non-transient error should not be retried."""
        call_count = 0

        async def fail_permanently():
            nonlocal call_count
            call_count += 1
            raise ValueError("bad input")

        tool = _make_agent_tool(executor_fn=fail_permanently)
        tc = _make_tool_call()

        result, error = await execute_with_retry(tc, tool)

        assert result is None
        assert error == "bad input"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_timeout_error(self):
        """TimeoutError should trigger retries."""
        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("Request timed out")
            return "recovered"

        tool = _make_agent_tool(executor_fn=fail_then_succeed)
        tc = _make_tool_call()
        policy = RetryPolicy(backoff_base=0.01)  # fast for tests

        result, error = await execute_with_retry(tc, tool, policy=policy)

        assert result == "recovered"
        assert error is None
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self):
        """ConnectionError should trigger retries."""
        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection refused")
            return "connected"

        tool = _make_agent_tool(executor_fn=fail_then_succeed)
        tc = _make_tool_call()
        policy = RetryPolicy(backoff_base=0.01)

        result, error = await execute_with_retry(tc, tool, policy=policy)

        assert result == "connected"
        assert error is None
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self):
        """Rate limit errors should trigger retries."""
        call_count = 0

        async def rate_limited_then_ok():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("rate_limit exceeded")
            return "success"

        tool = _make_agent_tool(executor_fn=rate_limited_then_ok)
        tc = _make_tool_call()
        policy = RetryPolicy(backoff_base=0.01)

        result, error = await execute_with_retry(tc, tool, policy=policy)

        assert result == "success"
        assert error is None
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """All retries exhausted should return the last error."""
        call_count = 0

        async def always_timeout():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("timed out")

        tool = _make_agent_tool(executor_fn=always_timeout)
        tc = _make_tool_call()
        policy = RetryPolicy(max_retries=2, backoff_base=0.01)

        result, error = await execute_with_retry(tc, tool, policy=policy)

        assert result is None
        assert "timed out" in error
        # 1 initial + 2 retries = 3
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_with_backoff_delay(self):
        """Verify exponential backoff delays are applied."""
        sleep_calls: list[float] = []

        async def always_timeout():
            raise TimeoutError("timeout")

        tool = _make_agent_tool(executor_fn=always_timeout)
        tc = _make_tool_call()
        policy = RetryPolicy(max_retries=3, backoff_base=1.0)

        with patch("basket_agent.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = lambda d: sleep_calls.append(d)

            await execute_with_retry(tc, tool, policy=policy)

        # Delays: 1.0 * 2^0 = 1.0, 1.0 * 2^1 = 2.0, 1.0 * 2^2 = 4.0
        assert sleep_calls == [1.0, 2.0, 4.0]

    @pytest.mark.asyncio
    async def test_custom_retry_policy(self):
        """Custom policy with different max_retries and backoff."""
        call_count = 0
        sleep_calls: list[float] = []

        async def always_timeout():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("timeout")

        tool = _make_agent_tool(executor_fn=always_timeout)
        tc = _make_tool_call()
        policy = RetryPolicy(max_retries=1, backoff_base=0.5)

        with patch("basket_agent.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = lambda d: sleep_calls.append(d)

            result, error = await execute_with_retry(tc, tool, policy=policy)

        assert result is None
        assert "timeout" in error
        assert call_count == 2  # 1 initial + 1 retry
        assert sleep_calls == [0.5]  # 0.5 * 2^0

    @pytest.mark.asyncio
    async def test_on_retry_callback_called(self):
        """on_retry callback should receive correct arguments."""
        callback_calls: list[tuple] = []

        def on_retry(name: str, attempt: int, err: str, max_retries: int):
            callback_calls.append((name, attempt, err, max_retries))

        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("ConnectionResetError")
            return "ok"

        tool = _make_agent_tool(executor_fn=fail_then_succeed)
        tc = _make_tool_call(name="test_tool")
        policy = RetryPolicy(max_retries=3, backoff_base=0.01)

        result, error = await execute_with_retry(
            tc, tool, policy=policy, on_retry=on_retry
        )

        assert result == "ok"
        assert error is None
        assert len(callback_calls) == 2
        assert callback_calls[0] == ("test_tool", 1, "ConnectionResetError", 3)
        assert callback_calls[1] == ("test_tool", 2, "ConnectionResetError", 3)

    @pytest.mark.asyncio
    async def test_on_retry_async_callback(self):
        """Async on_retry callback should also work."""
        callback_calls: list[tuple] = []

        async def on_retry(name: str, attempt: int, err: str, max_retries: int):
            callback_calls.append((name, attempt, err, max_retries))

        call_count = 0

        async def fail_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("timed out")
            return "done"

        tool = _make_agent_tool(executor_fn=fail_once)
        tc = _make_tool_call()
        policy = RetryPolicy(backoff_base=0.01)

        result, error = await execute_with_retry(
            tc, tool, policy=policy, on_retry=on_retry
        )

        assert result == "done"
        assert len(callback_calls) == 1

    @pytest.mark.asyncio
    async def test_on_retry_callback_error_does_not_break_retry(self):
        """A failing callback should not prevent the retry."""
        def bad_callback(name, attempt, err, max_retries):
            raise RuntimeError("callback bug")

        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("timeout")
            return "recovered"

        tool = _make_agent_tool(executor_fn=fail_then_succeed)
        tc = _make_tool_call()
        policy = RetryPolicy(backoff_base=0.01)

        result, error = await execute_with_retry(
            tc, tool, policy=policy, on_retry=bad_callback
        )

        assert result == "recovered"
        assert error is None
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_no_executor_returns_error(self):
        """Tool with no executor should return error immediately."""
        tool = AgentTool(
            name="no_exec",
            description="no executor",
            parameters={},
            executor=None,
        )
        tc = _make_tool_call(name="no_exec")

        result, error = await execute_with_retry(tc, tool)

        assert result is None
        assert "No executor found" in error

    @pytest.mark.asyncio
    async def test_zero_retries_no_retry(self):
        """With max_retries=0, should not retry even on transient error."""
        call_count = 0

        async def always_timeout():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("timeout")

        tool = _make_agent_tool(executor_fn=always_timeout)
        tc = _make_tool_call()
        policy = RetryPolicy(max_retries=0)

        result, error = await execute_with_retry(tc, tool, policy=policy)

        assert result is None
        assert "timeout" in error
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_default_policy_when_none(self):
        """Passing policy=None should use default RetryPolicy."""
        call_count = 0

        async def fail_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("ECONNRESET")
            return "ok"

        tool = _make_agent_tool(executor_fn=fail_once)
        tc = _make_tool_call()

        with patch("basket_agent.retry.asyncio.sleep", new_callable=AsyncMock):
            result, error = await execute_with_retry(tc, tool, policy=None)

        assert result == "ok"
        assert error is None
        assert call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

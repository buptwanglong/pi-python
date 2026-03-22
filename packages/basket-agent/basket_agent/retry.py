"""
Structured tool retry with exponential backoff.

Automatically retries transient errors (timeout, connection, rate_limit)
instead of wasting an LLM turn on retry decisions.
"""

import asyncio
import logging
from typing import Any, Callable, FrozenSet, Optional, Tuple

from pydantic import BaseModel, Field, ConfigDict

from basket_ai.types import ToolCall
from .types import AgentTool

logger = logging.getLogger(__name__)

# Patterns that indicate transient/retryable errors
DEFAULT_RETRYABLE_PATTERNS: FrozenSet[str] = frozenset({
    "timeout",
    "timed out",
    "connection",
    "ConnectionError",
    "ConnectionRefusedError",
    "ConnectionResetError",
    "TimeoutError",
    "rate_limit",
    "rate limit",
    "429",
    "503",
    "502",
    "HTTPError",
    "ECONNRESET",
    "ETIMEDOUT",
})


class RetryPolicy(BaseModel):
    """Configuration for tool retry behavior."""

    max_retries: int = Field(default=2, ge=0, le=5)
    backoff_base: float = Field(default=1.0, gt=0)
    retryable_patterns: FrozenSet[str] = DEFAULT_RETRYABLE_PATTERNS

    model_config = ConfigDict(frozen=True)


def is_retryable_error(error_str: str, policy: RetryPolicy) -> bool:
    """Check if an error string matches retryable patterns."""
    error_lower = error_str.lower()
    for pattern in policy.retryable_patterns:
        if pattern.lower() in error_lower:
            return True
    return False


async def execute_with_retry(
    tool_call: ToolCall,
    agent_tool: AgentTool,
    policy: Optional[RetryPolicy] = None,
    on_retry: Optional[Callable] = None,
) -> Tuple[Any, Optional[str]]:
    """
    Execute a tool call with automatic retry for transient errors.

    Args:
        tool_call: The tool call to execute
        agent_tool: The agent tool with executor
        policy: Retry policy (uses defaults if None)
        on_retry: Optional callback(tool_name, attempt, error, max_retries)
                  for event emission

    Returns:
        Tuple of (result, error_message)
    """
    policy = policy or RetryPolicy()

    if not agent_tool.executor:
        return None, f"No executor found for tool: {agent_tool.name}"

    last_error: Optional[str] = None

    for attempt in range(policy.max_retries + 1):
        try:
            result = await agent_tool.executor.execute(**tool_call.arguments)
            return result, None
        except Exception as e:
            last_error = str(e)

            is_last_attempt = attempt >= policy.max_retries
            if not is_last_attempt and is_retryable_error(last_error, policy):
                delay = policy.backoff_base * (2 ** attempt)
                logger.info(
                    "Retrying tool %s (attempt %d/%d) after error: %s (delay: %.1fs)",
                    tool_call.name,
                    attempt + 1,
                    policy.max_retries,
                    last_error,
                    delay,
                )

                if on_retry:
                    try:
                        if asyncio.iscoroutinefunction(on_retry):
                            await on_retry(
                                tool_call.name,
                                attempt + 1,
                                last_error,
                                policy.max_retries,
                            )
                        else:
                            on_retry(
                                tool_call.name,
                                attempt + 1,
                                last_error,
                                policy.max_retries,
                            )
                    except Exception:
                        pass  # Don't let callback errors break retry

                await asyncio.sleep(delay)
            else:
                # Not retryable or max retries reached
                break

    return None, last_error


__all__ = [
    "DEFAULT_RETRYABLE_PATTERNS",
    "RetryPolicy",
    "is_retryable_error",
    "execute_with_retry",
]

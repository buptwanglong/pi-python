"""
Tests for parallel tool execution in agent_loop.py.

Validates that:
- Single tool call works as before (backward compat)
- Multiple tool calls run in parallel (timing check)
- Exception in one tool doesn't block others
- Events are emitted correctly per tool (start before end)
- Tool-not-found is handled correctly in parallel
"""

import asyncio
import time

import pytest

from basket_agent.agent_loop import _execute_single_tool_call, execute_tool_call
from basket_agent.types import AgentState, AgentTool, ToolExecutor
from basket_ai.types import (
    Context,
    Model,
    ToolCall,
    UserMessage,
)


@pytest.fixture
def sample_model():
    """Create a sample model for testing."""
    return Model(
        id="gpt-4o-mini",
        name="GPT-4o Mini",
        api="openai-completions",
        provider="openai",
        baseUrl="https://api.openai.com/v1",
        reasoning=False,
        cost={"input": 0.15, "output": 0.6, "cacheRead": 0.075, "cacheWrite": 0.3},
        contextWindow=128000,
        maxTokens=16384,
    )


def _make_tool(name: str, fn) -> AgentTool:
    """Helper to create an AgentTool with an executor."""
    executor = ToolExecutor(name, f"{name} tool", fn)
    return AgentTool(
        name=name,
        description=f"{name} tool",
        parameters={},
        executor=executor,
    )


def _make_state(model, tools: list[AgentTool]) -> AgentState:
    """Helper to create an AgentState with tools."""
    context = Context(
        systemPrompt="test",
        messages=[UserMessage(role="user", content="test", timestamp=0)],
    )
    return AgentState(model=model, context=context, tools=tools)


def _make_tool_call(name: str, call_id: str, args: dict | None = None) -> ToolCall:
    """Helper to create a ToolCall."""
    return ToolCall(
        type="toolCall",
        id=call_id,
        name=name,
        arguments=args or {},
    )


class TestExecuteSingleToolCall:
    """Tests for the _execute_single_tool_call helper."""

    @pytest.mark.asyncio
    async def test_single_tool_call_works(self, sample_model):
        """Single tool call returns result with correct events (backward compat)."""

        async def add(a: int, b: int) -> int:
            return a + b

        tool = _make_tool("add", add)
        state = _make_state(sample_model, [tool])
        tc = _make_tool_call("add", "call_1", {"a": 3, "b": 4})

        result = await _execute_single_tool_call(tc, state)

        assert result["tool_call_id"] == "call_1"
        assert result["tool_name"] == "add"
        assert result["result"] == 7
        assert result["error"] is None
        assert len(result["events"]) == 2

        # First event is start, second is end
        assert result["events"][0].type == "agent_tool_call_start"
        assert result["events"][0].tool_name == "add"
        assert result["events"][1].type == "agent_tool_call_end"
        assert result["events"][1].result == 7
        assert result["events"][1].error is None

    @pytest.mark.asyncio
    async def test_tool_not_found_handled(self, sample_model):
        """Tool not found produces error result with start+end events."""
        state = _make_state(sample_model, [])
        tc = _make_tool_call("nonexistent", "call_missing")

        result = await _execute_single_tool_call(tc, state)

        assert result["tool_name"] == "nonexistent"
        assert result["result"] is None
        assert "Tool not found" in result["error"]
        assert len(result["events"]) == 2
        assert result["events"][0].type == "agent_tool_call_start"
        assert result["events"][1].type == "agent_tool_call_end"
        assert "Tool not found" in result["events"][1].error

    @pytest.mark.asyncio
    async def test_tool_error_captured(self, sample_model):
        """Tool execution error is captured, not raised."""

        async def failing() -> str:
            raise RuntimeError("Tool failed!")

        tool = _make_tool("fail", failing)
        state = _make_state(sample_model, [tool])
        tc = _make_tool_call("fail", "call_fail")

        result = await _execute_single_tool_call(tc, state)

        assert result["result"] is None
        assert "Tool failed!" in result["error"]
        assert len(result["events"]) == 2
        assert result["events"][1].type == "agent_tool_call_end"
        assert "Tool failed!" in result["events"][1].error


class TestParallelExecution:
    """Tests for parallel tool execution via asyncio.gather."""

    @pytest.mark.asyncio
    async def test_multiple_tools_run_in_parallel(self, sample_model):
        """Multiple tool calls run concurrently, not sequentially.

        Each tool sleeps for 0.1s. If run sequentially, total >= 0.3s.
        If parallel, total should be ~0.1s.
        """

        async def slow_tool(label: str) -> str:
            await asyncio.sleep(0.1)
            return f"done-{label}"

        tools = [_make_tool(f"tool_{i}", slow_tool) for i in range(3)]
        state = _make_state(sample_model, tools)

        tool_calls = [
            _make_tool_call(f"tool_{i}", f"call_{i}", {"label": str(i)})
            for i in range(3)
        ]

        start = time.monotonic()
        tasks = [_execute_single_tool_call(tc, state) for tc in tool_calls]
        results = await asyncio.gather(*tasks)
        elapsed = time.monotonic() - start

        # All should succeed
        for i, r in enumerate(results):
            assert r["result"] == f"done-{i}"
            assert r["error"] is None

        # Should take ~0.1s, not ~0.3s. Use 0.25s as threshold.
        assert elapsed < 0.25, f"Parallel execution took {elapsed:.3f}s, expected < 0.25s"

    @pytest.mark.asyncio
    async def test_exception_in_one_doesnt_block_others(self, sample_model):
        """One tool raising an exception doesn't prevent others from completing."""

        async def good_tool() -> str:
            await asyncio.sleep(0.05)
            return "ok"

        async def bad_tool() -> str:
            await asyncio.sleep(0.02)
            raise ValueError("Boom!")

        good = _make_tool("good", good_tool)
        bad = _make_tool("bad", bad_tool)
        state = _make_state(sample_model, [good, bad])

        tc_good = _make_tool_call("good", "call_good")
        tc_bad = _make_tool_call("bad", "call_bad")

        tasks = [
            _execute_single_tool_call(tc_good, state),
            _execute_single_tool_call(tc_bad, state),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Good tool should succeed
        assert results[0]["result"] == "ok"
        assert results[0]["error"] is None

        # Bad tool should have error captured (not an exception, since
        # execute_tool_call catches exceptions)
        assert results[1]["result"] is None
        assert "Boom!" in results[1]["error"]

    @pytest.mark.asyncio
    async def test_events_emitted_correctly_for_parallel(self, sample_model):
        """Each tool call produces start event before end event."""

        async def echo(msg: str) -> str:
            return msg

        tools = [_make_tool("echo", echo)]
        state = _make_state(sample_model, tools)

        tool_calls = [
            _make_tool_call("echo", f"call_{i}", {"msg": f"hello{i}"})
            for i in range(3)
        ]

        tasks = [_execute_single_tool_call(tc, state) for tc in tool_calls]
        results = await asyncio.gather(*tasks)

        for r in results:
            events = r["events"]
            # Must have at least start + end
            assert len(events) >= 2
            # Start must come before end
            start_idx = next(
                i for i, e in enumerate(events) if e.type == "agent_tool_call_start"
            )
            end_idx = next(
                i for i, e in enumerate(events) if e.type == "agent_tool_call_end"
            )
            assert start_idx < end_idx

    @pytest.mark.asyncio
    async def test_tool_not_found_handled_in_parallel(self, sample_model):
        """Tool-not-found mixed with valid tools is handled correctly."""

        async def valid() -> str:
            return "valid_result"

        tool = _make_tool("valid", valid)
        state = _make_state(sample_model, [tool])

        tc_valid = _make_tool_call("valid", "call_valid")
        tc_missing = _make_tool_call("missing", "call_missing")

        tasks = [
            _execute_single_tool_call(tc_valid, state),
            _execute_single_tool_call(tc_missing, state),
        ]
        results = await asyncio.gather(*tasks)

        # Valid tool succeeds
        assert results[0]["result"] == "valid_result"
        assert results[0]["error"] is None

        # Missing tool returns error
        assert results[1]["result"] is None
        assert "Tool not found" in results[1]["error"]

    @pytest.mark.asyncio
    async def test_gather_exception_handling(self, sample_model):
        """asyncio.gather with return_exceptions=True handles unexpected exceptions."""

        async def crash_tool() -> str:
            raise RuntimeError("Unexpected crash")

        tool = _make_tool("crash", crash_tool)
        state = _make_state(sample_model, [tool])
        tc = _make_tool_call("crash", "call_crash")

        results = await asyncio.gather(
            _execute_single_tool_call(tc, state),
            return_exceptions=True,
        )

        # execute_tool_call catches exceptions, so result should be a dict not an exception
        assert isinstance(results[0], dict)
        assert results[0]["error"] is not None
        assert "Unexpected crash" in results[0]["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

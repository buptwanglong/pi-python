"""
Tests for the agent execution loop.
"""

import pytest

from basket_agent.agent_loop import execute_tool_call, run_agent_turn
from basket_agent.types import AgentState, AgentTool, ToolExecutor
from basket_ai.types import (
    AssistantMessage,
    Context,
    Model,
    TextContent,
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


class TestExecuteToolCall:
    """Tests for execute_tool_call function."""

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Test successful tool execution."""

        async def multiply(a: int, b: int) -> int:
            return a * b

        executor = ToolExecutor("multiply", "Multiply numbers", multiply)
        tool = AgentTool(
            name="multiply", description="Multiply numbers", parameters={}, executor=executor
        )

        tool_call = ToolCall(
            type="toolCall",
            id="call_123",
            name="multiply",
            arguments={"a": 5, "b": 3},
        )

        result, error = await execute_tool_call(tool_call, tool)

        assert result == 15
        assert error is None

    @pytest.mark.asyncio
    async def test_execution_error(self):
        """Test tool execution with error."""

        async def failing_tool():
            raise ValueError("Something went wrong")

        executor = ToolExecutor("fail", "Failing tool", failing_tool)
        tool = AgentTool(
            name="fail", description="Failing tool", parameters={}, executor=executor
        )

        tool_call = ToolCall(
            type="toolCall",
            id="call_456",
            name="fail",
            arguments={},
        )

        result, error = await execute_tool_call(tool_call, tool)

        assert result is None
        assert error == "Something went wrong"

    @pytest.mark.asyncio
    async def test_missing_executor(self):
        """Test tool call with missing executor."""
        tool = AgentTool(
            name="no_executor",
            description="Tool without executor",
            parameters={},
            executor=None,
        )

        tool_call = ToolCall(
            type="toolCall",
            id="call_789",
            name="no_executor",
            arguments={},
        )

        result, error = await execute_tool_call(tool_call, tool)

        assert result is None
        assert "No executor found" in error


class TestRunAgentTurn:
    """Tests for run_agent_turn function."""

    @pytest.mark.skip(reason="Requires mocked LLM API")
    @pytest.mark.asyncio
    async def test_simple_turn_no_tools(self, sample_model):
        """Test a simple turn without tool calls."""
        context = Context(
            systemPrompt="You are helpful.",
            messages=[UserMessage(role="user", content="Hello", timestamp=0)],
        )

        state = AgentState(model=sample_model, context=context)

        events = []
        async for event in run_agent_turn(state, stream_llm_events=False):
            events.append(event)

        # Should have turn_start and turn_end events
        assert any(e.get("type") == "agent_turn_start" for e in events)
        assert any(e.get("type") == "agent_turn_end" for e in events)

        # Turn counter should be incremented
        assert state.current_turn == 1


class TestAgentLoopIntegration:
    """Integration tests for agent loop (require actual LLM)."""

    @pytest.mark.skip(reason="Requires API key and real LLM")
    @pytest.mark.asyncio
    async def test_agent_with_calculator_tool(self, sample_model):
        """Test agent with a calculator tool."""
        from pydantic import BaseModel, Field

        class CalculatorParams(BaseModel):
            a: int = Field(..., description="First number")
            b: int = Field(..., description="Second number")
            operation: str = Field(..., description="Operation: add, subtract")

        async def calculator(a: int, b: int, operation: str) -> int:
            if operation == "add":
                return a + b
            elif operation == "subtract":
                return a - b
            else:
                raise ValueError(f"Unknown operation: {operation}")

        executor = ToolExecutor("calculator", "Calculate", calculator)
        tool = AgentTool(
            name="calculator",
            description="Perform arithmetic",
            parameters=CalculatorParams,
            executor=executor,
        )

        context = Context(
            systemPrompt="You are a calculator assistant.",
            messages=[
                UserMessage(role="user", content="What is 15 + 27?", timestamp=0)
            ],
            tools=[],
        )

        state = AgentState(model=sample_model, context=context, tools=[tool])

        from basket_agent.agent_loop import run_agent_loop

        events = []
        async for event in run_agent_loop(state, stream_llm_events=False):
            events.append(event)
            if event.get("type") == "agent_complete":
                break

        # Should have tool call events
        assert any(e.get("type") == "agent_tool_call_start" for e in events)
        assert any(e.get("type") == "agent_tool_call_end" for e in events)

        # Should complete
        assert any(e.get("type") == "agent_complete" for e in events)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

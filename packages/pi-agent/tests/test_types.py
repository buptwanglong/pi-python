"""
Tests for agent types and state management.
"""

import pytest

from pi_agent.types import (
    AgentState,
    AgentTool,
    FollowUpMessage,
    SteeringMessage,
    ToolExecutor,
)
from pi_ai.types import Context, Model, UserMessage


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


@pytest.fixture
def sample_context():
    """Create a sample context for testing."""
    return Context(
        systemPrompt="You are a helpful assistant.",
        messages=[
            UserMessage(role="user", content="Hello!", timestamp=1234567890000)
        ],
    )


class TestSteeringMessage:
    """Tests for SteeringMessage."""

    def test_basic_steering(self):
        """Test basic steering message creation."""
        msg = SteeringMessage(content="Be concise")
        assert msg.content == "Be concise"
        assert msg.priority == 0

    def test_steering_with_priority(self):
        """Test steering message with priority."""
        msg = SteeringMessage(content="Critical instruction", priority=10)
        assert msg.content == "Critical instruction"
        assert msg.priority == 10


class TestFollowUpMessage:
    """Tests for FollowUpMessage."""

    def test_basic_follow_up(self):
        """Test basic follow-up message."""
        msg = FollowUpMessage(content="Continue the task")
        assert msg.content == "Continue the task"


class TestToolExecutor:
    """Tests for ToolExecutor."""

    @pytest.mark.asyncio
    async def test_tool_executor(self):
        """Test basic tool executor."""

        async def add_numbers(a: int, b: int) -> int:
            return a + b

        executor = ToolExecutor("add", "Add two numbers", add_numbers)
        result = await executor.execute(a=5, b=3)
        assert result == 8

    @pytest.mark.asyncio
    async def test_tool_executor_error(self):
        """Test tool executor with error."""

        async def failing_tool():
            raise ValueError("Tool failed")

        executor = ToolExecutor("fail", "Failing tool", failing_tool)

        with pytest.raises(ValueError, match="Tool failed"):
            await executor.execute()


class TestAgentTool:
    """Tests for AgentTool."""

    def test_basic_agent_tool(self):
        """Test basic agent tool creation."""
        from pydantic import BaseModel, Field

        class AddParams(BaseModel):
            a: int = Field(..., description="First number")
            b: int = Field(..., description="Second number")

        tool = AgentTool(
            name="add",
            description="Add two numbers",
            parameters=AddParams,
        )

        assert tool.name == "add"
        assert tool.description == "Add two numbers"
        assert tool.parameters == AddParams
        assert tool.executor is None


class TestAgentState:
    """Tests for AgentState."""

    def test_basic_state(self, sample_model, sample_context):
        """Test basic agent state creation."""
        state = AgentState(model=sample_model, context=sample_context)

        assert state.model == sample_model
        assert state.context == sample_context
        assert len(state.tools) == 0
        assert len(state.steering_messages) == 0
        assert len(state.follow_up_messages) == 0
        assert state.max_turns == 10
        assert state.current_turn == 0

    def test_add_message(self, sample_model, sample_context):
        """Test adding messages to state."""
        state = AgentState(model=sample_model, context=sample_context)
        initial_count = len(state.context.messages)

        new_msg = UserMessage(role="user", content="Test", timestamp=0)
        state.add_message(new_msg)

        assert len(state.context.messages) == initial_count + 1
        assert state.context.messages[-1] == new_msg

    def test_add_steering(self, sample_model, sample_context):
        """Test adding steering messages."""
        state = AgentState(model=sample_model, context=sample_context)

        state.add_steering("Be concise")
        state.add_steering("Use examples", priority=5)

        assert len(state.steering_messages) == 2
        assert state.steering_messages[0].content == "Be concise"
        assert state.steering_messages[1].priority == 5

    def test_clear_steering(self, sample_model, sample_context):
        """Test clearing steering messages."""
        state = AgentState(model=sample_model, context=sample_context)

        state.add_steering("Message 1")
        state.add_steering("Message 2")
        assert len(state.steering_messages) == 2

        state.clear_steering()
        assert len(state.steering_messages) == 0

    def test_add_follow_up(self, sample_model, sample_context):
        """Test adding follow-up messages."""
        state = AgentState(model=sample_model, context=sample_context)

        state.add_follow_up("Continue task")
        state.add_follow_up("Final step")

        assert len(state.follow_up_messages) == 2

    def test_pop_follow_up(self, sample_model, sample_context):
        """Test popping follow-up messages."""
        state = AgentState(model=sample_model, context=sample_context)

        state.add_follow_up("First")
        state.add_follow_up("Second")

        first = state.pop_follow_up()
        assert first == "First"
        assert len(state.follow_up_messages) == 1

        second = state.pop_follow_up()
        assert second == "Second"
        assert len(state.follow_up_messages) == 0

        none = state.pop_follow_up()
        assert none is None

    def test_get_tool(self, sample_model, sample_context):
        """Test getting tool by name."""
        state = AgentState(model=sample_model, context=sample_context)

        tool1 = AgentTool(name="add", description="Add", parameters={})
        tool2 = AgentTool(name="subtract", description="Subtract", parameters={})

        state.tools.append(tool1)
        state.tools.append(tool2)

        found = state.get_tool("add")
        assert found is not None
        assert found.name == "add"

        not_found = state.get_tool("multiply")
        assert not_found is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

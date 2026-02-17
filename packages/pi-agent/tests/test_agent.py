"""
Tests for the Agent class.
"""

import pytest

from pi_agent import Agent
from pi_ai.types import Context, Model


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


class TestAgentInit:
    """Tests for Agent initialization."""

    def test_basic_init(self, sample_model):
        """Test basic agent initialization."""
        agent = Agent(sample_model)

        assert agent.model == sample_model
        assert agent.context is not None
        assert len(agent.context.messages) == 0
        assert len(agent.tools) == 0
        assert len(agent.event_handlers) == 0
        assert agent.max_turns == 10

    def test_init_with_context(self, sample_model):
        """Test agent initialization with context."""
        from pi_ai.types import UserMessage

        context = Context(
            systemPrompt="Custom system prompt",
            messages=[UserMessage(role="user", content="Hello", timestamp=0)],
        )

        agent = Agent(sample_model, context)

        assert agent.context == context
        assert len(agent.context.messages) == 1


class TestAgentToolRegistration:
    """Tests for tool registration."""

    def test_register_simple_tool(self, sample_model):
        """Test registering a simple tool."""
        from pydantic import BaseModel, Field

        class AddParams(BaseModel):
            a: int = Field(..., description="First number")
            b: int = Field(..., description="Second number")

        agent = Agent(sample_model)

        async def add(a: int, b: int) -> int:
            return a + b

        agent.register_tool(
            name="add",
            description="Add two numbers",
            parameters=AddParams,
            execute_fn=add,
        )

        assert len(agent.tools) == 1
        assert agent.tools[0].name == "add"
        assert agent.tools[0].executor is not None

        # Should also be in context tools
        assert len(agent.context.tools) == 1
        assert agent.context.tools[0].name == "add"

    def test_register_multiple_tools(self, sample_model):
        """Test registering multiple tools."""
        from pydantic import BaseModel

        class MathParams(BaseModel):
            a: int
            b: int

        agent = Agent(sample_model)

        async def add(a: int, b: int) -> int:
            return a + b

        async def multiply(a: int, b: int) -> int:
            return a * b

        agent.register_tool("add", "Add numbers", MathParams, add)
        agent.register_tool("multiply", "Multiply numbers", MathParams, multiply)

        assert len(agent.tools) == 2
        assert len(agent.context.tools) == 2


class TestAgentEventSubscription:
    """Tests for event subscriptions."""

    def test_subscribe_to_event(self, sample_model):
        """Test subscribing to an event."""
        agent = Agent(sample_model)
        called = []

        def handler(event):
            called.append(event)

        agent.on("test_event", handler)

        assert "test_event" in agent.event_handlers
        assert len(agent.event_handlers["test_event"]) == 1

    def test_multiple_handlers(self, sample_model):
        """Test multiple handlers for same event."""
        agent = Agent(sample_model)

        def handler1(event):
            pass

        def handler2(event):
            pass

        agent.on("test_event", handler1)
        agent.on("test_event", handler2)

        assert len(agent.event_handlers["test_event"]) == 2

    @pytest.mark.asyncio
    async def test_emit_event(self, sample_model):
        """Test event emission."""
        agent = Agent(sample_model)
        events_received = []

        def sync_handler(event):
            events_received.append(("sync", event))

        async def async_handler(event):
            events_received.append(("async", event))

        agent.on("test", sync_handler)
        agent.on("test", async_handler)

        await agent._emit_event({"type": "test", "data": "value"})

        assert len(events_received) == 2
        assert events_received[0][0] == "sync"
        assert events_received[1][0] == "async"


class TestAgentRun:
    """Tests for agent run methods."""

    @pytest.mark.skip(reason="Requires mocked LLM API")
    @pytest.mark.asyncio
    async def test_run_with_steering(self, sample_model):
        """Test running agent with steering messages."""
        agent = Agent(sample_model)

        state = await agent.run(
            steering_messages=["Be concise", "Use examples"],
            stream_llm_events=False,
        )

        assert state is not None
        assert state.current_turn > 0

    @pytest.mark.skip(reason="Requires mocked LLM API")
    @pytest.mark.asyncio
    async def test_run_once(self, sample_model):
        """Test run_once convenience method."""
        agent = Agent(sample_model)

        state = await agent.run_once("Hello!", stream_llm_events=False)

        assert state is not None
        assert len(agent.context.messages) > 0


class TestAgentIntegration:
    """Integration tests for Agent (require actual LLM)."""

    @pytest.mark.skip(reason="Requires API key and real LLM")
    @pytest.mark.asyncio
    async def test_agent_with_tool_execution(self, sample_model):
        """Test agent with actual tool execution."""
        from pydantic import BaseModel, Field

        class WeatherParams(BaseModel):
            city: str = Field(..., description="City name")

        agent = Agent(sample_model)

        async def get_weather(city: str) -> str:
            return f"The weather in {city} is sunny and 25°C"

        agent.register_tool(
            name="get_weather",
            description="Get weather for a city",
            parameters=WeatherParams,
            execute_fn=get_weather,
        )

        # Track events
        events = []

        def event_handler(event):
            events.append(event)

        agent.on("agent_tool_call_start", event_handler)
        agent.on("agent_tool_call_end", event_handler)
        agent.on("agent_complete", event_handler)

        # Run agent
        state = await agent.run_once("What's the weather in Paris?")

        # Should have called the tool
        tool_start_events = [e for e in events if e["type"] == "agent_tool_call_start"]
        assert len(tool_start_events) > 0

        tool_end_events = [e for e in events if e["type"] == "agent_tool_call_end"]
        assert len(tool_end_events) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

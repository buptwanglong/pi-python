"""
Integration tests for OpenAI Completions provider.

These tests require OPENAI_API_KEY to be set in the environment.
"""

import asyncio
import os

import pytest

from basket_ai.providers.openai_completions import OpenAICompletionsProvider
from basket_ai.types import Context, Model, UserMessage


@pytest.fixture
def openai_provider():
    """Create OpenAI provider instance."""
    return OpenAICompletionsProvider()


@pytest.fixture
def gpt4_model():
    """Create GPT-4 model configuration."""
    return Model(
        id="gpt-4o-mini",
        name="GPT-4o Mini",
        api="openai-completions",
        provider="openai",
        baseUrl="https://api.openai.com/v1",
        reasoning=False,
        cost={
            "input": 0.15,
            "output": 0.6,
            "cacheRead": 0.075,
            "cacheWrite": 0.3,
        },
        contextWindow=128000,
        maxTokens=16384,
    )


@pytest.fixture
def simple_context():
    """Create simple test context."""
    return Context(
        systemPrompt="You are a helpful assistant.",
        messages=[
            UserMessage(
                role="user",
                content="Say 'Hello, World!' and nothing else.",
                timestamp=1234567890000,
            )
        ],
    )


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"
)
@pytest.mark.asyncio
async def test_openai_basic_streaming(openai_provider, gpt4_model, simple_context):
    """Test basic streaming with OpenAI provider."""
    stream = await openai_provider.stream(gpt4_model, simple_context)

    # Collect events
    events = []
    async for event in stream:
        events.append(event)

    # Get final result
    result = await stream.result()

    # Assertions
    assert len(events) > 0
    assert events[0]["type"] == "start"
    assert events[-1]["type"] == "done"

    assert result.role == "assistant"
    assert len(result.content) > 0
    assert result.stopReason in ["stop", "length"]

    # Check for "Hello" in response
    text_content = "".join(
        block.text for block in result.content if block.type == "text"
    )
    assert "Hello" in text_content


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"
)
@pytest.mark.asyncio
async def test_openai_usage_tracking(openai_provider, gpt4_model, simple_context):
    """Test that usage information is tracked correctly."""
    stream = await openai_provider.stream(gpt4_model, simple_context)

    # Consume stream
    async for _ in stream:
        pass

    # Get result
    result = await stream.result()

    # Check usage
    assert result.usage.input > 0
    assert result.usage.output > 0
    assert result.usage.total_tokens > 0
    assert result.usage.cost.total > 0


@pytest.mark.skip(reason="Requires tool calling setup")
@pytest.mark.asyncio
async def test_openai_tool_calling(openai_provider, gpt4_model):
    """Test tool calling with OpenAI provider."""
    from pydantic import BaseModel, Field

    class CalculatorParams(BaseModel):
        a: int = Field(..., description="First number")
        b: int = Field(..., description="Second number")
        operation: str = Field(..., description="Operation: add, subtract, multiply, divide")

    from basket_ai.types import Tool

    context = Context(
        systemPrompt="You are a helpful assistant with calculator capabilities.",
        messages=[
            UserMessage(
                role="user",
                content="What is 15 + 27?",
                timestamp=1234567890000,
            )
        ],
        tools=[
            Tool(
                name="calculator",
                description="Perform arithmetic operations",
                parameters=CalculatorParams,
            )
        ],
    )

    stream = await openai_provider.stream(gpt4_model, context)

    # Collect events
    events = []
    async for event in stream:
        events.append(event)

    result = await stream.result()

    # Check for tool call
    has_tool_call = any(
        block.type == "toolCall" for block in result.content
    )
    assert has_tool_call, "Expected tool call in response"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

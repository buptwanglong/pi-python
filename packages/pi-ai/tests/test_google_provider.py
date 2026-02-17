"""
Integration tests for Google Generative AI provider.

These tests require GOOGLE_API_KEY to be set in the environment.
"""

import asyncio
import os

import pytest

from pi_ai.providers.google import GoogleProvider
from pi_ai.types import Context, Model, UserMessage


@pytest.fixture
def google_provider():
    """Create Google provider instance."""
    return GoogleProvider()


@pytest.fixture
def gemini_model():
    """Create Gemini model configuration."""
    return Model(
        id="gemini-2.0-flash-exp",
        name="Gemini 2.0 Flash",
        api="google-generative-ai",
        provider="google",
        baseUrl="https://generativelanguage.googleapis.com",
        reasoning=False,
        cost={
            "input": 0.0,
            "output": 0.0,
            "cacheRead": 0.0,
            "cacheWrite": 0.0,
        },
        contextWindow=1000000,
        maxTokens=8192,
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
    not os.getenv("GOOGLE_API_KEY"), reason="GOOGLE_API_KEY not set"
)
@pytest.mark.asyncio
async def test_google_basic_streaming(google_provider, gemini_model, simple_context):
    """Test basic streaming with Google provider."""
    stream = await google_provider.stream(gemini_model, simple_context)

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
    not os.getenv("GOOGLE_API_KEY"), reason="GOOGLE_API_KEY not set"
)
@pytest.mark.asyncio
async def test_google_usage_tracking(google_provider, gemini_model, simple_context):
    """Test that usage information is tracked correctly."""
    stream = await google_provider.stream(gemini_model, simple_context)

    # Consume stream
    async for _ in stream:
        pass

    # Get result
    result = await stream.result()

    # Check usage
    assert result.usage.input > 0
    assert result.usage.output > 0
    assert result.usage.total_tokens > 0


@pytest.mark.skip(reason="Requires tool calling setup")
@pytest.mark.asyncio
async def test_google_tool_calling(google_provider, gemini_model):
    """Test tool calling with Google provider."""
    from pydantic import BaseModel, Field

    class CalculatorParams(BaseModel):
        a: int = Field(..., description="First number")
        b: int = Field(..., description="Second number")
        operation: str = Field(..., description="Operation: add, subtract, multiply, divide")

    from pi_ai.types import Tool

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

    stream = await google_provider.stream(gemini_model, context)

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

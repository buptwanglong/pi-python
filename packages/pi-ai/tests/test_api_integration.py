"""
Integration tests for the unified API with multiple providers.

These tests require API keys to be set in the environment:
- OPENAI_API_KEY for OpenAI
- ANTHROPIC_API_KEY for Anthropic
- GOOGLE_API_KEY for Google
"""

import os

import pytest

from pi_ai.api import complete, get_model, stream
from pi_ai.types import Context, Model, UserMessage


@pytest.fixture
def simple_prompt():
    """Create simple test prompt."""
    return Context(
        systemPrompt="You are a helpful assistant.",
        messages=[
            UserMessage(
                role="user",
                content="Say 'Hello!' and nothing else.",
                timestamp=1234567890000,
            )
        ],
    )


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"
)
@pytest.mark.asyncio
async def test_openai_via_unified_api(simple_prompt):
    """Test OpenAI through unified API."""
    model = get_model("openai", "gpt-4o-mini")

    # Test streaming
    event_stream = await stream(model, simple_prompt)
    events = []
    async for event in event_stream:
        events.append(event)

    result = await event_stream.result()

    assert len(events) > 0
    assert events[0]["type"] == "start"
    assert events[-1]["type"] == "done"
    assert result.role == "assistant"
    assert len(result.content) > 0

    # Check response contains "Hello"
    text = "".join(b.text for b in result.content if b.type == "text")
    assert "Hello" in text


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set"
)
@pytest.mark.asyncio
async def test_anthropic_via_unified_api(simple_prompt):
    """Test Anthropic through unified API."""
    model = get_model("anthropic", "claude-sonnet-4-20250514")

    # Test complete() convenience function
    result = await complete(model, simple_prompt)

    assert result.role == "assistant"
    assert len(result.content) > 0
    assert result.stopReason in ["stop", "end_turn"]

    # Check response contains "Hello"
    text = "".join(b.text for b in result.content if b.type == "text")
    assert "Hello" in text


@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"), reason="GOOGLE_API_KEY not set"
)
@pytest.mark.asyncio
async def test_google_via_unified_api(simple_prompt):
    """Test Google through unified API."""
    model = get_model("google", "gemini-2.0-flash-exp")

    # Test streaming
    event_stream = await stream(model, simple_prompt)

    # Collect all events
    events = []
    async for event in event_stream:
        events.append(event)

    result = await event_stream.result()

    assert len(events) > 0
    assert events[0]["type"] == "start"
    assert events[-1]["type"] == "done"
    assert result.role == "assistant"

    # Check response
    text = "".join(b.text for b in result.content if b.type == "text")
    assert "Hello" in text


@pytest.mark.skipif(
    not (os.getenv("OPENAI_API_KEY") and os.getenv("ANTHROPIC_API_KEY")),
    reason="Both OPENAI_API_KEY and ANTHROPIC_API_KEY required"
)
@pytest.mark.asyncio
async def test_cross_provider_comparison():
    """Compare responses from different providers."""
    prompt = Context(
        systemPrompt="You are a helpful assistant.",
        messages=[
            UserMessage(
                role="user",
                content="What is 2+2? Answer with just the number.",
                timestamp=1234567890000,
            )
        ],
    )

    # Get responses from both providers
    openai_model = get_model("openai", "gpt-4o-mini")
    anthropic_model = get_model("anthropic", "claude-sonnet-4-20250514")

    openai_result = await complete(openai_model, prompt)
    anthropic_result = await complete(anthropic_model, prompt)

    # Both should contain "4"
    openai_text = "".join(b.text for b in openai_result.content if b.type == "text")
    anthropic_text = "".join(b.text for b in anthropic_result.content if b.type == "text")

    assert "4" in openai_text
    assert "4" in anthropic_text

    # Both should have usage info
    assert openai_result.usage.input > 0
    assert anthropic_result.usage.input > 0


@pytest.mark.asyncio
async def test_get_model_defaults():
    """Test get_model() convenience function defaults."""
    # OpenAI
    openai_model = get_model("openai", "gpt-4")
    assert openai_model.id == "gpt-4"
    assert openai_model.api == "openai-completions"
    assert openai_model.provider == "openai"
    assert openai_model.baseUrl == "https://api.openai.com/v1"
    assert openai_model.contextWindow == 128000

    # Anthropic
    anthropic_model = get_model("anthropic", "claude-3-opus-20240229")
    assert anthropic_model.id == "claude-3-opus-20240229"
    assert anthropic_model.api == "anthropic-messages"
    assert anthropic_model.provider == "anthropic"
    assert anthropic_model.baseUrl == "https://api.anthropic.com"

    # Google
    google_model = get_model("google", "gemini-pro")
    assert google_model.id == "gemini-pro"
    assert google_model.api == "google-generative-ai"
    assert google_model.provider == "google"
    assert google_model.baseUrl == "https://generativelanguage.googleapis.com"


@pytest.mark.asyncio
async def test_get_model_custom_params():
    """Test get_model() with custom parameters."""
    model = get_model(
        "openai",
        "gpt-4",
        name="My Custom GPT-4",
        reasoning=True,
        context_window=200000,
        max_tokens=8192,
    )

    assert model.name == "My Custom GPT-4"
    assert model.reasoning is True
    assert model.contextWindow == 200000
    assert model.maxTokens == 8192


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

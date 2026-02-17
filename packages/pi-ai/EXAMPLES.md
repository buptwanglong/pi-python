# Pi-AI Usage Examples

This guide shows how to use the pi-ai unified API for streaming LLM responses.

## Installation

```bash
cd packages/pi-ai
poetry install

# Install provider SDKs
poetry add openai anthropic google-generativeai
```

## Basic Usage

### Streaming Responses

```python
import asyncio
from pi_ai.api import stream, get_model
from pi_ai.types import Context, UserMessage

async def main():
    # Create a model configuration
    model = get_model("openai", "gpt-4o-mini")

    # Create a conversation context
    context = Context(
        systemPrompt="You are a helpful assistant.",
        messages=[
            UserMessage(
                role="user",
                content="Explain Python async/await in one sentence.",
                timestamp=1234567890000,
            )
        ],
    )

    # Stream the response
    event_stream = await stream(model, context)

    # Print text as it streams
    async for event in event_stream:
        if event["type"] == "text_delta":
            print(event["delta"], end="", flush=True)

    print()  # Newline

    # Get the final message
    final_message = await event_stream.result()
    print(f"\nTokens used: {final_message.usage.total_tokens}")
    print(f"Cost: ${final_message.usage.cost.total:.6f}")

asyncio.run(main())
```

### Complete (Non-Streaming)

```python
import asyncio
from pi_ai.api import complete, get_model
from pi_ai.types import Context, UserMessage

async def main():
    model = get_model("anthropic", "claude-sonnet-4-20250514")

    context = Context(
        systemPrompt="You are a helpful assistant.",
        messages=[
            UserMessage(
                role="user",
                content="What is the capital of France?",
                timestamp=1234567890000,
            )
        ],
    )

    # Get the complete response (no streaming)
    message = await complete(model, context)

    # Extract text content
    text = "".join(block.text for block in message.content if block.type == "text")
    print(text)

asyncio.run(main())
```

## Multi-Provider Support

### OpenAI

```python
from pi_ai.api import get_model, stream

# GPT-4
model = get_model("openai", "gpt-4o")

# GPT-4 Mini
model = get_model("openai", "gpt-4o-mini")

# Custom configuration
model = get_model(
    "openai",
    "gpt-4",
    base_url="https://api.openai.com/v1",
    max_tokens=8192,
)
```

### Anthropic Claude

```python
from pi_ai.api import get_model

# Claude Sonnet 4
model = get_model("anthropic", "claude-sonnet-4-20250514")

# Claude Opus 3.5
model = get_model("anthropic", "claude-3-5-sonnet-20241022")
```

### Google Gemini

```python
from pi_ai.api import get_model

# Gemini 2.0 Flash
model = get_model("google", "gemini-2.0-flash-exp")

# Gemini Pro
model = get_model("google", "gemini-pro")
```

## Event Types

The streaming API emits various event types:

```python
async for event in event_stream:
    match event["type"]:
        case "start":
            print("Stream started")

        case "text_start":
            print("Text block started")

        case "text_delta":
            print(event["delta"], end="")

        case "text_end":
            print(f"\nText block finished: {event['content']}")

        case "thinking_start":
            print("Model is thinking...")

        case "thinking_delta":
            print(f"Thinking: {event['delta']}")

        case "thinking_end":
            print(f"Thought complete: {event['content']}")

        case "toolcall_start":
            print(f"Tool call started: {event['partial'].content[event['contentIndex']].name}")

        case "toolcall_delta":
            print(f"Tool arguments: {event['delta']}")

        case "toolcall_end":
            tool_call = event["toolCall"]
            print(f"Tool: {tool_call.name}({tool_call.arguments})")

        case "done":
            print(f"Stream complete. Reason: {event['reason']}")

        case "error":
            print(f"Error: {event['error'].errorMessage}")
```

## Tool Calling

```python
import asyncio
from pydantic import BaseModel, Field
from pi_ai.api import stream, get_model
from pi_ai.types import Context, UserMessage, Tool

class WeatherParams(BaseModel):
    location: str = Field(..., description="City name")
    units: str = Field("celsius", description="Temperature units: celsius or fahrenheit")

async def main():
    model = get_model("openai", "gpt-4o-mini")

    context = Context(
        systemPrompt="You are a helpful weather assistant.",
        messages=[
            UserMessage(
                role="user",
                content="What's the weather in Paris?",
                timestamp=1234567890000,
            )
        ],
        tools=[
            Tool(
                name="get_weather",
                description="Get current weather for a location",
                parameters=WeatherParams,
            )
        ],
    )

    event_stream = await stream(model, context)

    async for event in event_stream:
        if event["type"] == "toolcall_end":
            tool_call = event["toolCall"]
            print(f"Tool: {tool_call.name}")
            print(f"Args: {tool_call.arguments}")
            # Here you would execute the tool and send results back

asyncio.run(main())
```

## Streaming Options

```python
from pi_ai.types import StreamOptions

options = StreamOptions(
    temperature=0.7,
    max_tokens=1000,
    api_key="your-api-key-here",  # Override environment variable
)

event_stream = await stream(model, context, options)
```

## Multi-Turn Conversations

```python
import asyncio
from pi_ai.api import complete, get_model
from pi_ai.types import Context, UserMessage, AssistantMessage, TextContent

async def main():
    model = get_model("openai", "gpt-4o-mini")

    # First turn
    context = Context(
        systemPrompt="You are a helpful assistant.",
        messages=[
            UserMessage(
                role="user",
                content="My name is Alice.",
                timestamp=1234567890000,
            )
        ],
    )

    response1 = await complete(model, context)
    print("Assistant:", response1.content[0].text)

    # Second turn (add assistant response and new user message)
    context.messages.append(response1)
    context.messages.append(
        UserMessage(
            role="user",
            content="What's my name?",
            timestamp=1234567891000,
        )
    )

    response2 = await complete(model, context)
    print("Assistant:", response2.content[0].text)

asyncio.run(main())
```

## Error Handling

```python
import asyncio
from pi_ai.api import stream, get_model
from pi_ai.types import Context, UserMessage, StopReason

async def main():
    model = get_model("openai", "gpt-4o-mini")

    context = Context(
        systemPrompt="You are a helpful assistant.",
        messages=[
            UserMessage(
                role="user",
                content="Hello!",
                timestamp=1234567890000,
            )
        ],
    )

    try:
        event_stream = await stream(model, context)

        async for event in event_stream:
            if event["type"] == "error":
                print(f"Error occurred: {event['error'].errorMessage}")
                break

        result = await event_stream.result()

        if result.stopReason == StopReason.ERROR:
            print(f"Stream ended with error: {result.errorMessage}")
        else:
            print("Stream completed successfully")

    except Exception as e:
        print(f"Exception: {e}")

asyncio.run(main())
```

## Environment Variables

Set API keys in your environment:

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# Google
export GOOGLE_API_KEY="AIza..."
```

Or pass them explicitly:

```python
from pi_ai.types import StreamOptions

options = StreamOptions(api_key="your-api-key-here")
event_stream = await stream(model, context, options)
```

## Performance Tips

1. **Use streaming for real-time UX**: Stream events for progressive rendering
2. **Use complete() for simple cases**: When you just need the final result
3. **Reuse model configs**: Create model once, use for multiple requests
4. **Context management**: Keep contexts small to reduce token usage
5. **Provider selection**: Choose provider based on task (OpenAI for tools, Claude for reasoning, Gemini for large contexts)

## Next Steps

- See `tests/test_api_integration.py` for more examples
- Read provider-specific documentation for advanced features
- Check out the agent runtime in `pi-agent` package for stateful conversations

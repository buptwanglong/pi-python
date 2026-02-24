# pi-ai

Multi-provider LLM streaming library for Python.

Unified API for streaming responses from OpenAI, Anthropic Claude, Google Gemini, and 20+ other LLM providers.

## Features

- 🎯 **Unified API**: Single interface for all providers
- 🌊 **Streaming**: Real-time event streaming with async/await
- 🔧 **Tool Calling**: Standardized tool/function calling across providers
- 💭 **Thinking Blocks**: Support for reasoning/thinking content
- 📊 **Token Tracking**: Automatic usage and cost calculation
- 🔄 **Multi-Turn**: Conversation management with message history
- 🔌 **Provider Support**:
  - ✅ OpenAI (GPT-4, GPT-4o, GPT-4o-mini)
  - ✅ Anthropic (Claude 3.5, Claude 4)
  - ✅ Google (Gemini 2.0, Gemini Pro)
  - 🚧 AWS Bedrock, Azure OpenAI, Mistral, xAI, Groq, and more (coming soon)

## Installation

```bash
cd packages/pi-ai
poetry install

# Install provider SDKs (choose the ones you need)
poetry add openai          # For OpenAI
poetry add anthropic       # For Anthropic Claude
poetry add google-generativeai  # For Google Gemini
```

## Quick Start

### Basic Streaming

```python
import asyncio
from basket_ai.api import stream, get_model
from basket_ai.types import Context, UserMessage

async def main():
    # Create model and context
    model = get_model("openai", "gpt-4o-mini")
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

    async for event in event_stream:
        if event["type"] == "text_delta":
            print(event["delta"], end="", flush=True)

    # Get final result
    result = await event_stream.result()
    print(f"\n\nTokens: {result.usage.total_tokens}")

asyncio.run(main())
```

### Complete (Non-Streaming)

```python
from basket_ai.api import complete, get_model
from basket_ai.types import Context, UserMessage

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

    # Get complete response
    message = await complete(model, context)
    print(message.content[0].text)

asyncio.run(main())
```

## API Documentation

### Main Functions

#### `stream(model, context, options=None)`

Stream a response from an LLM.

**Parameters:**
- `model` (Model): Model configuration
- `context` (Context): Conversation context with messages and tools
- `options` (StreamOptions, optional): Streaming options (temperature, max_tokens, etc.)

**Returns:**
- `AssistantMessageEventStream`: Async event stream yielding events

#### `complete(model, context, options=None)`

Complete a request and return the final message (convenience wrapper around `stream()`).

**Returns:**
- `AssistantMessage`: Final message after streaming completes

#### `get_model(provider, model_id, **kwargs)`

Create a Model configuration with sensible defaults.

**Parameters:**
- `provider` (str): Provider name ("openai", "anthropic", "google")
- `model_id` (str): Model identifier
- `**kwargs`: Additional model parameters (name, reasoning, context_window, max_tokens, etc.)

**Returns:**
- `Model`: Model configuration

### Event Types

The streaming API emits these event types:

| Event Type | Description |
|------------|-------------|
| `start` | Stream started |
| `text_start` | Text block started |
| `text_delta` | Text content delta |
| `text_end` | Text block finished |
| `thinking_start` | Thinking block started |
| `thinking_delta` | Thinking content delta |
| `thinking_end` | Thinking block finished |
| `toolcall_start` | Tool call started |
| `toolcall_delta` | Tool arguments delta |
| `toolcall_end` | Tool call finished |
| `done` | Stream completed successfully |
| `error` | Error occurred |

### Provider Support

| Provider | Status | Models |
|----------|--------|--------|
| OpenAI | ✅ Complete | gpt-4, gpt-4o, gpt-4o-mini, etc. |
| Anthropic | ✅ Complete | claude-3-5-sonnet, claude-sonnet-4, etc. |
| Google | ✅ Complete | gemini-2.0-flash-exp, gemini-pro, etc. |
| AWS Bedrock | 🚧 Planned | - |
| Azure OpenAI | 🚧 Planned | - |
| Mistral | 🚧 Planned | - |
| xAI (Grok) | 🚧 Planned | - |
| Groq | 🚧 Planned | - |

## Examples

See [EXAMPLES.md](./EXAMPLES.md) for comprehensive usage examples including:
- Multi-provider usage
- Tool/function calling
- Multi-turn conversations
- Event handling
- Error handling
- Streaming options

## Environment Variables

Set API keys for the providers you use:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="AIza..."
```

Or pass them explicitly via `StreamOptions`:

```python
from basket_ai.types import StreamOptions

options = StreamOptions(api_key="your-key-here")
event_stream = await stream(model, context, options)
```

## Development

```bash
# Run tests (unit tests only, no API calls)
poetry run pytest tests/test_types.py tests/test_stream.py -v

# Run integration tests (requires API keys)
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="AIza..."
poetry run pytest tests/test_*_provider.py tests/test_api_integration.py -v

# Type checking
poetry run mypy basket_ai

# Format code
poetry run black basket_ai tests
poetry run ruff check basket_ai tests
```

## Architecture

```
basket_ai/
├── api.py                  # Unified API (stream, complete, get_model)
├── types.py                # Pydantic models (Context, Message, Tool, etc.)
├── stream.py               # Event streaming infrastructure
├── providers/
│   ├── base.py            # BaseProvider interface
│   ├── openai_completions.py   # OpenAI implementation
│   ├── anthropic.py       # Anthropic Claude implementation
│   ├── google.py          # Google Gemini implementation
│   └── utils.py           # Provider utilities
└── utils/
    ├── json_parsing.py    # Partial JSON parsing for streaming
    └── token_counting.py  # Token estimation utilities
```

## Testing

```bash
# Unit tests (fast, no API calls)
poetry run pytest tests/test_types.py tests/test_stream.py -v

# Integration tests (require API keys)
poetry run pytest tests/test_openai_provider.py -v  # Requires OPENAI_API_KEY
poetry run pytest tests/test_anthropic_provider.py -v  # Requires ANTHROPIC_API_KEY
poetry run pytest tests/test_google_provider.py -v  # Requires GOOGLE_API_KEY
poetry run pytest tests/test_api_integration.py -v  # Requires all API keys

# Run all tests
poetry run pytest -v
```

## License

MIT

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.

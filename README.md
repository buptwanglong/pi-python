# Basket-Python

Python implementation of [pi-mono](https://github.com/badlogic/pi-mono): A comprehensive AI agent framework with multi-provider LLM support.

## 🎯 Status: Phases 1-8 Complete!

**200+ tests** | **11 LLM providers** | **5 core tools** | **Extension system** | **Theme support**

Basket-Python is a production-ready rewrite of the TypeScript pi-mono project, providing:

- **Multi-provider LLM abstraction** - Unified API for 11+ providers (OpenAI, Anthropic, Google, Azure, Groq, Together, OpenRouter, Deepseek, Perplexity, Cerebras, xAI)
- **Agent runtime** - Stateful agent execution with tool calling and event streaming
- **Interactive coding agent** - CLI tool for AI-assisted coding with file operations and shell commands
- **Terminal UI framework** - Textual-based interactive interface with markdown rendering
- **Extension system** - Plugin architecture for custom tools, commands, and event handlers
- **Theme system** - Customizable color schemes for terminal UI

## Architecture

This is a monorepo with 6 core packages (+ 2 future applications):

```
basket-python/
├── packages/
│   ├── basket-ai/              # LLM abstraction layer ✅
│   ├── basket-agent/           # Agent runtime ✅
│   ├── basket-tui/             # Terminal UI ✅
│   ├── basket-trajectory/      # Task trajectory recording (RL/tuning) ✅
│   ├── basket-remote/          # Remote web terminal (ZeroTier/LAN) ✅
│   ├── basket-assistant/       # Interactive CLI agent ✅
│   ├── pi-mom/                 # Slack bot (future)
│   └── pi-pods/                # vLLM management (future)
```

## Requirements

- Python 3.12+
- Poetry (package manager)
- API keys for LLM providers (OpenAI, Anthropic, or Google)

## Installation

```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Clone the repository
git clone https://github.com/badlogic/pi-python.git
cd pi-python

# Install dependencies
poetry install

# Install a specific package
cd packages/basket-ai
poetry install
```

## Development Status

✅ **Phases 1-8 Complete** - Core functionality production-ready!

### Implementation Progress

- [x] **Phase 1**: Foundation (Core types & streaming)
- [x] **Phase 2**: Provider Layer (OpenAI, Anthropic, Google)
- [x] **Phase 3**: Agent Runtime (stateful execution loop)
- [x] **Phase 4**: Session Management (JSONL persistence)
- [x] **Phase 5**: Tools & CLI (Read, Write, Edit, Bash, Grep)
- [x] **Phase 6**: Terminal UI (Textual framework)
- [x] **Phase 7**: Additional Providers (11 total)
- [x] **Phase 8**: Extensions & Themes (plugin system)
- [ ] **Phase 9**: Applications (Mom/Pods - future work)

**Statistics:**
- 200+ tests
- 11 LLM providers
- 5 core tools
- 4 example extensions
- 2 built-in themes

See [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for detailed breakdown.

## Quick Start

### Using Basket

```bash
# Set API key
export ANTHROPIC_API_KEY=sk-ant-...

# Run interactive mode
cd packages/basket-assistant
poetry install
poetry run basket

# Or TUI mode (Textual-based UI)
poetry run basket --tui

# One-shot mode
poetry run basket "Create a hello.py file"
```

### Using basket-ai Library

```python
from basket_ai import get_model, stream
from basket_ai.types import Context, UserMessage

# Initialize a model
model = get_model("anthropic-messages", "claude-opus-4-20250514")

# Create context
context = Context(
    systemPrompt="You are a helpful assistant",
    messages=[UserMessage(role="user", content="Hello!")]
)

# Stream response
async for event in stream(model, context):
    if event["type"] == "text_delta":
        print(event["delta"], end="", flush=True)
```

### Creating Extensions

```python
"""my_extension.py"""
from pydantic import BaseModel, Field

class MyToolParams(BaseModel):
    text: str = Field(..., description="Input text")

def setup(basket):
    @basket.register_tool(
        name="my_tool",
        description="Process text",
        parameters=MyToolParams,
    )
    async def my_tool(text: str) -> str:
        return f"Processed: {text}"

    @basket.register_command("/mycmd")
    def my_command(args: str):
        print(f"Command: {args}")
```

Install to `~/.basket/extensions/` and the agent will load it automatically.

## Testing

```bash
# Run all tests (200+ tests)
cd packages/basket-assistant
poetry run pytest -v

# Run specific test categories
poetry run pytest tests/test_tools/ -v          # Tool tests
poetry run pytest tests/test_extensions.py -v   # Extension tests
poetry run pytest tests/test_theme.py -v        # Theme tests

# Run with coverage
poetry run pytest --cov=basket_assistant --cov-report=html tests/
```

**Test Coverage:**
- Tools: 32 tests (read, write, edit, bash, grep)
- Extensions: 18 tests (API, loader, integration)
- Themes: 11 tests (colors, manager, loading)
- Sessions: 9 tests (JSONL, metadata, trees)
- Settings: 13 tests (load, save, defaults)
- Messages: 14 tests (tree navigation)
- TUI: 13 tests (components, integration)

## Features

### LLM Providers (11 supported)
- ✅ OpenAI (GPT-4, GPT-3.5, o1, o3)
- ✅ Anthropic (Claude Opus, Sonnet, Haiku)
- ✅ Google (Gemini Pro, Flash, Nano)
- ✅ Azure OpenAI
- ✅ Groq (Llama, Mixtral)
- ✅ Together AI
- ✅ OpenRouter
- ✅ Deepseek
- ✅ Perplexity
- ✅ Cerebras
- ✅ xAI (Grok)

### Core Tools (5)
- **Read**: Read files with line numbers and offset/limit
- **Write**: Create or overwrite files
- **Edit**: Precise string replacement with diff support
- **Bash**: Execute shell commands with timeout
- **Grep**: Search code with regex and glob patterns

### Extension System
- Dynamic module loading
- Decorator-based API (`@basket.register_tool`, `@basket.register_command`, `@basket.on`)
- Event-driven architecture
- Auto-discovery from `~/.basket/extensions/` and `./extensions/`

### Theme System
- JSON-based theme files
- Variable references for DRY colors
- Built-in dark and light themes
- Load from `~/.basket/themes/`

### Terminal UI (TUI)
- Textual framework
- Real-time streaming
- Markdown rendering
- Syntax highlighting
- Code block display
- Multi-line input

## Comparison with TypeScript Version

| Feature | TypeScript | Python | Status |
|---------|-----------|--------|---------|
| Multi-provider LLM | ✅ 20+ | ✅ 11 | ✅ Core complete |
| Agent runtime | ✅ | ✅ | ✅ Complete |
| Tool calling | ✅ | ✅ | ✅ Complete |
| Session management | ✅ | ✅ | ✅ Complete |
| File operations | ✅ | ✅ | ✅ Complete |
| Terminal UI | ✅ Custom | ✅ Textual | ✅ Complete |
| Extensions | ✅ | ✅ | ✅ Complete |
| Themes | ✅ | ✅ | ✅ Complete |
| Slack bot (Mom) | ✅ | ⏸️ | 🔜 Future |
| vLLM manager (Pods) | ✅ | ⏸️ | 🔜 Future |

## Publishing to PyPI

To publish the five packages (basket-ai, basket-tui, basket-agent, basket-trajectory, basket-assistant) to PyPI, use the release script and follow [RELEASE.md](RELEASE.md). Summary: run `./scripts/publish-to-pypi.sh` to build, or `./scripts/publish-to-pypi.sh --upload` to build and upload (set `TWINE_USERNAME`/`TWINE_PASSWORD` or use a PyPI token).

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Summary:** Fork the repo, create a feature branch, add tests for new features, run `poetry run pytest -v`, and submit a pull request. Follow PEP 8, use type hints and docstrings.

## License

MIT License - same as [pi-mono](https://github.com/badlogic/pi-mono).

## Credits

This is a Python rewrite of the excellent [pi-mono](https://github.com/badlogic/pi-mono) TypeScript project by [Mario Zechner](https://github.com/badlogic).

## Resources

- [Original pi-mono repo](https://github.com/badlogic/pi-mono)
- [Pydantic documentation](https://docs.pydantic.dev/)
- [Textual documentation](https://textual.textualize.io/)
- [Poetry documentation](https://python-poetry.org/)

---

**Version**: 0.1.0 (Phases 1-8 complete)
**Python**: 3.12+
**Status**: Production-ready for coding assistant use cases

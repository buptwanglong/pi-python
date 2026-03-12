# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Basket-Python is a Python rewrite of the TypeScript pi-mono project. It's a comprehensive AI agent framework with multi-provider LLM support, organized as a Poetry monorepo with 6 core packages.

**Key Characteristics:**
- Python 3.12+ with strict type hints (Pydantic v2)
- AsyncIO-first architecture
- 200+ tests with pytest + pytest-asyncio
- Plugin-based extensibility (tools, agents, skills)

## Architecture

### Package Structure (Monorepo)

```
packages/
├── basket-ai/              # Multi-provider LLM abstraction (11 providers)
├── basket-agent/           # Agent runtime with tool calling
├── basket-tui/             # Textual-based terminal UI
├── basket-trajectory/      # Task trajectory recording
├── basket-remote/          # Remote web terminal (ZeroTier/LAN)
├── basket-gateway/         # Resident HTTP/WebSocket service
├── basket-memory/          # Memory management (optional)
├── basket-assistant/       # Main CLI application (depends on all above)
├── pi-mom/                 # Slack bot (future)
└── pi-pods/                # vLLM management (future)
```

**Dependency flow:** `basket-assistant` → `basket-agent` + `basket-tui` + `basket-gateway` → `basket-ai`

### Core Components

**basket-ai**: Unified streaming API over 11 LLM providers (OpenAI, Anthropic, Google, Azure, Groq, Together, OpenRouter, Deepseek, Perplexity, Cerebras, xAI). Event-based streaming with `stream()` and `complete()` functions. Supports tool calling, thinking blocks, token usage tracking.

**basket-agent**: Stateful agent execution loop. Registers tools via decorators, executes tool calls automatically, manages conversation context. Event-driven with `@basket.on("event_name")` handlers.

**basket-assistant**: Main CLI application. Five core tools (Read, Write, Edit, Bash, Grep) plus WebFetch and WebSearch. Session persistence in JSONL format. Supports interactive mode, TUI mode, one-shot mode, and remote access.

**basket-gateway**: Resident service for long-lived assistant. HTTP/WebSocket gateway on 127.0.0.1:7682. Managed via `basket gateway start/stop/status`.

**basket-tui**: Textual framework UI with markdown rendering, syntax highlighting, streaming display, and multi-line input.

## Development Commands

### Installation

```bash
# Root level (installs dev dependencies)
poetry install

# Individual package
cd packages/<package-name>
poetry install
```

### Running the Assistant

```bash
cd packages/basket-assistant

# Interactive REPL mode
poetry run basket

# Terminal UI mode
poetry run basket tui

# TUI with specific agent
poetry run basket tui --agent <agent-name>

# One-shot mode
poetry run basket "Your message here"

# Remote access (requires basket-remote)
poetry run basket --remote --bind <IP> --port 7681
```

### Testing

```bash
# Run all tests in a package
cd packages/<package-name>
poetry run pytest -v

# Run specific test file or category
poetry run pytest tests/test_tools/ -v
poetry run pytest tests/test_extensions.py -v

# Run with coverage
poetry run pytest --cov=basket_ai --cov-report=html tests/

# From root (runs all package tests)
poetry run pytest -v
```

**Test organization:**
- `packages/basket-ai/tests/` - Provider tests, streaming, types
- `packages/basket-agent/tests/` - Agent loop, tools, events
- `packages/basket-assistant/tests/` - CLI, tools, extensions, sessions
- `conftest.py` in each test directory provides fixtures

### Code Quality

```bash
# Type checking (mypy configured in pyproject.toml)
cd packages/<package-name>
poetry run mypy .

# Code formatting (Black, line-length 100)
poetry run black .

# Linting (Ruff)
poetry run ruff check .
```

### Publishing

```bash
# Build all packages (dry run)
./scripts/publish-to-pypi.sh

# Build and upload to PyPI (requires TWINE_USERNAME/TWINE_PASSWORD)
./scripts/publish-to-pypi.sh --upload
```

## Configuration

### Settings File

Location: `~/.basket/settings.json`

**First-time setup:**
```bash
cd packages/basket-assistant
poetry run basket init          # Guided configuration
poetry run basket init --force  # Overwrite existing
```

### Key Configuration Areas

**Model configuration:**
- `model.provider`: openai, anthropic, or google
- `model.model_id`: Specific model (e.g., "claude-sonnet-4-20250514")
- `model.base_url`: Custom/internal API endpoint (optional)
- `model.context_window`: Token limit for context

**API Keys:**
- In `api_keys` object or environment variables
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`
- `SERPER_API_KEY` (optional, for web search)

**Agent behavior:**
- `agent.max_turns`: Maximum tool execution rounds
- `agent.auto_save`: Auto-save sessions
- `agent.verbose`: Debug output

**Workspace:**
- `workspace_dir`: OpenClaw-style markdown files (IDENTITY.md, AGENTS.md, etc.)
- Default: `~/.basket/workspace` (auto-created with templates)

**Skills:**
- `skills_dirs`: Search paths for skills (SKILL.md format)
- Default paths: `~/.basket/skills`, `~/.claude/skills`, `~/.config/opencode/skills`

**SubAgents:**
- `agents`: Dictionary of named subagent configurations
- `default_agent`: Main agent name (optional)
- Each agent can have its own model, workspace, tools

## Key Patterns

### Tool Registration

Tools use Pydantic models for parameters:

```python
from pydantic import BaseModel, Field

class MyToolParams(BaseModel):
    text: str = Field(..., description="Input text")

@basket.register_tool(
    name="my_tool",
    description="Process text",
    parameters=MyToolParams
)
async def my_tool(text: str) -> str:
    return f"Processed: {text}"
```

### Event Handling

```python
@basket.on("tool_call_started")
async def on_tool_call(event: dict):
    print(f"Tool called: {event['tool_name']}")
```

### Session Management

Sessions stored as JSONL in `~/.basket/sessions/`. Each line is a JSON object (message or metadata). Tree structure supports branching conversations.

### Extension System

Extensions placed in `~/.basket/extensions/` or `./extensions/`. Must have a `setup(basket)` function. Supports tool registration, command registration (`@basket.register_command`), and event handlers.

### Skills System

OpenCode/Claude-compatible skill layout:
- One directory per skill (name matches `^[a-z0-9]+(-[a-z0-9]+)*$`)
- `SKILL.md` inside with YAML frontmatter (name, description)
- Agent gets `skill` tool to load skill content on-demand
- Interactive: `/skill <id> [message]`

### SubAgent Delegation

When subagents configured, main agent gets `task` tool:
```python
await task(
    subagent_type="explore",
    prompt="Find all API endpoints",
    description="Exploring codebase"
)
```

## Important Constraints

### Immutability

**ALWAYS** create new objects, never mutate existing ones. Pydantic models are immutable by default (use `model_copy(update={...})` to create modified copies).

### Type Safety

All functions require type hints. Use Pydantic models for complex types. Enable mypy strict mode in `pyproject.toml`.

### Async First

All I/O operations must be async (use `aiofiles`, `httpx`, etc.). Agent tools are async coroutines.

### File Size

Keep modules under 800 lines. Extract utilities and separate concerns into multiple files.

## Testing Requirements

- Minimum 80% coverage for new code
- Use pytest fixtures in `conftest.py`
- Mock external API calls with `pytest-httpx`
- Mark async tests with `@pytest.mark.asyncio` (or use `asyncio_mode = "auto"`)

## Troubleshooting

**Import errors:** Ensure packages installed with `develop = true` in pyproject.toml. Run `poetry install` in each package directory.

**Test failures:** Check venv activation and editable installs. Use `poetry run pytest` not `pytest` directly.

**Provider errors:** Verify API keys in environment or `~/.basket/settings.json`. Check `model.base_url` for custom endpoints.

**Gateway not starting:** Check if port 7682 is available. Use `BASKET_SERVE_PORT` to override.

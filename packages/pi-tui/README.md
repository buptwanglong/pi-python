# Pi TUI

Terminal UI framework for Pi Coding Agent, built with [Textual](https://github.com/Textualize/textual).

## Features

- 🎨 **Rich Terminal UI** - Beautiful, interactive interface with Markdown rendering
- 🔄 **Real-time Streaming** - Display LLM responses as they arrive
- 🛠️ **Tool Visualization** - Show tool calls and results inline
- 🎭 **Theming** - Light/dark mode with CSS styling
- ⌨️ **Keyboard Shortcuts** - Efficient navigation and control

## Installation

```bash
poetry install
```

## Usage

### Standalone

Run the TUI app directly:

```python
from pi_tui import PiCodingAgentApp

app = PiCodingAgentApp()
app.run()
```

### With Agent

Integrate with Pi Agent:

```python
from pi_tui import PiCodingAgentApp
from pi_agent import Agent

agent = Agent(...)
app = PiCodingAgentApp(agent=agent)

# Connect agent events
agent.on("text_delta", lambda e: app.append_text(e["delta"]))
agent.on("thinking_delta", lambda e: app.append_thinking(e["delta"]))
agent.on("agent_tool_call_start", lambda e: app.show_tool_call(e["tool_name"]))

app.run()
```

## Keyboard Shortcuts

- `Ctrl+C` - Quit
- `Ctrl+L` - Clear output
- `Ctrl+D` - Toggle dark/light mode

## Development

Run tests:

```bash
poetry run pytest tests/ -v
```

## Architecture

The TUI is built with Textual, a modern Python TUI framework:

- `app.py` - Main application class
- `components/streaming_log.py` - Custom log widget for streaming content
- Future components: Markdown viewer, code blocks, autocomplete input

## License

MIT

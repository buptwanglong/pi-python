# Basket TUI

Terminal-native TUI for Basket: line-by-line output with [prompt_toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit) input. Connects to the basket-gateway WebSocket.

## Features

- **Line output** – Assistant and tool output printed as lines (no full-screen Textual UI)
- **prompt_toolkit input** – Single-line input with history
- **Slash commands** – `/help`, `/new`, `/abort`, `/session`, `/agent`, `/model`
- **Pickers** – Ctrl+P (session), Ctrl+G (agent), Ctrl+L (model)

## Installation

```bash
poetry install
```

## Usage

Typically used via the Basket CLI (gateway + native TUI):

```bash
basket tui          # same as tui-native
basket tui-native   # or short: basket tn
```

Programmatic:

```python
from basket_tui import run_tui_native_attach

# Connect to gateway WebSocket and run the native TUI
await run_tui_native_attach("ws://127.0.0.1:7682/ws", agent_name="default", max_cols=120)
```

## Development

The TUI runs in a single asyncio event loop: WebSocket and prompt_toolkit share the same loop; no threads or `queue.Queue`. Output is pushed via an `output_put` callback (append to body + invalidate).

Run tests:

```bash
poetry run pytest tests/native/ -v
```

## License

MIT

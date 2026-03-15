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

## Debugging with Logs

Enable debug logging to trace message flow, user interactions, and system behavior.

**Log output location**: `~/.basket/logs/basket.log` (auto-rotated, 10MB max, 5 backups)

### Configuration Priority

Log level is determined by (in priority order):
1. **`BASKET_LOG_LEVEL`** environment variable (global for all basket modules)
2. **`BASKET_TUI_LOG_LEVEL`** environment variable (TUI-specific, backward compatibility)
3. **`log_level`** field in `~/.basket/settings.json`
4. **Default**: INFO

### Using Environment Variables

```bash
# Global log level (affects all basket modules)
export BASKET_LOG_LEVEL=DEBUG
basket tui

# TUI-specific log level (backward compatible)
export BASKET_TUI_LOG_LEVEL=DEBUG
basket tui
```

### Using settings.json

Add to your `~/.basket/settings.json`:
```json
{
  "log_level": "DEBUG",
  "model": { ... },
  ...
}
```

### Viewing Logs

```bash
# Real-time log viewing
tail -f ~/.basket/logs/basket.log

# View last 100 lines
tail -n 100 ~/.basket/logs/basket.log

# Search for specific content
grep "ERROR" ~/.basket/logs/basket.log
```

### Log Levels

- **DEBUG**: Detailed data flow (message parsing, delta accumulation, buffer states)
- **INFO**: Key events (connections, phase transitions, user actions, tool calls)
- **WARNING**: Recoverable issues (JSON parse errors, reconnections)
- **ERROR**: Errors (handler failures, tool errors, connection failures)

### Common Debugging Scenarios

**Trace complete message flow:**
```bash
export BASKET_LOG_LEVEL=DEBUG
basket tui &
tail -f ~/.basket/logs/basket.log | grep -E "(User input|Text delta|Agent complete)"
```

**Debug connection issues:**
```bash
export BASKET_LOG_LEVEL=INFO
basket tui &
tail -f ~/.basket/logs/basket.log | grep -E "(WebSocket|Connection)"
```

**Monitor tool execution:**
```bash
export BASKET_LOG_LEVEL=INFO
basket tui &
tail -f ~/.basket/logs/basket.log | grep -E "(Tool call|phase)"
```

### Log Format

All logs follow this format:
```
[YYYY-MM-DD HH:MM:SS] [LEVEL   ] [module:line] message
```

Example output:
```
[2026-03-15 10:30:45] [INFO    ] [run:26] TUI starting
[2026-03-15 10:30:45] [INFO    ] [client:120] WebSocket connected
[2026-03-15 10:30:45] [INFO    ] [run:98] Connection ready
[2026-03-15 10:30:50] [INFO    ] [input_handler:118] User input received
[2026-03-15 10:30:50] [INFO    ] [client:175] Sending message
[2026-03-15 10:30:51] [DEBUG   ] [client:136] Raw message received
[2026-03-15 10:30:51] [DEBUG   ] [dispatch:40] Text delta processed
[2026-03-15 10:30:52] [INFO    ] [dispatch:93] Agent turn complete
```

For detailed logging documentation, see [LOGGING.md](LOGGING.md).

## License

MIT

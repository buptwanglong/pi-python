# Basket

Interactive CLI personal assistant with tool execution capabilities.

## Features

- 🛠️ **Built-in Tools**: Read, Write, Edit, Bash, Grep
- 🤖 **Agent Runtime**: Powered by basket-agent
- 📡 **Multi-Provider**: Supports OpenAI, Anthropic, Google via basket-ai
- 💾 **Session Persistence**: JSONL-based session management
- 🌳 **Session Trees**: Branching conversations

## Installation

```bash
cd packages/basket-assistant
poetry install
```

## Usage

- `basket` — interactive mode
- `basket --tui` — terminal UI
- `basket --remote` — remote web terminal (for phone/LAN access; see below)
- `basket "message"` — one-shot

## Resident assistant (gateway)

Run the assistant as a long-lived local service and attach with the TUI when needed. The assistant keeps running after you exit the TUI.

| Command | Description |
|---------|-------------|
| `basket serve start` | Start the resident assistant (HTTP/WebSocket gateway on 127.0.0.1). Runs in foreground; use `nohup basket serve start &` or systemd for background. |
| `basket serve stop` | Stop the assistant (sends SIGTERM to the gateway process). |
| `basket serve status` | Show whether the assistant is running (pid, port, uptime). |
| `basket serve attach` | Open the TUI connected to the running assistant. Exiting the TUI disconnects; the assistant keeps running. |

Port defaults to **7682**; set `BASKET_SERVE_PORT` to override. State files: `~/.basket/serve.pid`, `~/.basket/serve.port`. Attach uses `ws://127.0.0.1:<port>/ws` by default, or pass `--url ws://...` to `basket serve attach`.

## Remote access (ZeroTier)

Use the agent from your phone or another machine over ZeroTier or LAN:

1. Install [ZeroTier](https://www.zerotier.com/) on your computer and phone; create a network and join both devices.
2. Install **ttyd** on the computer (e.g. `brew install ttyd` on macOS).
3. Install the optional basket-remote dependency and run:

   ```bash
   poetry add basket-remote
   poetry run basket --remote --bind <your.ZeroTier.IP> --port 7681
   ```

4. On your phone (on the same ZeroTier network), open a browser and go to `http://<your.ZeroTier.IP>:7681`. You get a web terminal running the TUI.

You can use `BASKET_REMOTE_BIND` and `BASKET_REMOTE_PORT` instead of `--bind` / `--port`. Alternative: use Termux on Android and SSH to the computer's ZeroTier IP, then run `basket --tui` in the SSH session.

## Tools

### Read
Read files with line number ranges.

### Write
Write files with automatic parent directory creation.

### Edit
Edit files using exact string replacement.

### Bash
Execute shell commands with timeout support.

### Grep
Search for patterns in files using regex.

## Skills

Skills are instruction documents (Markdown) that the agent can use for a single turn. The main prompt only includes a short **index** (name + description); when you invoke a skill with `/skill <id>`, the full content is injected for that turn only.

- **Directories**: `~/.basket/skills/` and `./.basket/skills/` (project overrides user for same id).
- **Files**: One skill per file, `{id}.md` (e.g. `refactor.md`). Optional YAML frontmatter with `description: ...` for the index; the rest is the full instruction body.
- **Usage**: In interactive mode, type `/skill refactor` or `/skill refactor your request here`. The agent will see the full skill content for that turn and use the existing tools to follow it.

Optional settings in `~/.basket/settings.json`: `skills_dirs` (list of paths), `skills_include` (list of skill ids to load; empty = all).

## License

MIT

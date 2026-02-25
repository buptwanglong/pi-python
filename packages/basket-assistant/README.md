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

OpenCode/Claude-style layout: **one directory per skill with `SKILL.md` inside**. Same directories work with OpenCode and Claude Code.

- **Layout**: Create a subdirectory per skill (e.g. `git-release`); put `SKILL.md` inside. `SKILL.md` must have YAML frontmatter: `name` (matches directory name), `description` (1–1024 chars). Optional: `metadata`, `compatibility`, `license`. Name must match `^[a-z0-9]+(-[a-z0-9]+)*$`, length 1–64.
- **Default search paths** (when not configured): Basket (`~/.basket/skills`, `./.basket/skills`), OpenCode (`~/.config/opencode/skills`, `./.opencode/skills`), Claude (`~/.claude/skills`, `./.claude/skills`), Agents (`~/.agents/skills`, `./.agents/skills`). Later path wins for the same skill name.
- **Discovery and loading**: The agent has a `skill` tool; its description lists available skills in `<available_skills>`. Call the tool with a skill name to load the full content (returned as tool result). You can also type `/skill <id> [message]` in interactive mode to force that skill for the current turn.
- **Settings** in `~/.basket/settings.json`: `skills_dirs` (list of paths; when set, only these are used), `skills_include` (list of skill names to load; empty = all).

## SubAgents and Task tool

You can configure **subagents** (e.g. general-purpose, explore) and let the main agent delegate work via the **task** tool. The subagent runs in its own context with its own prompt and (optionally) tool set, then returns a single result.

- **Config**: `agents` in `~/.basket/settings.json` and/or `.basket/agents/*.md` files (YAML frontmatter + body as prompt). Same name in a later source overrides the earlier.
- **Task tool**: When at least one subagent is configured, the main agent gets a `task` tool; call it with `subagent_type`, `prompt`, and `description`. See [CONFIG.md](CONFIG.md) for `SubAgentConfig` fields and `.basket/agents` layout.

## License

MIT

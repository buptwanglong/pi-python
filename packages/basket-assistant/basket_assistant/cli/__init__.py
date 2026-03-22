"""Basket CLI — entry-point routing and logging setup.

This subpackage is the command router for the ``basket`` CLI. It delegates
to focused command modules after parsing arguments and configuring logging.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from .parser import ParsedArgs, parse_args

logger = logging.getLogger(__name__)

# Help text displayed for ``basket --help`` / ``basket -h``.
_HELP_TEXT = """\
Basket - AI-powered personal assistant

Usage:
  basket                 - Start interactive mode
  basket tui [--agent <name>] - Start TUI (optionally with specified main agent)
  basket tui-native | basket tn - Start terminal-native TUI (line output, selectable/copyable; same gateway as 'basket tui')
  basket --session <id> - Start with session loaded (use with interactive or tui)
  basket --remote        - Start remote web terminal (requires basket-remote, ttyd; use with ZeroTier)
  basket "message"       - Run once with a message
  basket --plan          - Run in plan mode (read-only; same as --permission-mode plan)
  basket gateway start   - Start resident assistant (gateway)
  basket gateway stop    - Stop resident assistant
  basket gateway status  - Show assistant status
  basket relay [url]      - Connect to relay (outbound only); url from settings.json relay_url or arg
  basket init             - Guided setup (create or overwrite settings.json)
  basket agent list|add|remove - Manage subagents (Task tool)
  basket --help          - Show this help
  basket --version       - Show version
  basket --debug         - Enable DEBUG logging (to log file only)

  --agent <name>  - Use with 'basket', 'basket tui', or 'basket tui-native' to select main agent from settings.agents

Interactive mode commands:
  help      - Show help
  settings  - Show settings
  exit/quit - Exit

Environment variables:
  OPENAI_API_KEY        - OpenAI API key
  ANTHROPIC_API_KEY     - Anthropic API key
  GOOGLE_API_KEY        - Google API key
  LOG_LEVEL             - Log level (e.g. DEBUG); overridden by --debug
  BASKET_REMOTE_BIND    - Bind address for --remote (default: 0.0.0.0)
  BASKET_REMOTE_PORT    - Port for --remote (default: 7681)
  BASKET_SERVE_PORT     - Port for resident assistant (default: 7682)
"""


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def _setup_logging(parsed: ParsedArgs) -> None:
    """Configure file-based logging (mirrors original ``main_async`` logic)."""
    fmt = "%(asctime)s %(name)s: %(levelname)s: %(message)s"
    log_level_name = (os.environ.get("LOG_LEVEL") or "").upper()
    level = logging.INFO
    if parsed.debug:
        level = logging.DEBUG
    elif log_level_name:
        level = getattr(logging, log_level_name, level) or level

    log_dir = Path.home() / ".basket" / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "basket.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(fmt))
        root = logging.getLogger()
        root.setLevel(level)
        root.addHandler(file_handler)
        for name in ("basket_tui", "basket_assistant.interaction.modes.tui"):
            logging.getLogger(name).setLevel(level)
        logging.getLogger("anthropic._base_client").setLevel(logging.INFO)
        logger.info("Log file: %s", log_file)
    except OSError as e:
        logger.debug("Could not create log file: %s", e)


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------


async def main_async(args: Optional[list[str]] = None) -> int:
    """Async entry point — parse args, set up logging, route to command."""
    parsed = parse_args(args)
    _setup_logging(parsed)

    # -- trivial commands (no imports needed) --------------------------------
    if parsed.command == "help":
        print(_HELP_TEXT)
        return 0

    if parsed.command == "version":
        print("Basket v0.1.0")
        return 0

    # -- lazy-import command modules -----------------------------------------
    from . import config_cmd, agent_cmd, gateway_cmd, remote_cmd, relay_cmd, run_cmd

    match parsed.command:
        case "init":
            return await config_cmd.run(parsed)
        case "agent":
            return await agent_cmd.run(parsed)
        case "gateway":
            return await gateway_cmd.run(parsed)
        case "remote":
            return await remote_cmd.run(parsed)
        case "relay":
            return await relay_cmd.run(parsed)
        case "tui" | "tui-native":
            return await run_cmd.run_tui(parsed)
        case "interactive":
            return await run_cmd.run_interactive(parsed)
        case "once":
            return await run_cmd.run_once(parsed)
        case _:
            print(_HELP_TEXT)
            return 1


def main() -> int:
    """Synchronous entry point (called by ``pyproject.toml`` script)."""
    return asyncio.run(main_async())

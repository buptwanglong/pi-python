"""
Slash commands for terminal-native TUI.

Parse and handle /help, /exit, /session, /agent, /model, /new, /abort, /settings.
"""

from typing import Literal, Optional

# Commands that are implemented or stubbed; used for /help and routing.
HELP_LINES = [
    "[system] Commands:",
    "  /help     - show this help",
    "  /exit     - exit",
    "  /session  - switch session",
    "  /agent    - switch agent",
    "  /model    - switch model",
    "  /new      - new session",
    "  /abort    - abort current turn",
    "  /settings - open settings",
    "",
]

# Return: "exit" = caller should exit; "handled" = printed something, don't send; None = not a slash command.
SlashResult = Optional[Literal["exit", "handled"]]


def handle_slash_command(text: str) -> SlashResult:
    """
    If input is a slash command, handle it (print to stdout) and return status.
    Return "exit" for /exit, "handled" for other handled commands, None if not a slash command.
    """
    t = (text or "").strip()
    if not t.startswith("/"):
        return None
    parts = t.split(maxsplit=1)
    cmd = (parts[0] or "").lower()
    if not cmd:
        return None

    if cmd == "/help":
        for line in HELP_LINES:
            print(line, flush=True)
        return "handled"
    if cmd == "/exit":
        return "exit"
    # Unknown slash command
    print("[system] Unknown command. Type /help for commands.", flush=True)
    return "handled"

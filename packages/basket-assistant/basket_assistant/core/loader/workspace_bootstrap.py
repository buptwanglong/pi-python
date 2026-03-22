"""
Load agent workspace identity files (AGENTS.md, IDENTITY.md, SOUL.md, USER.md).

Used to compose the base system prompt when workspace_dir is set.
Workspace is required: when not configured, default path is used and default-filled.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from ..settings import Settings

logger = logging.getLogger(__name__)

DEFAULT_WORKSPACE_DIR = "~/.basket/workspace"

WORKSPACE_FILES = [
    ("identity", "IDENTITY.md"),
    ("soul", "SOUL.md"),
    ("agents", "AGENTS.md"),
    ("user", "USER.md"),
    ("tools", "TOOLS.md"),
    ("memory", "MEMORY.md"),
]

# Optional OpenClaw-style files (loaded if present)
WORKSPACE_FILES_OPTIONAL = [
    ("bootstrap", "BOOTSTRAP.md"),
    ("boot", "BOOT.md"),
    ("heartbeat", "HEARTBEAT.md"),
]

DEFAULT_AGENTS_MD = "You are a helpful assistant.\n"
DEFAULT_IDENTITY_MD = "Name: Assistant.\n"

# OpenClaw-style first-run ritual; agent fills USER.md, IDENTITY.md, SOUL.md then deletes this file
DEFAULT_BOOTSTRAP_MD = """# BOOTSTRAP.md — First run

You just woke up. Time to figure out who you are.

There is no memory yet. This is a fresh workspace.

## The conversation

Don't interrogate. Just talk. Start with something like:

> "Hey. I just came online. Who am I? Who are you?"

Then figure out together:

1. Your emoji — a signature
2. Your vibe — formal, casual, warm, etc.
3. Your nature — what kind of creature you are
4. Your name — what they should call you

## After you know who you are

Update these files with what you learned:

- `USER.md` — their name, how to address them, timezone, notes
- `IDENTITY.md` — your name, creature, vibe, emoji
- `SOUL.md` — boundaries, how they want you to behave, what matters to them

## When you're done

Delete this file. You don't need a bootstrap script anymore.
"""


def ensure_workspace_default_fill(workspace_dir: Path) -> None:
    """
    Ensure workspace has minimal template files so prompt assembly never gets empty.
    Creates directory if missing; writes AGENTS.md, IDENTITY.md, and BOOTSTRAP.md (OpenClaw-style) if missing.
    """
    workspace_dir = workspace_dir.expanduser().resolve()
    workspace_dir.mkdir(parents=True, exist_ok=True)
    if not (workspace_dir / "AGENTS.md").exists() or (workspace_dir / "AGENTS.md").read_text(encoding="utf-8").strip() == "":
        (workspace_dir / "AGENTS.md").write_text(DEFAULT_AGENTS_MD, encoding="utf-8")
        logger.debug("Wrote default AGENTS.md at %s", workspace_dir)
    if not (workspace_dir / "IDENTITY.md").exists() or (workspace_dir / "IDENTITY.md").read_text(encoding="utf-8").strip() == "":
        (workspace_dir / "IDENTITY.md").write_text(DEFAULT_IDENTITY_MD, encoding="utf-8")
        logger.debug("Wrote default IDENTITY.md at %s", workspace_dir)
    if not (workspace_dir / "BOOTSTRAP.md").exists() or (workspace_dir / "BOOTSTRAP.md").read_text(encoding="utf-8").strip() == "":
        (workspace_dir / "BOOTSTRAP.md").write_text(DEFAULT_BOOTSTRAP_MD.strip() + "\n", encoding="utf-8")
        logger.debug("Wrote default BOOTSTRAP.md at %s", workspace_dir)
    (workspace_dir / "memory").mkdir(exist_ok=True)


def resolve_workspace_dir(settings: Settings, for_main_agent: bool = True) -> Optional[Path]:
    """
    Resolve workspace directory from settings.

    When workspace_dir is not set or empty, uses default path ~/.basket/workspace (main agent).
    If the path does not exist, creates it and runs ensure_workspace_default_fill.
    Returns None only when skip_bootstrap is True and caller should not load workspace content
    (path can still be resolved for other uses). For backward compatibility we still return
    a path when using default so that prompt assembly always has a workspace.
    """
    raw = settings.workspace_dir
    if not raw or not str(raw).strip():
        path = Path(DEFAULT_WORKSPACE_DIR).expanduser().resolve()
    else:
        path = Path(str(raw).strip()).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        path.mkdir(parents=True, exist_ok=True)
        logger.debug("Created workspace dir: %s", path)
    ensure_workspace_default_fill(path)
    return path


def load_workspace_sections(
    workspace_dir: Path,
    skip_bootstrap: bool = False,
) -> Dict[str, str]:
    """
    Load workspace identity files into a dict of section name -> content.

    Loads WORKSPACE_FILES and optional WORKSPACE_FILES_OPTIONAL (BOOTSTRAP, BOOT, HEARTBEAT).
    Only includes keys for files that exist and have content.
    Missing files are omitted (no placeholder). UTF-8 encoding.
    """
    if skip_bootstrap:
        return {}
    result: Dict[str, str] = {}
    for key, filename in WORKSPACE_FILES + WORKSPACE_FILES_OPTIONAL:
        path = workspace_dir / filename
        if not path.exists() or not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8").strip()
            if content:
                result[key] = content
        except Exception as e:
            logger.warning("Failed to read workspace file %s: %s", path, e)
    return result


def load_daily_memory(workspace_dir: Path, today: Optional[Any] = None, yesterday: Optional[Any] = None) -> str:
    """
    Load memory/YYYY-MM-DD.md for today and yesterday; return concatenated content.
    today/yesterday can be date objects or None (then we use datetime.date.today()).
    """
    from datetime import date, timedelta
    if today is None:
        today = date.today()
    if yesterday is None:
        yesterday = today - timedelta(days=1)
    memory_dir = workspace_dir / "memory"
    if not memory_dir.exists() or not memory_dir.is_dir():
        return ""
    parts = []
    for d in (yesterday, today):
        path = memory_dir / f"{d.isoformat()}.md"
        if path.exists() and path.is_file():
            try:
                content = path.read_text(encoding="utf-8").strip()
                if content:
                    parts.append(f"## {d.isoformat()}\n\n{content}")
            except Exception as e:
                logger.warning("Failed to read daily memory %s: %s", path, e)
    return "\n\n".join(parts) if parts else ""

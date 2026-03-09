"""
Load agent workspace identity files (AGENTS.md, IDENTITY.md, SOUL.md, USER.md).

Used to compose the base system prompt when workspace_dir is set.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

WORKSPACE_FILES = [
    ("identity", "IDENTITY.md"),
    ("soul", "SOUL.md"),
    ("agents", "AGENTS.md"),
    ("user", "USER.md"),
    ("tools", "TOOLS.md"),
    ("memory", "MEMORY.md"),
]


def resolve_workspace_dir(settings: Any) -> Optional[Path]:
    """
    Resolve workspace directory from settings.

    Returns None if workspace_dir is not set, empty, or the path does not exist.
    """
    raw = getattr(settings, "workspace_dir", None)
    if not raw or not str(raw).strip():
        return None
    path = Path(str(raw).strip()).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        logger.debug("Workspace dir not found or not a directory: %s", path)
        return None
    return path


def load_workspace_sections(
    workspace_dir: Path,
    skip_bootstrap: bool = False,
) -> Dict[str, str]:
    """
    Load workspace identity files into a dict of section name -> content.

    Only includes keys for files that exist and have content.
    Missing files are omitted (no placeholder). UTF-8 encoding.
    """
    if skip_bootstrap:
        return {}
    result: Dict[str, str] = {}
    for key, filename in WORKSPACE_FILES:
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

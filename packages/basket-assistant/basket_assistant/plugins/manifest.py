"""Plugin manifest parsing and directory validation.

A Plugin is a directory containing an optional plugin.json manifest plus
any combination of skills/, hooks.json, extensions/, and agents/ sub-dirs.
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


@dataclass(frozen=True)
class PluginManifest:
    """Parsed plugin.json manifest (immutable)."""

    name: str
    version: str = "0.0.0"
    description: str = ""
    author: str = ""


def _sanitize_name(raw: str) -> Optional[str]:
    """Return raw if it matches the naming convention, else None."""
    if _NAME_RE.match(raw) and len(raw) <= 64:
        return raw
    return None


def load_plugin_manifest(plugin_dir: Path) -> PluginManifest:
    """Load plugin.json from a plugin directory.

    Falls back to directory name when plugin.json is missing or invalid.
    """
    fallback_name = _sanitize_name(plugin_dir.name) or plugin_dir.name.lower().replace(" ", "-")
    fallback = PluginManifest(name=fallback_name)

    manifest_path = plugin_dir / "plugin.json"
    if not manifest_path.exists():
        return fallback

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to parse plugin.json in %s: %s", plugin_dir, e)
        return fallback

    if not isinstance(data, dict):
        return fallback

    raw_name = data.get("name", "")
    name = _sanitize_name(str(raw_name)) if raw_name else None
    if not name:
        name = fallback_name

    return PluginManifest(
        name=name,
        version=str(data.get("version", "0.0.0")),
        description=str(data.get("description", "")),
        author=str(data.get("author", "")),
    )


def validate_plugin_dir(plugin_dir: Path) -> List[str]:
    """Validate a plugin directory structure.

    Returns a list of error messages (empty = valid).
    A valid plugin must contain at least one of:
    skills/, hooks.json, extensions/, agents/
    """
    errors: List[str] = []

    has_content = False

    skills_dir = plugin_dir / "skills"
    if skills_dir.is_dir() and any(skills_dir.iterdir()):
        has_content = True

    hooks_file = plugin_dir / "hooks.json"
    if hooks_file.is_file():
        has_content = True

    extensions_dir = plugin_dir / "extensions"
    if extensions_dir.is_dir() and any(extensions_dir.iterdir()):
        has_content = True

    agents_dir = plugin_dir / "agents"
    if agents_dir.is_dir() and any(agents_dir.iterdir()):
        has_content = True

    if not has_content:
        errors.append(
            "Plugin has no content: expected at least one of "
            "skills/, hooks.json, extensions/, agents/"
        )

    return errors

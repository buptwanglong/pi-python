"""
Declarative slash commands: flat `*.md` files with YAML frontmatter + body template.

Scan order is defined by callers (typically ~/.basket/commands, then cwd/.basket/commands,
then plugin commands/); later directories overwrite earlier for the same command name.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_NAME_MAX_LEN = 64
_DESCRIPTION_MAX_LEN = 1024


@dataclass(frozen=True)
class SlashCommandSpec:
    """A loaded declarative slash command (stem of file = command name without leading /)."""

    name: str
    description: str
    body_template: str
    skill_id: Optional[str]
    disable_model_invocation: bool
    source_path: Path


def _parse_bool_line(value: str) -> Optional[bool]:
    v = value.strip().lower()
    if v in ("true", "yes", "1", "on"):
        return True
    if v in ("false", "no", "0", "off"):
        return False
    return None


def _parse_slash_frontmatter(
    raw: str,
) -> tuple[Optional[str], Optional[str], Optional[str], bool, str]:
    """
    Parse --- frontmatter for slash commands.

    Returns (description, skill_id, error_reason_if_skip, disable_model_invocation, body).
    If frontmatter invalid or missing required fields, description is None and error has reason.
    """
    text = raw.strip()
    if not text.startswith("---"):
        return None, None, "missing opening ---", True, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, None, "unclosed frontmatter", True, text
    fm, body = parts[1].strip(), parts[2].strip()
    description: Optional[str] = None
    skill_id: Optional[str] = None
    disable_model_invocation = True

    for line in fm.splitlines():
        m = re.match(r"description\s*:\s*(.+)", line, re.IGNORECASE)
        if m:
            description = m.group(1).strip().strip("'\"").strip()
            continue
        m = re.match(r"skill\s*:\s*(.+)", line, re.IGNORECASE)
        if m:
            skill_id = m.group(1).strip().strip("'\"").strip()
            continue
        m = re.match(r"disable-model-invocation\s*:\s*(.+)", line, re.IGNORECASE)
        if m:
            parsed = _parse_bool_line(m.group(1))
            if parsed is not None:
                disable_model_invocation = parsed
            continue

    if not description:
        return None, None, "missing required frontmatter 'description'", disable_model_invocation, body
    if len(description) > _DESCRIPTION_MAX_LEN:
        return (
            None,
            None,
            f"description longer than {_DESCRIPTION_MAX_LEN} chars",
            disable_model_invocation,
            body,
        )

    if skill_id is not None and skill_id != "":
        if not _NAME_RE.match(skill_id) or len(skill_id) > _NAME_MAX_LEN:
            return (
                None,
                None,
                f"invalid skill id {skill_id!r}",
                disable_model_invocation,
                body,
            )
    else:
        skill_id = None

    return description, skill_id, None, disable_model_invocation, body


def expand_slash_body(template: str, args: str) -> str:
    """Replace {{args}} with trimmed args (may be empty)."""
    return template.replace("{{args}}", args.strip())


def _load_one_md(path: Path) -> Optional[SlashCommandSpec]:
    stem = path.stem.lower()
    if stem.startswith("_"):
        return None
    if not _NAME_RE.match(stem) or len(stem) > _NAME_MAX_LEN:
        logger.warning(
            "Slash command file %s: name must match ^[a-z0-9]+(-[a-z0-9]+)*$, skipping",
            path,
        )
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("Failed to read slash command %s: %s", path, e)
        return None

    description, skill_id, err, disable_mi, body = _parse_slash_frontmatter(raw)
    if err or description is None:
        logger.warning("Slash command %s: %s, skipping", path, err or "invalid frontmatter")
        return None

    return SlashCommandSpec(
        name=stem,
        description=description,
        body_template=body,
        skill_id=skill_id,
        disable_model_invocation=disable_mi,
        source_path=path,
    )


def collect_slash_commands(dirs: List[Path]) -> Dict[str, SlashCommandSpec]:
    """
    Load all `*.md` from dirs in order; later dirs overwrite earlier for the same command name.
    """
    seen: Dict[str, SlashCommandSpec] = {}
    for d in dirs:
        expanded = d.expanduser().resolve()
        if not expanded.is_dir():
            continue
        for path in sorted(expanded.glob("*.md")):
            spec = _load_one_md(path)
            if spec is not None:
                seen[spec.name] = spec
    return dict(sorted(seen.items(), key=lambda x: x[0]))


__all__ = [
    "SlashCommandSpec",
    "collect_slash_commands",
    "expand_slash_body",
]

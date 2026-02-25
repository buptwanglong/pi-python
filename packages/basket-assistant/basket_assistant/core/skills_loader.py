"""
Skill loader: scan directories for OpenCode-style skills (one dir per skill with SKILL.md).
"""

import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# OpenCode name: lowercase alphanumeric and single hyphens, 1-64 chars
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_NAME_MAX_LEN = 64
_DESCRIPTION_MAX_LEN = 1024


def _parse_frontmatter_and_body(text: str) -> Tuple[Optional[str], Optional[str], str]:
    """Extract name and description from YAML frontmatter and body. Returns (name, description, body)."""
    text = text.strip()
    if not text.startswith("---"):
        return None, None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, None, text
    fm, body = parts[1].strip(), parts[2].strip()
    name_val: Optional[str] = None
    desc_val: Optional[str] = None
    for line in fm.splitlines():
        m = re.match(r"name\s*:\s*(.+)", line, re.IGNORECASE)
        if m:
            name_val = m.group(1).strip().strip("'\"").strip()
            continue
        m = re.match(r"description\s*:\s*(.+)", line, re.IGNORECASE)
        if m:
            desc_val = m.group(1).strip().strip("'\"").strip()
    return name_val, desc_val, body


def _collect_skill_entries(dirs: List[Path], include_ids: Optional[List[str]] = None) -> List[Tuple[str, str, Path]]:
    """
    Scan dirs for OpenCode layout: each skills_dir has subdirs with SKILL.md.
    Return [(skill_name, description, path_to_skill_md)], later dir overwrites earlier for same name.
    """
    seen: dict[str, Tuple[str, Path]] = {}  # name -> (description, path)
    for d in dirs:
        expanded = d.expanduser().resolve()
        if not expanded.exists() or not expanded.is_dir():
            continue
        for subdir in expanded.iterdir():
            if not subdir.is_dir():
                continue
            skill_md = subdir / "SKILL.md"
            if not skill_md.is_file():
                continue
            try:
                raw = skill_md.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning("Failed to read skill file %s: %s", skill_md, e)
                continue
            name_fm, desc_fm, _ = _parse_frontmatter_and_body(raw)
            if not name_fm or not desc_fm:
                logger.warning(
                    "Skill %s: missing required frontmatter 'name' or 'description', skipping",
                    skill_md,
                )
                continue
            if len(desc_fm) > _DESCRIPTION_MAX_LEN:
                logger.warning(
                    "Skill %s: description longer than %d chars, skipping",
                    skill_md,
                    _DESCRIPTION_MAX_LEN,
                )
                continue
            if not _NAME_RE.match(name_fm) or len(name_fm) > _NAME_MAX_LEN:
                logger.warning(
                    "Skill %s: name must match ^[a-z0-9]+(-[a-z0-9]+)*$ and be 1-%d chars, got %r, skipping",
                    skill_md,
                    _NAME_MAX_LEN,
                    name_fm,
                )
                continue
            if name_fm != subdir.name:
                logger.warning(
                    "Skill %s: frontmatter name %r does not match directory name %r, skipping",
                    skill_md,
                    name_fm,
                    subdir.name,
                )
                continue
            if include_ids is not None and len(include_ids) > 0 and name_fm not in include_ids:
                continue
            seen[name_fm] = (desc_fm, skill_md)
    return [(name, desc, path) for name, (desc, path) in sorted(seen.items(), key=lambda x: x[0])]


def get_skills_index(
    dirs: List[Path],
    include_ids: Optional[List[str]] = None,
) -> List[Tuple[str, str]]:
    """
    Return [(skill_name, description), ...] for all skills in dirs (OpenCode layout: */SKILL.md).
    """
    entries = _collect_skill_entries(dirs, include_ids)
    return [(name, desc) for name, desc, _ in entries]


def get_skill_full_content(skill_id: str, dirs: List[Path]) -> str:
    """
    Return full body content for the skill (no frontmatter). Empty string if not found.
    """
    for _name, _desc, path in _collect_skill_entries(dirs, include_ids=None):
        if _name != skill_id:
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except Exception:
            return ""
        _, _, body = _parse_frontmatter_and_body(raw)
        return body
    return ""


def get_skill_base_dir(skill_id: str, dirs: List[Path]) -> Optional[Path]:
    """
    Return the base directory (parent of SKILL.md) for the skill, or None if not found.
    Used by the skill tool to show "Base directory for this skill" in the output.
    """
    for _name, _desc, path in _collect_skill_entries(dirs, include_ids=None):
        if _name != skill_id:
            continue
        return path.parent
    return None

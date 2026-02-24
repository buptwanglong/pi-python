"""
Skill loader: scan directories for .md skills, parse short description and full content.
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple

# Optional in-memory cache: skill_id -> (short_desc, full_body)
_cache: Optional[dict[str, Tuple[str, str]]] = None


def _parse_frontmatter_and_body(text: str) -> Tuple[Optional[str], str]:
    """Extract optional description from YAML frontmatter and body. Returns (description, body)."""
    text = text.strip()
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    fm, body = parts[1].strip(), parts[2].strip()
    desc = None
    for line in fm.splitlines():
        m = re.match(r"description\s*:\s*(.+)", line, re.IGNORECASE)
        if m:
            desc = m.group(1).strip().strip("'\"").strip()
            break
    return desc, body


def _short_description_from_content(content: str, max_chars: int = 200) -> str:
    """First paragraph or first max_chars as short description."""
    content = content.strip()
    if not content:
        return "(no description)"
    first_para = content.split("\n\n")[0].strip()
    if len(first_para) > max_chars:
        return first_para[: max_chars - 3].rstrip() + "..."
    return first_para or "(no description)"


def _collect_skill_files(dirs: List[Path], include_ids: Optional[List[str]] = None) -> List[Tuple[str, Path]]:
    """Scan dirs for *.md; return [(skill_id, path), ...] sorted by id; later dir overrides earlier for same id."""
    seen: dict[str, Path] = {}
    for d in dirs:
        expanded = d.expanduser().resolve()
        if not expanded.exists() or not expanded.is_dir():
            continue
        for f in expanded.glob("*.md"):
            if f.name.startswith("_"):
                continue
            sid = f.stem
            if include_ids is not None and len(include_ids) > 0 and sid not in include_ids:
                continue
            seen[sid] = f
    return sorted(seen.items(), key=lambda x: x[0])


def get_skills_index(
    dirs: List[Path],
    include_ids: Optional[List[str]] = None,
) -> List[Tuple[str, str]]:
    """
    Return [(skill_id, short_description), ...] for all skills in dirs.
    """
    out: List[Tuple[str, str]] = []
    for sid, path in _collect_skill_files(dirs, include_ids):
        try:
            raw = path.read_text(encoding="utf-8")
        except Exception:
            out.append((sid, "(failed to read)"))
            continue
        desc_from_fm, body = _parse_frontmatter_and_body(raw)
        short = desc_from_fm if desc_from_fm is not None else _short_description_from_content(body)
        out.append((sid, short))
    return out


def get_skill_full_content(skill_id: str, dirs: List[Path]) -> str:
    """
    Return full body content for the skill (no frontmatter in body). Empty string if not found.
    """
    for _, path in _collect_skill_files(dirs, include_ids=None):
        if path.stem != skill_id:
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except Exception:
            return ""
        _, body = _parse_frontmatter_and_body(raw)
        return body
    return ""

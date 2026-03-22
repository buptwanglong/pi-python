"""
Validate a skill directory (SKILL.md frontmatter and naming rules).
Usage: python -m basket_assistant.scripts.quick_validate <path-to-skill-dir>
Exit code 0 if valid, non-zero otherwise.
"""

import sys
from pathlib import Path

from basket_assistant.core.loader.skills_loader import (
    _DESCRIPTION_MAX_LEN,
    _NAME_MAX_LEN,
    _NAME_RE,
    _parse_frontmatter_and_body,
)


def _validate(path: Path) -> list[str]:
    """Run all checks. Return list of error messages (empty if valid)."""
    errors: list[str] = []
    if not path.exists():
        errors.append(f"Path does not exist: {path}")
        return errors
    if not path.is_dir():
        errors.append(f"Path is not a directory: {path}")
        return errors

    skill_md = path / "SKILL.md"
    if not skill_md.is_file():
        errors.append("SKILL.md not found or not a file")
        return errors

    try:
        raw = skill_md.read_text(encoding="utf-8")
    except Exception as e:
        errors.append(f"Failed to read SKILL.md: {e}")
        return errors

    name_fm, desc_fm, _ = _parse_frontmatter_and_body(raw)
    if not name_fm or not name_fm.strip():
        errors.append("Frontmatter 'name' is missing or empty")
    if not desc_fm or not desc_fm.strip():
        errors.append("Frontmatter 'description' is missing or empty")

    if name_fm and path.name != name_fm:
        errors.append(f"Frontmatter name {name_fm!r} does not match directory name {path.name!r}")

    if name_fm and (not _NAME_RE.match(name_fm) or len(name_fm) > _NAME_MAX_LEN):
        errors.append(
            f"Name must match ^[a-z0-9]+(-[a-z0-9]+)*$ and be 1-{_NAME_MAX_LEN} chars, got {name_fm!r}"
        )

    if desc_fm and len(desc_fm) > _DESCRIPTION_MAX_LEN:
        errors.append(f"Description must be at most {_DESCRIPTION_MAX_LEN} chars, got {len(desc_fm)}")

    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m basket_assistant.scripts.quick_validate <path-to-skill-dir>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1]).expanduser().resolve()
    errors = _validate(path)
    if errors:
        for msg in errors:
            print(f"ERROR: {msg}", file=sys.stderr)
        return 1
    print("Validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

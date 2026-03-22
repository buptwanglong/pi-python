"""
Create a new skill directory with SKILL.md template and optional scripts/references/assets.
Usage: python -m basket_assistant.scripts.init_skill <skill-name> --path <output-dir> [--resources scripts,references,assets] [--examples]
"""

import argparse
import re
import sys
from pathlib import Path

from basket_assistant.core.loader.skills_loader import _NAME_MAX_LEN, _NAME_RE

ALLOWED_RESOURCES = {"scripts", "references", "assets"}


def _skill_md_content(skill_name: str) -> str:
    """Generate SKILL.md template body."""
    # Human-readable title: capitalize words
    title = " ".join(w.capitalize() for w in skill_name.split("-"))
    return f"""---
name: {skill_name}
description: <TODO: describe what this skill does and when to use it>
---

# {title}

<TODO: Add instructions and when to use scripts/references.>
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a new skill directory with SKILL.md template."
    )
    parser.add_argument(
        "skill_name",
        metavar="skill-name",
        help="Skill name (lowercase, hyphens; must match ^[a-z0-9]+(-[a-z0-9]+)*$, max 64 chars)",
    )
    parser.add_argument(
        "--path",
        required=True,
        type=Path,
        help="Output directory under which to create the skill (e.g. ~/.basket/skills)",
    )
    parser.add_argument(
        "--resources",
        type=str,
        default="",
        help="Comma-separated: scripts, references, assets (create these subdirs)",
    )
    parser.add_argument(
        "--examples",
        action="store_true",
        help="Add placeholder files in scripts/ and references/",
    )
    args = parser.parse_args()

    name = args.skill_name.strip()
    if not _NAME_RE.match(name) or len(name) > _NAME_MAX_LEN:
        print(
            f"ERROR: skill name must match ^[a-z0-9]+(-[a-z0-9]+)*$ and be 1-{_NAME_MAX_LEN} chars, got {name!r}",
            file=sys.stderr,
        )
        return 1

    base = args.path.expanduser().resolve()
    if not base.exists():
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"ERROR: failed to create path {base}: {e}", file=sys.stderr)
            return 1
    if not base.is_dir():
        print(f"ERROR: path is not a directory: {base}", file=sys.stderr)
        return 1

    skill_dir = base / name
    if skill_dir.exists():
        print(f"ERROR: skill directory already exists: {skill_dir}", file=sys.stderr)
        return 1

    skill_dir.mkdir(parents=False)
    (skill_dir / "SKILL.md").write_text(_skill_md_content(name), encoding="utf-8")

    resources = set()
    if args.resources:
        for part in args.resources.split(","):
            part = part.strip().lower()
            if part in ALLOWED_RESOURCES:
                resources.add(part)
            elif part:
                print(f"WARNING: unknown resource {part!r}, ignoring", file=sys.stderr)

    for sub in resources:
        (skill_dir / sub).mkdir()

    if args.examples:
        if "scripts" in resources:
            (skill_dir / "scripts" / "README.txt").write_text(
                "Replace with your scripts. Use from skill base dir.\n",
                encoding="utf-8",
            )
        if "references" in resources:
            (skill_dir / "references" / "README.txt").write_text(
                "Replace with your reference files. Load with read when needed.\n",
                encoding="utf-8",
            )

    print(f"Created skill at {skill_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

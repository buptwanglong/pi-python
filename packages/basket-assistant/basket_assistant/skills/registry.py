"""Builtin skill roots: single place to register package-shipped skill directories."""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# (skill directory name under builtin/, path to module relative to that directory)
_BUILTIN_SKILL_TOOL_SCRIPTS: tuple[tuple[str, str], ...] = (
    ("create-skill", "scripts/skill_authoring_tools.py"),
)


def get_builtin_skill_roots() -> list[Path]:
    """Return skill directory roots scanned before user and plugin paths.

    Each root uses OpenCode layout: immediate subdirs with SKILL.md.
    Later roots in get_skills_dirs override earlier entries for the same skill id.
    """
    return [Path(__file__).resolve().parent / "builtin"]


def load_builtin_skill_tool_modules() -> None:
    """Import tool-registration modules shipped under builtin/*/scripts/.

    Skill folders use hyphenated names (e.g. create-skill), so they are not Python
    packages; modules are loaded by file path. Idempotent: skips if tools from this
    bundle are already registered (e.g. avoids duplicates if import runs twice).
    """
    from basket_assistant.tools._registry import get_all

    if any(d.name == "draft_skill_from_session" for d in get_all()):
        return

    pkg_dir = Path(__file__).resolve().parent
    for skill_dir_name, rel_script in _BUILTIN_SKILL_TOOL_SCRIPTS:
        path = pkg_dir / "builtin" / skill_dir_name / rel_script
        if not path.is_file():
            logger.warning("Builtin skill tool script missing: %s", path)
            continue
        mod_name = f"basket_assistant_builtin_skill_{skill_dir_name.replace('-', '_')}_tools"
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:
            logger.warning("Could not load spec for builtin skill tools: %s", path)
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)


__all__ = ["get_builtin_skill_roots", "load_builtin_skill_tool_modules"]

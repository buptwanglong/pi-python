"""Tests for fixed skills and slash-commands directory resolution."""

from pathlib import Path
from unittest.mock import MagicMock

from basket_assistant.agent.prompts import get_skills_dirs, get_slash_commands_dirs
from basket_assistant.core import get_skills_index
from basket_assistant.skills.registry import get_builtin_skill_roots


def test_get_skills_dirs_ignores_settings_skills_dirs() -> None:
    settings = MagicMock()
    settings.skills_dirs = ["/should/be/ignored"]
    dirs = get_skills_dirs(settings)
    assert dirs[0] == get_builtin_skill_roots()[0]
    assert Path.home() / ".basket" / "skills" in dirs
    assert Path.cwd() / ".basket" / "skills" in dirs
    assert not any("ignored" in str(p) for p in dirs)


def test_builtin_create_skill_in_skills_index() -> None:
    roots = get_builtin_skill_roots()
    index = get_skills_index(roots)
    names = [n for n, _ in index]
    assert "create-skill" in names


def test_get_skills_dirs_appends_plugin_dirs() -> None:
    settings = MagicMock()
    settings.skills_dirs = []
    extra = Path("/tmp/plugin-skills")
    dirs = get_skills_dirs(settings, plugin_skill_dirs=[extra])
    assert dirs[0] == get_builtin_skill_roots()[0]
    assert dirs[-1] == extra


def test_get_slash_commands_dirs_fixed_plus_plugins() -> None:
    extra = Path("/tmp/plugin-cmd")
    dirs = get_slash_commands_dirs([extra])
    assert dirs[0] == Path.home() / ".basket" / "commands"
    assert dirs[1] == Path.cwd() / ".basket" / "commands"
    assert dirs[2] == extra


def test_get_slash_commands_dirs_no_plugins() -> None:
    dirs = get_slash_commands_dirs(None)
    assert len(dirs) == 2

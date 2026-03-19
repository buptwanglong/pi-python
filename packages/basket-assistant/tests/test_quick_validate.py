"""Tests for quick_validate script."""

import subprocess
import sys
from pathlib import Path


def _run_quick_validate(skill_path: Path) -> subprocess.CompletedProcess:
    """Run quick_validate on skill_path. skill_path can be str or Path."""
    return subprocess.run(
        [sys.executable, "-m", "basket_assistant.scripts.quick_validate", str(skill_path)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )


def test_quick_validate_pass(tmp_path):
    """Valid skill directory passes validation."""
    (tmp_path / "my-skill").mkdir()
    (tmp_path / "my-skill" / "SKILL.md").write_text(
        "---\nname: my-skill\ndescription: A short description for the skill.\n---\n\n# Body",
        encoding="utf-8",
    )
    result = _run_quick_validate(tmp_path / "my-skill")
    assert result.returncode == 0
    assert "Validation passed" in result.stdout
    assert "ERROR" not in result.stdout


def test_quick_validate_missing_skill_md(tmp_path):
    """Directory without SKILL.md fails."""
    (tmp_path / "empty").mkdir()
    result = _run_quick_validate(tmp_path / "empty")
    assert result.returncode != 0
    assert "ERROR" in result.stderr
    assert "SKILL.md" in result.stderr


def test_quick_validate_missing_name(tmp_path):
    """SKILL.md without name in frontmatter fails."""
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "SKILL.md").write_text(
        "---\ndescription: Only description\n---\n\nBody",
        encoding="utf-8",
    )
    result = _run_quick_validate(tmp_path / "bad")
    assert result.returncode != 0
    assert "ERROR" in result.stderr
    assert "name" in result.stderr.lower()


def test_quick_validate_name_mismatch(tmp_path):
    """Frontmatter name not matching directory name fails."""
    (tmp_path / "dir-name").mkdir()
    (tmp_path / "dir-name" / "SKILL.md").write_text(
        "---\nname: other-name\ndescription: Desc\n---\n\nBody",
        encoding="utf-8",
    )
    result = _run_quick_validate(tmp_path / "dir-name")
    assert result.returncode != 0
    assert "ERROR" in result.stderr
    assert "match" in result.stderr.lower() or "directory" in result.stderr.lower()


def test_quick_validate_invalid_name_regex(tmp_path):
    """Invalid name (e.g. uppercase) fails."""
    (tmp_path / "Bad-Name").mkdir()
    (tmp_path / "Bad-Name" / "SKILL.md").write_text(
        "---\nname: Bad-Name\ndescription: Desc\n---\n\nBody",
        encoding="utf-8",
    )
    result = _run_quick_validate(tmp_path / "Bad-Name")
    assert result.returncode != 0
    assert "ERROR" in result.stderr


def test_quick_validate_nonexistent_path(tmp_path):
    """Nonexistent path fails."""
    result = _run_quick_validate(tmp_path / "nonexistent")
    assert result.returncode != 0
    assert "ERROR" in result.stderr

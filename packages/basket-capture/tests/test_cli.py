"""Integration tests for CLI record command."""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from basket_capture.cli import resolve_record_output_path, resolve_sessions_parent


def test_resolve_record_output_path_default(tmp_path: Path) -> None:
    """No --output -> ~/.basket/capture under given home with timestamped name."""
    fixed = datetime(2026, 3, 19, 14, 30, 5)
    p = resolve_record_output_path(None, home=tmp_path, now=fixed)
    assert p == tmp_path / ".basket" / "capture" / "capture-20260319-143005.cast"
    assert p.parent.is_dir()


def test_resolve_record_output_path_explicit_cast(tmp_path: Path) -> None:
    """--output foo.cast uses that path (no forced timestamp in name)."""
    out = tmp_path / "mysession.cast"
    p = resolve_record_output_path(out, home=tmp_path)
    assert p == out
    assert p.parent.is_dir()


def test_resolve_record_output_path_directory(tmp_path: Path) -> None:
    """--output somedir/ writes capture-<ts>.cast inside."""
    fixed = datetime(2026, 1, 2, 3, 4, 5)
    d = tmp_path / "sessions"
    p = resolve_record_output_path(d, home=tmp_path, now=fixed)
    assert p == d / "capture-20260102-030405.cast"


def test_cli_record_help() -> None:
    """record subcommand shows help."""
    result = subprocess.run(
        [sys.executable, "-m", "basket_capture.cli", "record", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "record" in result.stdout
    assert ".cast" in result.stdout
    assert "--output" in result.stdout
    assert "--bundle" in result.stdout
    assert "--screenshot-cmd" in result.stdout


def test_resolve_sessions_parent_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    p = resolve_sessions_parent(None)
    assert p == tmp_path / ".basket" / "capture" / "sessions"


def test_resolve_sessions_parent_explicit(tmp_path: Path) -> None:
    custom = tmp_path / "my-sessions"
    p = resolve_sessions_parent(custom)
    assert p == custom
    assert p.is_dir()


def test_cli_record_without_output_uses_default_path_not_argparse_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """record without --output resolves default path; fails later if not a TTY."""
    monkeypatch.setenv("HOME", str(tmp_path))
    result = subprocess.run(
        [sys.executable, "-m", "basket_capture.cli", "record", "--timeout", "0.01"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert "required" not in result.stderr.lower()
    assert "终端" in result.stderr or "terminal" in result.stderr.lower()

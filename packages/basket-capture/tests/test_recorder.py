"""Tests for basket_capture.recorder (pty recording to asciinema v2 .cast)."""

import json
import sys
from pathlib import Path

import pytest

from basket_capture.recorder import record

# Skip when no TTY so CI doesn't fail; openpty() may still work but echo might behave differently
_pty_available = sys.stdin.isatty()


@pytest.mark.skipif(not _pty_available, reason="pty required (run in a real terminal)")
def test_record_produces_cast_file(tmp_path: Path) -> None:
    """record(command, output_path, timeout=2) produces a .cast file with version and stdout."""
    output_path = tmp_path / "out.cast"
    record("echo hello", output_path, timeout=2)

    assert output_path.exists()
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert "version" in data
    assert "stdout" in data
    assert isinstance(data["stdout"], list)

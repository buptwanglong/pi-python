"""Integration tests for CLI generate-prd pipeline."""

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from basket_capture.cast import parse_cast
from basket_capture.layout import infer_regions
from basket_capture.interactions import detect_interactions
from basket_capture.renderer import AnalysisResult, render_prd


def test_cli_generate_prd_nonexistent_cast_exits_nonzero(tmp_path: Path) -> None:
    """generate-prd with non-existent --cast file prints error and exits with code 1."""
    nonexistent = tmp_path / "nonexistent.cast"
    assert not nonexistent.exists()
    result = subprocess.run(
        [sys.executable, "-m", "basket_capture.cli", "generate-prd", "--cast", str(nonexistent)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert "Error" in result.stderr or "not found" in result.stderr.lower() or "Cast file" in result.stderr


def test_cli_generate_prd_invalid_output_path_exits_nonzero(tmp_path: Path) -> None:
    """generate-prd with --output pointing to a directory (non-writable as file) exits non-zero."""
    fixture_dir = Path(__file__).parent / "fixtures"
    cast_path = fixture_dir / "sample.cast"
    if not cast_path.exists():
        pytest.skip("Fixture sample.cast not found")
    # Output to a path that is a directory -> write will fail
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "basket_capture.cli",
            "generate-prd",
            "--cast",
            str(cast_path),
            "--output",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert "Error" in result.stderr or "write" in result.stderr.lower() or "writable" in result.stderr.lower()


def test_generate_prd_pipeline_programmatically() -> None:
    """Run generate-prd pipeline on fixture and assert output file has expected sections."""
    fixture_dir = Path(__file__).parent / "fixtures"
    cast_path = fixture_dir / "sample.cast"
    assert cast_path.exists(), f"Fixture missing: {cast_path}"

    cast_result = parse_cast(cast_path)
    regions = infer_regions(cast_result)
    interactions = detect_interactions(cast_result)
    analysis = AnalysisResult(
        layout=regions,
        interactions=interactions,
        screenshots=[],
    )

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".md",
        delete=False,
    ) as f:
        out_path = Path(f.name)
    try:
        render_prd(analysis, out_path)
        content = out_path.read_text(encoding="utf-8")
        assert "Layout" in content
        assert "PRD" in content or "Product Requirements" in content
        assert out_path.exists()
    finally:
        out_path.unlink(missing_ok=True)

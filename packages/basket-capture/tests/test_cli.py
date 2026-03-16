"""Integration tests for CLI generate-prd pipeline."""

import tempfile
from pathlib import Path

import pytest

from basket_capture.cast import parse_cast
from basket_capture.layout import infer_regions
from basket_capture.interactions import detect_interactions
from basket_capture.renderer import AnalysisResult, render_prd


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

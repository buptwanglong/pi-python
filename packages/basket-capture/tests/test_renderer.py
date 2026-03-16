"""Tests for PRD renderer: render_prd fills template from analysis result."""

import pytest

from basket_capture.layout import Region
from basket_capture.interactions import Interaction
from basket_capture.renderer import render_prd, AnalysisResult


def test_render_prd_produces_markdown_with_sections():
    """Render PRD returns markdown with section titles and all placeholders replaced."""
    analysis_result = AnalysisResult(
        layout=[
            Region(type="header", start_line=0, end_line=0),
            Region(type="chat", start_line=1, end_line=2),
            Region(type="input", start_line=3, end_line=3),
        ],
        interactions=[
            Interaction(timestamp=1.0, type="send", payload=None),
        ],
        screenshots=[],
    )
    result = render_prd(analysis_result, output_path=None)

    assert "## Layout" in result
    assert "## Components" in result
    assert "## Shortcuts" in result
    assert "## Flows" in result
    assert "## Screenshots" in result
    assert "{{" not in result, "all placeholders must be replaced (no {{ left)"


def test_render_prd_writes_to_file_when_output_path_given(tmp_path):
    """When output_path is provided, render_prd writes the markdown to that file."""
    out = tmp_path / "prd.md"
    analysis_result = AnalysisResult(
        layout=[Region(type="header", start_line=0, end_line=0)],
        interactions=[],
        screenshots=[],
    )
    render_prd(analysis_result, output_path=out)

    content = out.read_text(encoding="utf-8")
    assert "## Layout" in content
    assert "{{" not in content

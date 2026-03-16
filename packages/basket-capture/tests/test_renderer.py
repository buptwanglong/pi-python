"""Tests for PRD renderer: render_prd fills template from analysis result."""

from pathlib import Path
from unittest.mock import patch

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


def test_render_prd_empty_layout_shows_placeholder():
    """When layout is empty, PRD shows 布局未识别 and does not crash."""
    analysis_result = AnalysisResult(
        layout=[],
        interactions=[],
        screenshots=[],
    )
    result = render_prd(analysis_result, output_path=None)
    assert "布局未识别" in result
    assert "{{" not in result


def test_render_prd_non_writable_output_raises(tmp_path):
    """When output_path is a directory or otherwise not writable, render_prd raises OSError."""
    # Passing a directory as output path causes write to fail (IsADirectoryError or similar)
    out_dir = tmp_path / "subdir"
    out_dir.mkdir()
    analysis_result = AnalysisResult(
        layout=[Region(type="header", start_line=0, end_line=0)],
        interactions=[],
        screenshots=[],
    )
    with pytest.raises(OSError):
        render_prd(analysis_result, output_path=out_dir)


def test_render_prd_uses_embedded_template_when_file_missing():
    """When prd_template.md is missing, render_prd uses embedded default and still produces valid output."""
    analysis_result = AnalysisResult(
        layout=[Region(type="header", start_line=0, end_line=0)],
        interactions=[],
        screenshots=[],
    )
    with patch("basket_capture.renderer._template_path", return_value=Path("/nonexistent/prd_template.md")):
        result = render_prd(analysis_result, output_path=None)
    assert "## Layout" in result
    assert "## Components" in result
    assert "{{" not in result

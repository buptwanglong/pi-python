"""PRD renderer: fill Markdown template from analysis result (no LLM)."""

from pathlib import Path

from pydantic import BaseModel, Field

from basket_capture.layout import Region
from basket_capture.interactions import Interaction

# Embedded default so the package works even if prd_template.md is removed
DEFAULT_TEMPLATE = """# PRD (Product Requirements Document)

## Layout

{{layout}}

## Components

{{components}}

## Shortcuts

{{shortcuts}}

## Flows

{{flows}}

## Screenshots

{{screenshots}}
"""


class AnalysisResult(BaseModel):
    """Result of layout + interaction analysis for PRD rendering."""

    layout: list[Region] = Field(default_factory=list)
    interactions: list[Interaction] = Field(default_factory=list)
    screenshots: list[str] = Field(default_factory=list)


def _template_path() -> Path:
    return Path(__file__).parent / "prd_template.md"


def _format_layout(regions: list[Region]) -> str:
    if not regions:
        return "布局未识别"
    lines = ["| Type | Start line | End line |"]
    lines.append("|------|------------|----------|")
    for r in regions:
        lines.append(f"| {r.type} | {r.start_line} | {r.end_line} |")
    return "\n".join(lines)


def _format_components(regions: list[Region]) -> str:
    if not regions:
        return "布局未识别"
    return "\n".join(f"- **{r.type}** (lines {r.start_line}–{r.end_line})" for r in regions)


def _format_shortcuts(interactions: list[Interaction]) -> str:
    if not interactions:
        return "None recorded."
    return "\n".join(f"- {i.type} (t={i.timestamp})" for i in interactions)


def _format_flows(interactions: list[Interaction]) -> str:
    if not interactions:
        return "No flows inferred."
    return "\n".join(f"- {i.type} at {i.timestamp}s" for i in interactions)


def _format_screenshots(paths: list[str]) -> str:
    if not paths:
        return "None"
    return "\n".join(f"- {p}" for p in paths)


def render_prd(
    analysis_result: AnalysisResult,
    output_path: str | Path | None = None,
) -> str:
    """
    Fill the PRD template with analysis result and return the Markdown string.

    If output_path is provided, also write the result to that file.
    No LLM calls.
    """
    template_path = _template_path()
    if template_path.exists():
        text = template_path.read_text(encoding="utf-8")
    else:
        text = DEFAULT_TEMPLATE

    text = text.replace("{{layout}}", _format_layout(analysis_result.layout))
    text = text.replace("{{components}}", _format_components(analysis_result.layout))
    text = text.replace(
        "{{shortcuts}}", _format_shortcuts(analysis_result.interactions)
    )
    text = text.replace("{{flows}}", _format_flows(analysis_result.interactions))
    text = text.replace(
        "{{screenshots}}", _format_screenshots(analysis_result.screenshots)
    )

    if output_path is not None:
        Path(output_path).write_text(text, encoding="utf-8")

    return text

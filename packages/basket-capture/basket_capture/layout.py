"""Layout inferrer: infer Header/Chat/Footer/Input regions from frame lines or CastResult."""

from typing import Literal, Union

from pydantic import BaseModel, Field

from basket_capture.cast import CastResult


class Region(BaseModel):
    """A contiguous region of lines with a layout type."""

    type: Literal["header", "chat", "footer", "input"] = Field(
        ..., description="Region type"
    )
    start_line: int = Field(..., ge=0, description="First line index (0-based inclusive)")
    end_line: int = Field(..., ge=0, description="Last line index (0-based inclusive)")


def infer_regions(
    lines_or_cast: Union[list[str], CastResult],
) -> list[Region]:
    """
    Infer layout regions from a list of lines or from the last frame of a CastResult.

    Simple rules: first line = header, last line = input, second-to-last = footer,
    middle lines = chat. Empty or single-line input yields minimal regions.

    Args:
        lines_or_cast: Either a list of line strings, or a CastResult (uses last frame
            text split by newline).

    Returns:
        List of Region with type and start_line/end_line (0-based inclusive).
    """
    if isinstance(lines_or_cast, CastResult):
        if not lines_or_cast.frames:
            return []
        text = "".join(f.text for f in lines_or_cast.frames)
        lines = text.split("\n")
        if text and not text.endswith("\n"):
            # Last chunk might not end with newline; split still gives one line per row
            pass
        lines = [ln for ln in lines]  # keep empty lines to preserve indices if needed
    else:
        lines = list(lines_or_cast)

    if not lines:
        return []

    n = len(lines)
    regions: list[Region] = []

    # First line = header
    regions.append(Region(type="header", start_line=0, end_line=0))

    if n == 1:
        return regions

    # Middle = chat (lines 1 .. n-3 when n >= 4)
    if n >= 4:
        regions.append(
            Region(type="chat", start_line=1, end_line=n - 3)
        )

    # Second-to-last = footer
    if n >= 3:
        regions.append(
            Region(type="footer", start_line=n - 2, end_line=n - 2)
        )

    # Last line = input
    regions.append(Region(type="input", start_line=n - 1, end_line=n - 1))

    return regions

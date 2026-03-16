"""Asciinema v2 cast parser: read .cast JSON and produce frames + events."""

from pathlib import Path

import json
from typing import Any

from pydantic import BaseModel, Field


class CastFrame(BaseModel):
    """One frame: cumulative time (seconds) and text chunk from stdout."""

    time: float = Field(..., description="Cumulative time in seconds")
    text: str = Field(..., description="Text chunk for this frame")


class CastResult(BaseModel):
    """Result of parsing an asciinema v2 .cast file."""

    frames: list[CastFrame] = Field(default_factory=list)
    events: list[Any] = Field(default_factory=list)
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    version: int = 2


def parse_cast(path: str | Path) -> CastResult:
    """
    Parse an asciinema v2 .cast file.

    Reads JSON, converts stdout [delay, text] entries into frames (cumulative time + text).
    Asciinema v2 has no separate stdin/key events in the format; events list is empty.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If JSON is invalid or required fields are missing.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Cast file not found: {path}")

    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid or corrupted cast file (not valid JSON): {path}: {e}"
        ) from e

    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid cast file: root must be a JSON object: {path}"
        )

    version = data.get("version", 2)
    width = int(data.get("width", 80))
    height = int(data.get("height", 24))
    stdout = data.get("stdout", [])
    if not isinstance(stdout, list):
        raise ValueError(
            f"Invalid cast file: 'stdout' must be a list: {path}"
        )

    cumulative = 0.0
    frames: list[CastFrame] = []
    for entry in stdout:
        if len(entry) != 2:
            continue
        delay, text = entry[0], entry[1]
        cumulative += float(delay)
        frames.append(CastFrame(time=cumulative, text=str(text)))

    return CastResult(
        frames=frames,
        events=[],
        width=width,
        height=height,
        version=version,
    )

"""
Read tool - Read files from the filesystem.

Supports reading text files with line number ranges and syntax highlighting.
"""

import asyncio
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class ReadParams(BaseModel):
    """Parameters for the Read tool."""

    file_path: str = Field(..., description="Absolute path to the file to read")
    offset: Optional[int] = Field(None, description="Line number to start reading from (1-indexed)")
    limit: Optional[int] = Field(None, description="Number of lines to read")


class ReadResult(BaseModel):
    """Result from reading a file."""

    content: str
    lines: int
    file_path: str


async def read_file(
    file_path: str, offset: Optional[int] = None, limit: Optional[int] = None
) -> ReadResult:
    """
    Read a file with optional line range.

    Args:
        file_path: Path to the file
        offset: Starting line number (1-indexed)
        limit: Number of lines to read

    Returns:
        ReadResult with file content

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file can't be read
    """
    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not path.is_file():
        raise ValueError(f"Not a file: {file_path}")

    # Read file
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        # Try reading as binary and decode with errors='replace'
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

    total_lines = len(lines)

    # Apply offset and limit
    start = (offset - 1) if offset else 0
    end = (start + limit) if limit else total_lines

    # Ensure bounds
    start = max(0, min(start, total_lines))
    end = max(start, min(end, total_lines))

    selected_lines = lines[start:end]

    # Format with line numbers (1-indexed from start)
    formatted_lines = []
    for i, line in enumerate(selected_lines, start=start + 1):
        formatted_lines.append(f"{i:6d}\t{line.rstrip()}")

    content = "\n".join(formatted_lines)

    return ReadResult(
        content=content,
        lines=len(selected_lines),
        file_path=str(path),
    )


# Tool definition for pi-agent
READ_TOOL = {
    "name": "read",
    "description": "Read files from the filesystem with optional line ranges. Returns file content with line numbers.",
    "parameters": ReadParams,
    "execute_fn": read_file,
}


__all__ = ["ReadParams", "ReadResult", "read_file", "READ_TOOL"]

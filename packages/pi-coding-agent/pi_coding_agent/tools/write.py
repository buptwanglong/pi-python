"""
Write tool - Write files to the filesystem.

Creates new files or overwrites existing files with content.
"""

import asyncio
from pathlib import Path

from pydantic import BaseModel, Field


class WriteParams(BaseModel):
    """Parameters for the Write tool."""

    file_path: str = Field(..., description="Absolute path to the file to write")
    content: str = Field(..., description="Content to write to the file")


class WriteResult(BaseModel):
    """Result from writing a file."""

    file_path: str
    bytes_written: int


async def write_file(file_path: str, content: str) -> WriteResult:
    """
    Write content to a file.

    Creates parent directories if they don't exist.
    Overwrites existing files.

    Args:
        file_path: Path to the file
        content: Content to write

    Returns:
        WriteResult with file path and bytes written

    Raises:
        PermissionError: If file can't be written
        OSError: If parent directories can't be created
    """
    path = Path(file_path).expanduser().resolve()

    # Create parent directories if needed
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write file
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    # Get file size
    file_size = path.stat().st_size

    return WriteResult(
        file_path=str(path),
        bytes_written=file_size,
    )


# Tool definition for pi-agent
WRITE_TOOL = {
    "name": "write",
    "description": "Write content to a file. Creates parent directories if needed. Overwrites existing files.",
    "parameters": WriteParams,
    "execute_fn": write_file,
}


__all__ = ["WriteParams", "WriteResult", "write_file", "WRITE_TOOL"]

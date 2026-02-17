"""
Grep tool - Search for patterns in files.

Uses ripgrep-like functionality for fast content searching.
"""

import asyncio
import re
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


class GrepParams(BaseModel):
    """Parameters for the Grep tool."""

    pattern: str = Field(..., description="Regular expression pattern to search for")
    path: str = Field(".", description="Directory or file to search in (default: current directory)")
    glob: Optional[str] = Field(None, description="Glob pattern to filter files (e.g., '*.py', '**/*.ts')")
    case_insensitive: bool = Field(False, description="Case-insensitive search")
    max_results: int = Field(100, description="Maximum number of results to return")


class GrepMatch(BaseModel):
    """A single grep match."""

    file_path: str
    line_number: int
    line: str


class GrepResult(BaseModel):
    """Result from grepping."""

    matches: List[GrepMatch]
    total_matches: int
    truncated: bool


async def grep_files(
    pattern: str,
    path: str = ".",
    glob: Optional[str] = None,
    case_insensitive: bool = False,
    max_results: int = 100,
) -> GrepResult:
    """
    Search for pattern in files.

    Args:
        pattern: Regex pattern to search
        path: Directory or file to search
        glob: Optional glob pattern to filter files
        case_insensitive: Case-insensitive matching
        max_results: Max number of results

    Returns:
        GrepResult with matches
    """
    search_path = Path(path).expanduser().resolve()

    if not search_path.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    # Compile pattern
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}")

    matches: List[GrepMatch] = []

    # Determine files to search
    if search_path.is_file():
        files = [search_path]
    else:
        # Use glob pattern if provided
        if glob:
            files = list(search_path.rglob(glob))
        else:
            files = list(search_path.rglob("*"))

        # Filter only files
        files = [f for f in files if f.is_file()]

    # Search files
    for file_path in files:
        if len(matches) >= max_results:
            break

        # Skip binary files
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    if len(matches) >= max_results:
                        break

                    if regex.search(line):
                        matches.append(
                            GrepMatch(
                                file_path=str(file_path),
                                line_number=line_num,
                                line=line.rstrip(),
                            )
                        )
        except (UnicodeDecodeError, PermissionError):
            # Skip binary files or files we can't read
            continue

    return GrepResult(
        matches=matches,
        total_matches=len(matches),
        truncated=len(matches) >= max_results,
    )


# Tool definition for pi-agent
GREP_TOOL = {
    "name": "grep",
    "description": "Search for patterns in files using regex. Supports glob filtering and case-insensitive search.",
    "parameters": GrepParams,
    "execute_fn": grep_files,
}


__all__ = ["GrepParams", "GrepMatch", "GrepResult", "grep_files", "GREP_TOOL"]

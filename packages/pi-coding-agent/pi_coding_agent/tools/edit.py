"""
Edit tool - Edit files using exact string replacement.

Performs exact string matching and replacement in files.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EditParams(BaseModel):
    """Parameters for the Edit tool."""

    file_path: str = Field(..., description="Absolute path to the file to edit")
    old_string: str = Field(..., description="Exact string to find and replace")
    new_string: str = Field(..., description="String to replace with")
    replace_all: bool = Field(False, description="Replace all occurrences (default: false)")


class EditResult(BaseModel):
    """Result from editing a file."""

    file_path: str
    replacements: int
    success: bool
    error: Optional[str] = None


async def edit_file(
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> EditResult:
    """
    Edit a file by replacing exact string matches.

    Args:
        file_path: Path to the file
        old_string: Exact string to find
        new_string: String to replace with
        replace_all: Whether to replace all occurrences

    Returns:
        EditResult with replacement count

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If old_string not found or not unique (when replace_all=False)
    """
    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        return EditResult(
            file_path=str(path),
            replacements=0,
            success=False,
            error=f"File not found: {file_path}",
        )

    # Read file content
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        logger.warning("Edit read failed for %s: %s", path, e)
        return EditResult(
            file_path=str(path),
            replacements=0,
            success=False,
            error=f"Failed to read file: {e}",
        )

    # Check if old_string exists
    count = content.count(old_string)

    if count == 0:
        return EditResult(
            file_path=str(path),
            replacements=0,
            success=False,
            error=f"String not found in file: {old_string[:50]}...",
        )

    if not replace_all and count > 1:
        return EditResult(
            file_path=str(path),
            replacements=0,
            success=False,
            error=f"String appears {count} times. Use replace_all=True or provide more context to make it unique.",
        )

    # Perform replacement
    if replace_all:
        new_content = content.replace(old_string, new_string)
        replacements = count
    else:
        new_content = content.replace(old_string, new_string, 1)
        replacements = 1

    # Write back
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception as e:
        logger.warning("Edit write failed for %s: %s", path, e)
        return EditResult(
            file_path=str(path),
            replacements=0,
            success=False,
            error=f"Failed to write file: {e}",
        )

    return EditResult(
        file_path=str(path),
        replacements=replacements,
        success=True,
    )


# Tool definition for pi-agent
EDIT_TOOL = {
    "name": "edit",
    "description": "Edit files by replacing exact string matches. IMPORTANT: old_string must match exactly including whitespace and indentation.",
    "parameters": EditParams,
    "execute_fn": edit_file,
}


__all__ = ["EditParams", "EditResult", "edit_file", "EDIT_TOOL"]

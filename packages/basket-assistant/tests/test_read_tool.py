"""
Tests for the Read tool.
"""

import pytest
from pathlib import Path
import tempfile
import os

from basket_assistant.tools.read import read_file, ReadParams, ReadResult


@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Line 1\n")
        f.write("Line 2\n")
        f.write("Line 3\n")
        f.write("Line 4\n")
        f.write("Line 5\n")
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.mark.asyncio
async def test_read_entire_file(temp_file):
    """Test reading an entire file."""
    result = await read_file(temp_file)

    assert result.lines == 5
    assert "Line 1" in result.content
    assert "Line 5" in result.content
    # Compare resolved paths (macOS /var is symlink to /private/var)
    from pathlib import Path
    assert Path(result.file_path).resolve() == Path(temp_file).resolve()


@pytest.mark.asyncio
async def test_read_with_offset(temp_file):
    """Test reading with offset."""
    result = await read_file(temp_file, offset=3)

    assert result.lines == 3
    assert "Line 3" in result.content
    assert "Line 1" not in result.content


@pytest.mark.asyncio
async def test_read_with_limit(temp_file):
    """Test reading with limit."""
    result = await read_file(temp_file, limit=2)

    assert result.lines == 2
    assert "Line 1" in result.content
    assert "Line 2" in result.content
    assert "Line 3" not in result.content


@pytest.mark.asyncio
async def test_read_with_offset_and_limit(temp_file):
    """Test reading with both offset and limit."""
    result = await read_file(temp_file, offset=2, limit=2)

    assert result.lines == 2
    assert "Line 2" in result.content
    assert "Line 3" in result.content
    assert "Line 1" not in result.content
    assert "Line 4" not in result.content


@pytest.mark.asyncio
async def test_read_nonexistent_file():
    """Test reading a nonexistent file."""
    with pytest.raises(FileNotFoundError):
        await read_file("/nonexistent/file.txt")


@pytest.mark.asyncio
async def test_read_directory():
    """Test reading a directory (should fail)."""
    with pytest.raises(ValueError, match="Not a file"):
        await read_file(tempfile.gettempdir())


@pytest.mark.asyncio
async def test_line_numbers_format(temp_file):
    """Test that line numbers are formatted correctly."""
    result = await read_file(temp_file)

    # Check line number format (should be right-aligned with tab separator)
    lines = result.content.split("\n")
    assert "\t" in lines[0]
    assert "     1\t" in lines[0] or "1\t" in lines[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

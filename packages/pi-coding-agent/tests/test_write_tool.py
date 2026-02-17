"""
Tests for the Write tool.
"""

import pytest
from pathlib import Path
import tempfile
import os

from pi_coding_agent.tools.write import write_file, WriteParams, WriteResult


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.mark.asyncio
async def test_write_new_file(temp_dir):
    """Test writing a new file."""
    file_path = os.path.join(temp_dir, "test.txt")
    content = "Hello, World!"

    result = await write_file(file_path, content)

    # Compare resolved paths (macOS /var is symlink to /private/var)
    from pathlib import Path
    assert Path(result.file_path).resolve() == Path(file_path).resolve()
    assert result.bytes_written > 0

    # Verify file was created
    assert os.path.exists(file_path)

    # Verify content
    with open(file_path, "r") as f:
        assert f.read() == content


@pytest.mark.asyncio
async def test_write_overwrites_existing(temp_dir):
    """Test that write overwrites existing files."""
    file_path = os.path.join(temp_dir, "existing.txt")

    # Create initial file
    with open(file_path, "w") as f:
        f.write("Old content")

    # Overwrite
    new_content = "New content"
    result = await write_file(file_path, new_content)

    # Compare resolved paths
    from pathlib import Path
    assert Path(result.file_path).resolve() == Path(file_path).resolve()

    # Verify overwrite
    with open(file_path, "r") as f:
        assert f.read() == new_content


@pytest.mark.asyncio
async def test_write_creates_parent_dirs(temp_dir):
    """Test that write creates parent directories."""
    file_path = os.path.join(temp_dir, "subdir1", "subdir2", "file.txt")
    content = "Test content"

    result = await write_file(file_path, content)

    # Compare resolved paths
    from pathlib import Path
    assert Path(result.file_path).resolve() == Path(file_path).resolve()
    assert os.path.exists(file_path)

    # Verify parent dirs were created
    assert os.path.exists(os.path.join(temp_dir, "subdir1"))
    assert os.path.exists(os.path.join(temp_dir, "subdir1", "subdir2"))


@pytest.mark.asyncio
async def test_write_empty_file(temp_dir):
    """Test writing an empty file."""
    file_path = os.path.join(temp_dir, "empty.txt")

    result = await write_file(file_path, "")

    assert os.path.exists(file_path)
    assert os.path.getsize(file_path) == 0


@pytest.mark.asyncio
async def test_write_unicode_content(temp_dir):
    """Test writing unicode content."""
    file_path = os.path.join(temp_dir, "unicode.txt")
    content = "Hello 世界 🌍"

    result = await write_file(file_path, content)

    # Verify unicode was written correctly
    with open(file_path, "r", encoding="utf-8") as f:
        assert f.read() == content


@pytest.mark.asyncio
async def test_write_multiline_content(temp_dir):
    """Test writing multiline content."""
    file_path = os.path.join(temp_dir, "multiline.txt")
    content = "Line 1\nLine 2\nLine 3"

    result = await write_file(file_path, content)

    with open(file_path, "r") as f:
        lines = f.readlines()
        assert len(lines) == 3
        assert lines[0].strip() == "Line 1"
        assert lines[2].strip() == "Line 3"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

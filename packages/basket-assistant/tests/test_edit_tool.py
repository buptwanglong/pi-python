"""
Tests for the Edit tool.
"""

import pytest
from pathlib import Path
import tempfile
import os

from basket_assistant.tools.edit import edit_file, EditParams, EditResult


@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Line 1\n")
        f.write("Line 2\n")
        f.write("Line 3\n")
        f.write("Line 2\n")  # Duplicate line
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.mark.asyncio
async def test_edit_single_replacement(temp_file):
    """Test replacing a single occurrence."""
    result = await edit_file(temp_file, "Line 1\n", "Modified Line 1\n")

    assert result.success
    assert result.replacements == 1

    # Verify replacement
    with open(temp_file, "r") as f:
        lines = f.readlines()
        assert lines[0] == "Modified Line 1\n"
        assert "Line 2\n" in lines


@pytest.mark.asyncio
async def test_edit_replace_all(temp_file):
    """Test replacing all occurrences."""
    result = await edit_file(temp_file, "Line 2\n", "Modified Line 2\n", replace_all=True)

    assert result.success
    assert result.replacements == 2  # Should replace both occurrences

    # Verify all replaced
    with open(temp_file, "r") as f:
        lines = f.readlines()
        modified_count = sum(1 for line in lines if line == "Modified Line 2\n")
        assert modified_count == 2


@pytest.mark.asyncio
async def test_edit_nonunique_without_replace_all(temp_file):
    """Test that non-unique string fails without replace_all."""
    result = await edit_file(temp_file, "Line 2\n", "Modified")

    assert not result.success
    assert result.replacements == 0
    assert "appears 2 times" in result.error


@pytest.mark.asyncio
async def test_edit_string_not_found(temp_file):
    """Test editing when string is not found."""
    result = await edit_file(temp_file, "Nonexistent", "Modified")

    assert not result.success
    assert result.replacements == 0
    assert "not found" in result.error


@pytest.mark.asyncio
async def test_edit_nonexistent_file():
    """Test editing a nonexistent file."""
    result = await edit_file("/nonexistent/file.txt", "old", "new")

    assert not result.success
    assert "not found" in result.error


@pytest.mark.asyncio
async def test_edit_preserves_other_content(temp_file):
    """Test that edit preserves other content."""
    result = await edit_file(temp_file, "Line 3", "Modified Line 3")

    assert result.success

    with open(temp_file, "r") as f:
        content = f.read()
        assert "Line 1" in content
        assert "Line 2" in content
        assert "Modified Line 3" in content


@pytest.mark.asyncio
async def test_edit_multiline_string(temp_file):
    """Test editing multiline strings."""
    result = await edit_file(temp_file, "Line 1\nLine 2", "Combined Lines")

    assert result.success
    assert result.replacements == 1

    with open(temp_file, "r") as f:
        content = f.read()
        assert "Combined Lines" in content


@pytest.mark.asyncio
async def test_edit_with_special_characters(temp_file):
    """Test editing with special characters."""
    # Add content with special characters
    with open(temp_file, "w") as f:
        f.write("function test() { return true; }")

    result = await edit_file(temp_file, "function test() {", "function test() {\n   ")

    assert result.success


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

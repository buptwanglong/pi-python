"""
Tests for the Grep tool.
"""

import pytest
from pathlib import Path
import tempfile
import os

from basket_assistant.tools.grep import grep_files, GrepParams, GrepMatch, GrepResult


@pytest.fixture
def temp_dir_with_files():
    """Create a temporary directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        (Path(tmpdir) / "file1.txt").write_text("Hello World\nPython is great\nHello again")
        (Path(tmpdir) / "file2.txt").write_text("JavaScript is fun\nHello there")
        (Path(tmpdir) / "file3.py").write_text("def hello():\n    return 'Hello'\n")

        # Create subdirectory with files
        subdir = Path(tmpdir) / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("Nested Hello\nNested content")

        yield tmpdir


@pytest.mark.asyncio
async def test_grep_simple_pattern(temp_dir_with_files):
    """Test searching for a simple pattern."""
    result = await grep_files("Hello", path=temp_dir_with_files)

    assert result.total_matches >= 3  # Should find "Hello" in multiple files
    assert any("Hello" in m.line for m in result.matches)


@pytest.mark.asyncio
async def test_grep_case_insensitive(temp_dir_with_files):
    """Test case-insensitive search."""
    result = await grep_files("hello", path=temp_dir_with_files, case_insensitive=True)

    assert result.total_matches >= 3


@pytest.mark.asyncio
async def test_grep_case_sensitive(temp_dir_with_files):
    """Test case-sensitive search."""
    result = await grep_files("hello", path=temp_dir_with_files, case_insensitive=False)

    # Should find the function def hello() but not Hello
    assert result.total_matches >= 1


@pytest.mark.asyncio
async def test_grep_with_glob(temp_dir_with_files):
    """Test grep with glob pattern."""
    result = await grep_files("Hello", path=temp_dir_with_files, glob="*.txt")

    # Should only search .txt files
    assert all(m.file_path.endswith(".txt") for m in result.matches)


@pytest.mark.asyncio
async def test_grep_regex_pattern(temp_dir_with_files):
    """Test grep with regex pattern."""
    result = await grep_files(r"\bHello\b", path=temp_dir_with_files)

    assert result.total_matches > 0
    assert all("Hello" in m.line for m in result.matches)


@pytest.mark.asyncio
async def test_grep_max_results(temp_dir_with_files):
    """Test max_results limit."""
    result = await grep_files("Hello", path=temp_dir_with_files, max_results=2)

    assert result.total_matches <= 2
    assert len(result.matches) <= 2


@pytest.mark.asyncio
async def test_grep_single_file(temp_dir_with_files):
    """Test grepping a single file."""
    file_path = os.path.join(temp_dir_with_files, "file1.txt")
    result = await grep_files("Hello", path=file_path)

    assert result.total_matches >= 2  # "Hello World" and "Hello again"
    # Compare resolved paths
    from pathlib import Path
    assert all(Path(m.file_path).resolve() == Path(file_path).resolve() for m in result.matches)


@pytest.mark.asyncio
async def test_grep_no_matches(temp_dir_with_files):
    """Test grep with no matches."""
    result = await grep_files("NonexistentPattern", path=temp_dir_with_files)

    assert result.total_matches == 0
    assert len(result.matches) == 0


@pytest.mark.asyncio
async def test_grep_line_numbers(temp_dir_with_files):
    """Test that line numbers are correct."""
    result = await grep_files("Python", path=temp_dir_with_files)

    assert result.total_matches > 0
    assert all(m.line_number > 0 for m in result.matches)


@pytest.mark.asyncio
async def test_grep_nonexistent_path():
    """Test grepping a nonexistent path."""
    with pytest.raises(FileNotFoundError):
        await grep_files("pattern", path="/nonexistent/path")


@pytest.mark.asyncio
async def test_grep_invalid_regex():
    """Test grep with invalid regex."""
    with pytest.raises(ValueError, match="Invalid regex"):
        await grep_files("[invalid(regex", path=".")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

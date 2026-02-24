"""
Test Markdown and Code Block components
"""

import pytest
from basket_tui.components import MarkdownViewer, CodeBlock


def test_markdown_viewer_import():
    """Test that MarkdownViewer can be imported."""
    assert MarkdownViewer is not None


def test_markdown_viewer_instantiation():
    """Test that MarkdownViewer can be instantiated."""
    viewer = MarkdownViewer("# Hello World")
    assert viewer is not None


def test_markdown_viewer_with_code():
    """Test Markdown with code blocks."""
    markdown = """
# Example

Here's some code:

```python
def hello():
    print("Hello, World!")
```

And some `inline code`.
"""
    viewer = MarkdownViewer(markdown)
    assert viewer is not None


def test_code_block_import():
    """Test that CodeBlock can be imported."""
    assert CodeBlock is not None


def test_code_block_instantiation():
    """Test that CodeBlock can be instantiated."""
    code = "def hello():\n    print('Hello!')"
    block = CodeBlock(code, language="python")
    assert block is not None
    assert block._code == code
    assert block._language == "python"


def test_code_block_update():
    """Test updating code block content."""
    block = CodeBlock("old code", language="python")
    block.update_code("new code", language="javascript")
    assert block._code == "new code"
    assert block._language == "javascript"

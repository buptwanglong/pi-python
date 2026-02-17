"""
Test Multi-line Input Components
"""

import pytest
from pi_tui.components import MultiLineInput


def test_multiline_input_import():
    """Test that MultiLineInput can be imported."""
    assert MultiLineInput is not None


def test_multiline_input_instantiation():
    """Test that MultiLineInput can be instantiated."""
    input_widget = MultiLineInput(text="Hello")
    assert input_widget is not None
    assert input_widget.text == "Hello"


def test_multiline_input_with_language():
    """Test MultiLineInput with syntax highlighting."""
    input_widget = MultiLineInput(text="print('hello')", language="python")
    assert input_widget is not None
    assert input_widget.language == "python"


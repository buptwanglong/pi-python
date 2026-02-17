"""
Test Multi-line Input Components
"""

import pytest
from pi_tui.components import MultiLineInput, AutocompleteInput


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


def test_autocomplete_input_import():
    """Test that AutocompleteInput can be imported."""
    assert AutocompleteInput is not None


def test_autocomplete_input_instantiation():
    """Test that AutocompleteInput can be instantiated."""
    suggestions = ["print", "printf", "println"]
    input_widget = AutocompleteInput(text="pr", suggestions=suggestions)
    assert input_widget is not None
    assert input_widget._suggestions == suggestions


def test_autocomplete_input_set_suggestions():
    """Test updating autocomplete suggestions."""
    input_widget = AutocompleteInput()
    new_suggestions = ["hello", "help", "heap"]
    input_widget.set_suggestions(new_suggestions)
    assert input_widget._suggestions == new_suggestions

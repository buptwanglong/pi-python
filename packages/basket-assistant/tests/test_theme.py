"""
Tests for theme system.
"""

import json
import pytest
from pathlib import Path

from basket_assistant.core.theme import Theme, ThemeColors, ThemeManager


def test_theme_colors_creation():
    """Test creating ThemeColors."""
    colors = ThemeColors(
        accent="#00aaff",
        border="#3e3e42",
        border_accent="#00aaff",
        border_muted="#2d2d30",
        success="#00ff00",
        error="#ff0000",
        warning="#ffaa00",
        muted="#808080",
        dim="#606060",
        text="",
        thinking_text="#808080",
        user_message_bg="#2d2d30",
        user_message_text="",
        tool_pending_bg="#1e1e2e",
        tool_success_bg="#1e2e1e",
        tool_error_bg="#2e1e1e",
        tool_title="#00aaff",
        tool_output="#d4d4d4",
        md_heading="#00aaff",
        md_link="#00aaff",
        md_code="#d7ba7d",
        md_code_block="#d4d4d4",
        md_code_block_border="#3e3e42",
        md_quote="#808080",
        md_quote_border="#3e3e42",
        syntax_comment="#608b4e",
        syntax_keyword="#569cd6",
        syntax_function="#dcdcaa",
        syntax_variable="#9cdcfe",
        syntax_string="#ce9178",
        syntax_number="#b5cea8",
        syntax_type="#4ec9b0",
        syntax_operator="#d4d4d4",
    )

    assert colors.accent == "#00aaff"
    assert colors.text == ""
    assert colors.success == "#00ff00"


def test_theme_creation():
    """Test creating a Theme."""
    theme = Theme(
        name="test-theme",
        vars={"primary": "#00aaff", "secondary": "#ff00aa"},
        colors=ThemeColors(
            accent="primary",
            border="secondary",
            border_accent="#00aaff",
            border_muted="#2d2d30",
            success="#00ff00",
            error="#ff0000",
            warning="#ffaa00",
            muted="#808080",
            dim="#606060",
            text="",
            thinking_text="#808080",
            user_message_bg="#2d2d30",
            user_message_text="",
            tool_pending_bg="#1e1e2e",
            tool_success_bg="#1e2e1e",
            tool_error_bg="#2e1e1e",
            tool_title="#00aaff",
            tool_output="#d4d4d4",
            md_heading="#00aaff",
            md_link="#00aaff",
            md_code="#d7ba7d",
            md_code_block="#d4d4d4",
            md_code_block_border="#3e3e42",
            md_quote="#808080",
            md_quote_border="#3e3e42",
            syntax_comment="#608b4e",
            syntax_keyword="#569cd6",
            syntax_function="#dcdcaa",
            syntax_variable="#9cdcfe",
            syntax_string="#ce9178",
            syntax_number="#b5cea8",
            syntax_type="#4ec9b0",
            syntax_operator="#d4d4d4",
        ),
    )

    assert theme.name == "test-theme"
    assert "primary" in theme.vars
    # Note: Variable resolution happens during validation
    assert theme.colors.accent in ["primary", "#00aaff"]


def test_theme_manager_init():
    """Test ThemeManager initialization."""
    manager = ThemeManager()

    # Should have built-in themes
    assert "dark" in manager.list_themes()
    assert "light" in manager.list_themes()

    # Should have default theme
    assert manager.get_current_theme() is not None
    assert manager.get_current_theme().name == "dark"


def test_theme_manager_get_theme():
    """Test getting themes by name."""
    manager = ThemeManager()

    dark = manager.get_theme("dark")
    assert dark is not None
    assert dark.name == "dark"

    light = manager.get_theme("light")
    assert light is not None
    assert light.name == "light"

    nonexistent = manager.get_theme("nonexistent")
    assert nonexistent is None


def test_theme_manager_set_current_theme():
    """Test setting the current theme."""
    manager = ThemeManager()

    # Set to light
    result = manager.set_current_theme("light")
    assert result is True
    assert manager.get_current_theme().name == "light"

    # Try to set non-existent theme
    result = manager.set_current_theme("nonexistent")
    assert result is False
    # Current theme should remain unchanged
    assert manager.get_current_theme().name == "light"


def test_theme_manager_load_from_file(tmp_path):
    """Test loading a theme from a file."""
    manager = ThemeManager()

    # Create a test theme file
    theme_file = tmp_path / "custom-theme.json"
    theme_data = {
        "name": "custom",
        "vars": {"primary": "#ff00ff"},
        "colors": {
            "accent": "#ff00ff",
            "border": "#3e3e42",
            "border_accent": "#ff00ff",
            "border_muted": "#2d2d30",
            "success": "#00ff00",
            "error": "#ff0000",
            "warning": "#ffaa00",
            "muted": "#808080",
            "dim": "#606060",
            "text": "",
            "thinking_text": "#808080",
            "user_message_bg": "#2d2d30",
            "user_message_text": "",
            "tool_pending_bg": "#1e1e2e",
            "tool_success_bg": "#1e2e1e",
            "tool_error_bg": "#2e1e1e",
            "tool_title": "#ff00ff",
            "tool_output": "#d4d4d4",
            "md_heading": "#ff00ff",
            "md_link": "#ff00ff",
            "md_code": "#d7ba7d",
            "md_code_block": "#d4d4d4",
            "md_code_block_border": "#3e3e42",
            "md_quote": "#808080",
            "md_quote_border": "#3e3e42",
            "syntax_comment": "#608b4e",
            "syntax_keyword": "#569cd6",
            "syntax_function": "#dcdcaa",
            "syntax_variable": "#9cdcfe",
            "syntax_string": "#ce9178",
            "syntax_number": "#b5cea8",
            "syntax_type": "#4ec9b0",
            "syntax_operator": "#d4d4d4",
        },
    }

    with open(theme_file, "w") as f:
        json.dump(theme_data, f)

    # Load the theme
    theme = manager.load_theme_from_file(theme_file)

    assert theme is not None
    assert theme.name == "custom"
    assert "custom" in manager.list_themes()

    # Set as current
    manager.set_current_theme("custom")
    assert manager.get_current_theme().name == "custom"


def test_theme_manager_load_from_dir(tmp_path):
    """Test loading themes from a directory."""
    manager = ThemeManager()

    themes_dir = tmp_path / "themes"
    themes_dir.mkdir()

    # Create multiple theme files
    for i in range(3):
        theme_file = themes_dir / f"theme{i}.json"
        theme_data = {
            "name": f"theme{i}",
            "colors": {
                "accent": f"#00{i}{i}ff",
                "border": "#3e3e42",
                "border_accent": "#00aaff",
                "border_muted": "#2d2d30",
                "success": "#00ff00",
                "error": "#ff0000",
                "warning": "#ffaa00",
                "muted": "#808080",
                "dim": "#606060",
                "text": "",
                "thinking_text": "#808080",
                "user_message_bg": "#2d2d30",
                "user_message_text": "",
                "tool_pending_bg": "#1e1e2e",
                "tool_success_bg": "#1e2e1e",
                "tool_error_bg": "#2e1e1e",
                "tool_title": "#00aaff",
                "tool_output": "#d4d4d4",
                "md_heading": "#00aaff",
                "md_link": "#00aaff",
                "md_code": "#d7ba7d",
                "md_code_block": "#d4d4d4",
                "md_code_block_border": "#3e3e42",
                "md_quote": "#808080",
                "md_quote_border": "#3e3e42",
                "syntax_comment": "#608b4e",
                "syntax_keyword": "#569cd6",
                "syntax_function": "#dcdcaa",
                "syntax_variable": "#9cdcfe",
                "syntax_string": "#ce9178",
                "syntax_number": "#b5cea8",
                "syntax_type": "#4ec9b0",
                "syntax_operator": "#d4d4d4",
            },
        }

        with open(theme_file, "w") as f:
            json.dump(theme_data, f)

    # Load themes from directory
    count = manager.load_themes_from_dir(themes_dir)

    assert count == 3
    assert "theme0" in manager.list_themes()
    assert "theme1" in manager.list_themes()
    assert "theme2" in manager.list_themes()


def test_theme_manager_load_from_nonexistent_dir(tmp_path):
    """Test loading from non-existent directory."""
    manager = ThemeManager()

    count = manager.load_themes_from_dir(tmp_path / "nonexistent")
    assert count == 0


def test_theme_manager_list_themes():
    """Test listing available themes."""
    manager = ThemeManager()

    themes = manager.list_themes()

    # Should have at least built-in themes
    assert "dark" in themes
    assert "light" in themes
    assert len(themes) >= 2


def test_builtin_dark_theme():
    """Test built-in dark theme structure."""
    manager = ThemeManager()
    dark = manager.get_theme("dark")

    assert dark is not None
    assert dark.name == "dark"
    assert dark.colors.accent == "#00aaff"
    assert dark.colors.success == "#00ff00"
    assert dark.colors.error == "#ff0000"


def test_builtin_light_theme():
    """Test built-in light theme structure."""
    manager = ThemeManager()
    light = manager.get_theme("light")

    assert light is not None
    assert light.name == "light"
    assert light.colors.accent == "#0066cc"
    assert light.colors.success == "#008000"
    assert light.colors.error == "#cd3131"

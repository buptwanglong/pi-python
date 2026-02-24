"""
Theme System for Pi Coding Agent

Manages color themes for the terminal UI.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, List
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class ThemeColors(BaseModel):
    """Theme color definitions."""

    # Core colors
    accent: str = Field(..., description="Primary accent color")
    border: str = Field(..., description="Normal borders")
    border_accent: str = Field(..., description="Highlighted borders")
    border_muted: str = Field(..., description="Subtle borders")
    success: str = Field(..., description="Success states")
    error: str = Field(..., description="Error states")
    warning: str = Field(..., description="Warning states")
    muted: str = Field(..., description="Secondary/dimmed text")
    dim: str = Field(..., description="Very dimmed text")
    text: str = Field(default="", description="Default text color (empty = terminal default)")

    # Message colors
    thinking_text: str = Field(..., description="Thinking block text")
    user_message_bg: str = Field(..., description="User message background")
    user_message_text: str = Field(..., description="User message text")

    # Tool colors
    tool_pending_bg: str = Field(..., description="Tool box (pending)")
    tool_success_bg: str = Field(..., description="Tool box (success)")
    tool_error_bg: str = Field(..., description="Tool box (error)")
    tool_title: str = Field(..., description="Tool title")
    tool_output: str = Field(..., description="Tool output text")

    # Markdown colors
    md_heading: str = Field(..., description="Markdown headings")
    md_link: str = Field(..., description="Markdown link text")
    md_code: str = Field(..., description="Markdown inline code")
    md_code_block: str = Field(..., description="Markdown code block content")
    md_code_block_border: str = Field(..., description="Markdown code block border")
    md_quote: str = Field(..., description="Markdown blockquote text")
    md_quote_border: str = Field(..., description="Markdown blockquote border")

    # Syntax highlighting
    syntax_comment: str = Field(..., description="Comments")
    syntax_keyword: str = Field(..., description="Keywords")
    syntax_function: str = Field(..., description="Function names")
    syntax_variable: str = Field(..., description="Variable names")
    syntax_string: str = Field(..., description="String literals")
    syntax_number: str = Field(..., description="Number literals")
    syntax_type: str = Field(..., description="Type names")
    syntax_operator: str = Field(..., description="Operators")

    model_config = {"populate_by_name": True}


class Theme(BaseModel):
    """A complete theme definition."""

    name: str = Field(..., description="Theme name")
    vars: Dict[str, str] = Field(default_factory=dict, description="Reusable color variables")
    colors: ThemeColors = Field(..., description="Theme colors")
    export: Dict[str, str] = Field(default_factory=dict, description="HTML export colors")

    @field_validator("colors", mode="before")
    @classmethod
    def resolve_color_vars(cls, colors, info) -> Dict:
        """Resolve color variable references."""
        # If colors is already a ThemeColors object, convert to dict
        if hasattr(colors, "model_dump"):
            colors = colors.model_dump()

        # Convert to dict if not already
        if not isinstance(colors, dict):
            return colors

        # Resolve variables if present
        if "vars" in info.data:
            vars_dict = info.data["vars"]
            resolved = {}
            for key, value in colors.items():
                if isinstance(value, str) and value in vars_dict:
                    resolved[key] = vars_dict[value]
                else:
                    resolved[key] = value
            return resolved
        return colors


class ThemeManager:
    """
    Manages theme loading and selection.

    Themes can be loaded from:
    - Built-in themes (dark, light)
    - User themes (~/.basket/themes/)
    - Project themes (./.basket/themes/)
    """

    def __init__(self):
        self._themes: Dict[str, Theme] = {}
        self._current_theme: Optional[Theme] = None
        self._load_builtin_themes()

    def _load_builtin_themes(self) -> None:
        """Load built-in themes."""
        # Dark theme
        dark_theme = Theme(
            name="dark",
            vars={
                "primary": "#00aaff",
                "bg": "#1e1e1e",
                "bg2": "#2d2d30",
            },
            colors=ThemeColors(
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
            ),
        )

        # Light theme
        light_theme = Theme(
            name="light",
            vars={
                "primary": "#0066cc",
                "bg": "#ffffff",
                "bg2": "#f3f3f3",
            },
            colors=ThemeColors(
                accent="#0066cc",
                border="#cccccc",
                border_accent="#0066cc",
                border_muted="#e1e1e1",
                success="#008000",
                error="#cd3131",
                warning="#ff8800",
                muted="#6a6a6a",
                dim="#999999",
                text="",
                thinking_text="#6a6a6a",
                user_message_bg="#f3f3f3",
                user_message_text="",
                tool_pending_bg="#f5f5ff",
                tool_success_bg="#f0fff0",
                tool_error_bg="#fff0f0",
                tool_title="#0066cc",
                tool_output="#000000",
                md_heading="#0066cc",
                md_link="#0066cc",
                md_code="#a31515",
                md_code_block="#000000",
                md_code_block_border="#cccccc",
                md_quote="#6a6a6a",
                md_quote_border="#cccccc",
                syntax_comment="#008000",
                syntax_keyword="#0000ff",
                syntax_function="#795e26",
                syntax_variable="#001080",
                syntax_string="#a31515",
                syntax_number="#098658",
                syntax_type="#267f99",
                syntax_operator="#000000",
            ),
        )

        self._themes["dark"] = dark_theme
        self._themes["light"] = light_theme
        self._current_theme = dark_theme

    def load_theme_from_file(self, path: Path) -> Optional[Theme]:
        """
        Load a theme from a JSON file.

        Args:
            path: Path to theme file

        Returns:
            Theme object if successful, None otherwise
        """
        try:
            with open(path) as f:
                data = json.load(f)

            theme = Theme(**data)
            self._themes[theme.name] = theme
            return theme

        except Exception as e:
            logger.warning("Failed to load theme from %s: %s", path, e)
            print(f"⚠️  Failed to load theme from {path}: {e}")
            return None

    def load_themes_from_dir(self, directory: Path) -> int:
        """
        Load all theme files from a directory.

        Args:
            directory: Path to themes directory

        Returns:
            Number of themes loaded
        """
        if not directory.exists() or not directory.is_dir():
            return 0

        count = 0
        for theme_file in directory.glob("*.json"):
            if self.load_theme_from_file(theme_file):
                count += 1

        return count

    def load_default_themes(self) -> int:
        """
        Load themes from default locations:
        - ~/.basket/themes/
        - ./.basket/themes/

        Returns:
            Number of themes loaded
        """
        total = 0

        # User themes
        user_themes_dir = Path.home() / ".basket" / "themes"
        if user_themes_dir.exists():
            total += self.load_themes_from_dir(user_themes_dir)

        # Project themes
        project_themes_dir = Path.cwd() / ".basket" / "themes"
        if project_themes_dir.exists():
            total += self.load_themes_from_dir(project_themes_dir)

        return total

    def get_theme(self, name: str) -> Optional[Theme]:
        """
        Get a theme by name.

        Args:
            name: Theme name

        Returns:
            Theme object if found, None otherwise
        """
        return self._themes.get(name)

    def set_current_theme(self, name: str) -> bool:
        """
        Set the current theme.

        Args:
            name: Theme name

        Returns:
            True if theme was set, False if not found
        """
        theme = self._themes.get(name)
        if theme:
            self._current_theme = theme
            return True
        return False

    def get_current_theme(self) -> Optional[Theme]:
        """Get the current theme."""
        return self._current_theme

    def list_themes(self) -> List[str]:
        """Get list of available theme names."""
        return list(self._themes.keys())


__all__ = ["Theme", "ThemeColors", "ThemeManager"]

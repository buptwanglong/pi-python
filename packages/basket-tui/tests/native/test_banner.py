"""Tests for native TUI banner lines."""

import re

import pytest

from basket_tui.native.ui.banner import build_banner_lines, resolve_basket_version


def _strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m|\x1b\]8;;.*?\x1b\\", "", s)


def test_build_banner_contains_brand_version_tagline():
    lines = build_banner_lines("2026.3.2")
    assert len(lines) == 4
    plain = "\n".join(_strip_ansi(x) for x in lines)
    assert "Basket" in plain
    assert "2026.3.2" in plain
    assert "stop" in plain and "ship" in plain
    assert lines[2] == ""


def test_build_banner_uses_resolve_when_version_omitted():
    lines = build_banner_lines()
    assert len(lines) == 4
    v = resolve_basket_version()
    assert v in _strip_ansi(lines[1])


def test_build_banner_strips_unknown_version_falls_back():
    lines = build_banner_lines("   ")
    assert "Basket" in _strip_ansi(lines[0])
    assert resolve_basket_version() in _strip_ansi(lines[1])
    assert lines[2] == ""


def test_build_banner_brand_line_has_emphasis():
    """Brand line (Basket) has bold or stronger emphasis."""
    lines = build_banner_lines("1.0.0")
    assert len(lines) >= 1
    assert "Basket" in lines[0]
    # ANSI bold is SGR 1 (e.g. \x1b[1m)
    assert "\x1b[1m" in lines[0] or "1;" in lines[0]


def test_build_banner_tagline_has_indent_or_border():
    """Tagline line has visual indent or leading border character."""
    lines = build_banner_lines("1.0.0")
    tagline_line = [l for l in lines if "stop" in l or "ship" in l][0]
    stripped = re.sub(r"\x1b\[[0-9;]*m", "", tagline_line)
    assert stripped.startswith("  ") or stripped.startswith("│") or stripped.startswith("|")

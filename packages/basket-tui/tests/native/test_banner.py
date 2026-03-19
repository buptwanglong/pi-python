"""Tests for native TUI banner lines."""

import re

import pytest

from basket_tui.native.ui.banner import build_banner_lines, resolve_basket_version


def _strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m|\x1b\]8;;.*?\x1b\\", "", s)


def test_build_banner_contains_brand_version_tagline():
    lines = build_banner_lines("2026.3.2")
    assert len(lines) == 3
    plain = "\n".join(_strip_ansi(x) for x in lines)
    assert "Basket" in plain
    assert "2026.3.2" in plain
    assert "stop" in plain and "ship" in plain


def test_build_banner_uses_resolve_when_version_omitted():
    lines = build_banner_lines()
    assert len(lines) == 3
    v = resolve_basket_version()
    assert v in _strip_ansi(lines[1])


def test_build_banner_strips_unknown_version_falls_back():
    lines = build_banner_lines("   ")
    assert "Basket" in _strip_ansi(lines[0])
    assert resolve_basket_version() in _strip_ansi(lines[1])

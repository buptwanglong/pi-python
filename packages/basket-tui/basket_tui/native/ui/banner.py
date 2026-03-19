"""
Startup banner lines (ANSI) for terminal-native TUI.
"""

from __future__ import annotations

import importlib.metadata

# OpenClaw-style orange headline + lighter secondary (24-bit)
_ORANGE = "\x1b[38;2;255;90;45m"
_ORANGE_LIGHT = "\x1b[38;2;255;138;91m"
_GRAY = "\x1b[38;2;139;127;119m"
_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_DIM = "\x1b[2m"

_TAGLINE = (
    'Say "stop" and I\'ll stop—say "ship" and we\'ll both learn a lesson.'
)


def resolve_basket_version() -> str:
    """Return installed version string for ``basket-tui`` or ``basket-assistant``."""
    for dist in ("basket-tui", "basket-assistant"):
        try:
            return importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            continue
    return "0.0.0"


def build_banner_lines(version: str | None = None) -> list[str]:
    """
    Build 4-line ANSI banner: brand, version, blank, tagline.

    Args:
        version: Explicit version; if omitted, uses :func:`resolve_basket_version`.
    """
    v = (version or "").strip() or resolve_basket_version()
    return [
        f"{_ORANGE}{_BOLD}  Basket{_RESET}",
        f"{_DIM}{_GRAY}  version {v}{_RESET}",
        "",
        f"{_ORANGE_LIGHT}  │ {_TAGLINE}{_RESET}",
    ]

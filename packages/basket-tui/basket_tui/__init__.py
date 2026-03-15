"""
Basket TUI - Terminal-native TUI (line output + prompt_toolkit).

Provides run_tui_native_attach to connect to the gateway WebSocket and run
the terminal-native UI with slash commands and pickers.
"""

from .native.run import run_tui_native_attach

__version__ = "0.1.0"

__all__ = ["run_tui_native_attach"]

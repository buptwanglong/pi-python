"""
Modes for Pi Coding Agent

Different interaction modes:
- interactive: Basic CLI with print/input
- tui: Rich terminal UI with Textual
- rpc: JSON-RPC mode for IDE integration
"""

from .tui import run_tui_mode
from .attach import run_tui_mode_attach

__all__ = ["run_tui_mode", "run_tui_mode_attach"]

"""
Pi TUI - Terminal UI Framework for Pi Coding Agent

A Textual-based TUI framework for building interactive terminal applications
with support for:
- Markdown rendering with syntax highlighting
- Multi-line input with autocomplete
- Streaming LLM responses in real-time
- Tool execution display
- Theming and CSS styling
"""

from .app import PiCodingAgentApp

__version__ = "0.1.0"

__all__ = ["PiCodingAgentApp"]

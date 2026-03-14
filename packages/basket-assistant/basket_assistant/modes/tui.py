"""
Backward compatibility shim for modes.tui module.

DEPRECATED: Import from basket_assistant.interaction.modes.tui instead.

This module re-exports from the new interaction layer for backward compatibility.
"""

# Re-export everything from new location
from basket_assistant.interaction.modes.tui import TUIMode, format_tool_result

# Backward compatible function wrapper
async def run_tui_mode(coding_agent, max_cols=None):
    """DEPRECATED: Use TUIMode(coding_agent, max_columns=max_cols).run() instead."""
    mode = TUIMode(coding_agent, max_columns=max_cols)
    await mode.initialize()
    return await mode.run()

# Alias for old tests that use _format_tool_result
_format_tool_result = format_tool_result

__all__ = ["run_tui_mode", "format_tool_result", "_format_tool_result", "TUIMode"]

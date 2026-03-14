"""
Backward compatibility shim for modes package.

DEPRECATED: Import from basket_assistant.interaction.modes instead.

This module re-exports from the new interaction layer for backward compatibility.
Old code using `from basket_assistant.modes import ...` will still work.
"""

# Re-export from new location
from basket_assistant.interaction.modes.tui import TUIMode
from basket_assistant.interaction.modes.attach import AttachMode

# Backward compatible function wrappers
async def run_tui_mode(coding_agent, max_cols=None):
    """DEPRECATED: Use TUIMode(coding_agent).run() instead."""
    mode = TUIMode(coding_agent, max_cols=max_cols)
    return await mode.run()

async def run_tui_mode_attach(ws_url, agent_name=None, max_cols=None):
    """DEPRECATED: Use AttachMode(ws_url, agent_name, max_cols).run() instead."""
    mode = AttachMode(ws_url, agent_name=agent_name, max_cols=max_cols)
    return await mode.run()

# Also export the new format function if anything uses it
from basket_assistant.interaction.modes.tui import format_tool_result as _format_tool_result

__all__ = ["run_tui_mode", "run_tui_mode_attach", "TUIMode", "AttachMode", "_format_tool_result"]

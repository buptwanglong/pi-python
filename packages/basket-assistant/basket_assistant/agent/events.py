"""Agent event handlers — re-exports from focused modules.

Split into:
- _event_handlers.py: CLI/TUI display handlers
- _event_logging.py: Logging-only handlers
- _trajectory.py: Trajectory recording
- _assistant_events.py: Assistant-level event emission
"""

from ._event_handlers import setup_event_handlers, _tool_call_args_summary
from ._event_logging import setup_logging_handlers
from ._trajectory import (
    get_trajectory_dir,
    on_trajectory_event,
    ensure_trajectory_handlers,
    run_with_trajectory_if_enabled,
)
from ._assistant_events import emit_assistant_event, messages_for_hook_payload

__all__ = [
    "setup_event_handlers",
    "setup_logging_handlers",
    "emit_assistant_event",
    "messages_for_hook_payload",
    "get_trajectory_dir",
    "on_trajectory_event",
    "ensure_trajectory_handlers",
    "run_with_trajectory_if_enabled",
    "_tool_call_args_summary",
]

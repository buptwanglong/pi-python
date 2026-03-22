"""Subprocess hook runner and tool wrapping (hooks.json / settings.hooks)."""

from .hook_runner import (
    HOOK_ALIAS_MAP,
    HOOK_EXIT_DENY,
    HookDef,
    HookRunner,
    normalize_hook_event,
)
from .tool_hooks import wrap_tool_execute_with_hooks

__all__ = [
    "HOOK_ALIAS_MAP",
    "HOOK_EXIT_DENY",
    "HookDef",
    "HookRunner",
    "normalize_hook_event",
    "wrap_tool_execute_with_hooks",
]

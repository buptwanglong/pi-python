"""Declarative tool registry.

Each tool module registers a ToolDefinition at import time.
agent/tools.py collects all definitions and applies uniform wrapping
(hooks, guardrails, plan-mode) in a single loop.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from pydantic import BaseModel


@dataclass(frozen=True)
class ToolDefinition:
    """Metadata for a single tool. Each tool module exports one (or more)."""

    name: str
    description: str
    parameters: type[BaseModel]
    factory: Callable[[Any], Callable]  # AgentContext -> execute_fn
    plan_mode_blocked: bool = False
    description_factory: Optional[Callable[[Any], str]] = None  # ctx -> dynamic description


_TOOL_REGISTRY: List[ToolDefinition] = []


def register(defn: ToolDefinition) -> None:
    """Register a tool definition. Called at module import time."""
    _TOOL_REGISTRY.append(defn)


def get_all() -> List[ToolDefinition]:
    """Return a copy of all registered tool definitions."""
    return list(_TOOL_REGISTRY)


def clear() -> None:
    """Clear registry (for testing only)."""
    _TOOL_REGISTRY.clear()

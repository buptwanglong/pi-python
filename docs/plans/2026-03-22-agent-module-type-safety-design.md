# Agent Module Type Safety Refactoring Design

**Date:** 2026-03-22
**Status:** Implemented
**Scope:** `basket-assistant/basket_assistant/agent/` + callers (~15 files, ~90 sites)

## Problem

The `basket-assistant` agent module has pervasive type safety issues:

1. **`agent: Any` duck typing** — 22 functions across 6 files accept `agent: Any`, then access properties via direct attribute access or `getattr`. No compile-time type checking, no IDE autocompletion, no refactor safety.

2. **Defensive `getattr` on known types** — ~60 `getattr(obj, "attr", None)` calls on objects whose types are well-defined (Pydantic `Settings`, `SubAgentConfig`, `AssistantAgent`). These obscure the actual contract and bypass type checkers.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scope | agent/ + callers (~15 files) | Covers the core module and its immediate dependents without touching `basket-agent` package interfaces |
| Strategy for `agent: Any` | `typing.Protocol` | Structural subtyping; no inheritance needed; AssistantAgent automatically satisfies it |
| Protocol organization | Single Protocol | Only one implementation class exists; split Protocols would be over-engineering |
| `getattr` handling | Aggressive replacement | Settings and Agent properties are declared in Pydantic/Protocol; direct access is correct |

## Design

### 1. New File: `agent/_protocol.py`

Define `AssistantAgentProtocol` as a `typing.Protocol` class:

```python
"""Protocol defining the structural type contract for AssistantAgent.

All helper modules in agent/ (tools, events, prompts, session, gateway_slash)
and external callers (tools/task.py, commands/, etc.) should type their
agent parameter as AssistantAgentProtocol instead of Any.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable

from basket_agent import Agent
from basket_ai.types import Context, Model

from ..core.configuration.models import Settings
from ..core import SessionManager, AgentConfigResolver
from ..guardrails.engine import GuardrailEngine
from ..hooks import HookRunner


@runtime_checkable
class AssistantAgentProtocol(Protocol):
    """Structural type for AssistantAgent consumed by helper modules.

    Grouped by responsibility area. All attributes here are set in
    AssistantAgent.__init__ and are guaranteed present at runtime.
    """

    # ── Settings & Configuration ──
    settings: Settings
    settings_manager: Any  # SettingsManager (avoid circular)
    config_resolver: AgentConfigResolver
    agent_key: str

    # ── LLM & Agent Runtime ──
    model: Model
    context: Context
    agent: Agent
    _default_system_prompt: str

    # ── Session State ──
    session_manager: SessionManager
    _session_id: Optional[str]
    _current_todos: List[dict]
    _pending_asks: List[dict]

    # ── Tool & Plugin State ──
    _plan_mode: bool
    _plugin_loader: Any  # Optional[PluginLoader] — typed as Any to avoid coupling
    _guardrail_engine: Optional[GuardrailEngine]
    _assistant_event_handlers: Dict[str, List[Callable]]

    # ── Trajectory (set dynamically but always present after __init__) ──
    _trajectory_recorder: Optional[Any]
    _trajectory_handlers_registered: bool

    # ── Hooks ──
    hook_runner: HookRunner
```

### 2. File Change Summary

| File | Changes |
|------|---------|
| `agent/_protocol.py` | **NEW** — Protocol definition |
| `agent/__init__.py` | Replace ~4 `getattr` with direct access; add `_trajectory_handlers_registered = False` to `_setup_state` |
| `agent/tools.py` | 7× `agent: Any` → `AssistantAgentProtocol`; eliminate ~10 `getattr` |
| `agent/events.py` | 8× `agent: Any` → Protocol; eliminate ~8 `getattr` |
| `agent/prompts.py` | 4× `agent: Any`/`settings: Any` → concrete types; eliminate ~6 `getattr` |
| `agent/session.py` | 2× `agent: Any` → Protocol; eliminate ~3 `getattr` |
| `agent/gateway_slash.py` | 1× `agent: Any` → Protocol; eliminate ~4 `getattr` |
| `tools/task.py` | Eliminate ~4 `getattr`, type agent ref |
| `tools/todo_write.py` | Eliminate ~2 `getattr` |
| `tools/web_search.py` | Type `settings` parameter |
| `commands/builtin/model.py` | Eliminate ~7 `getattr` → `agent.model.xxx` |
| `commands/builtin/help.py` | Eliminate `getattr` |
| `commands/builtin/clear.py` | Eliminate `getattr` |
| `commands/builtin/compact.py` | Eliminate `getattr` |
| `interaction/modes/base.py` | Eliminate `getattr` |

### 3. getattr Classification

| Category | Action | Example |
|----------|--------|---------|
| Settings fields | Replace with direct access | `getattr(settings, "workspace_dir", None)` → `settings.workspace_dir` |
| AssistantAgent fields | Replace (Protocol declares them) | `getattr(agent, "hook_runner", None)` → `agent.hook_runner` |
| Message objects (Union types) | **Keep** — Union types need runtime checks | `getattr(msg, "role", None)` stays |
| SubAgentConfig fields | Replace (Pydantic declares them) | `getattr(cfg, "workspace_dir", None)` → `cfg.workspace_dir` |
| Dynamic path traversal | **Keep** | `core/settings_full.py` dynamic attribute paths |
| Test code | **Keep** — defensive checks on mocks are valid | `tests/test_coding_agent_integration.py` |

### 4. Invariants

- `AssistantAgent` class structure unchanged (no new base class)
- `basket-agent` package interfaces unchanged
- Runtime behavior identical (Protocol is type-check-only; `runtime_checkable` for optional assertions)
- All existing 200+ tests must continue passing

### 5. Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| `getattr` → direct access causes AttributeError | Medium | Protocol + `__init__` initialization order guarantee; test suite validates |
| Circular import from Protocol file | Low | Use `from __future__ import annotations` + `TYPE_CHECKING` where needed |
| Missing property in Protocol | Low | Comprehensive scan completed; any missed property caught by mypy |

### 6. Validation

- Run `poetry run pytest -v` in `packages/basket-assistant/`
- Run `poetry run mypy .` in `packages/basket-assistant/` (if configured)
- Manual check: no remaining `agent: Any` in agent/ module files
- Manual check: `getattr` count reduced from ~60 to ~10 (only message Union + dynamic paths + tests)

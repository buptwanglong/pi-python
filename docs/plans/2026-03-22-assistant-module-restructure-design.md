# basket-assistant Module Restructure Design

**Date:** 2026-03-22
**Status:** Approved
**Scope:** AgentContext interface + tool self-registration + God module splits + circular import fix

---

## Problem Statement

basket-assistant has 5 structural issues that make it hard to maintain:

1. **Tools access Agent private state** — `task.py`, `todo_write.py`, `skill.py` directly read/write `agent_ref._session_id`, `agent_ref._recent_tasks`, etc. The `_protocol.py` Protocol exposes these private attributes, creating a "public private API".
2. **tools.py is a coupling hub** (308 lines) — imports 7 `create_xxx_tool` functions eagerly, hand-codes registration for each tool with repeated wrap logic.
3. **main.py is monolithic** (532 lines) — 8 unrelated responsibilities (CLI parsing, gateway start/stop/status, remote, relay, TUI attach, init, agent management, interactive/one-shot run).
4. **settings_full.py is a god module** (434 lines) — 4 responsibilities (Pydantic models, SettingsManager, AgentConfigResolver, legacy migration).
5. **session_manager.py is a god module** (462 lines) — 5 responsibilities (JSONL I/O, message serialization, session management, todo persistence, pending ask persistence).
6. **publisher.py has a real circular import** — imports `AssistantAgent` (concrete) instead of `AssistantAgentProtocol` under TYPE_CHECKING. Removing the guard would cause `publisher -> agent/__init__ -> core -> publisher` cycle.

---

## Design

### 1. AgentContext Interface

Introduce `AgentContext` as the **only contract between tools and Agent**. Tools never receive the Agent object itself.

**New file: `agent/context.py`**

```python
from dataclasses import dataclass
from typing import Callable, Awaitable, Optional, List, Dict, Any

@dataclass(frozen=True)
class AgentContext:
    """Public contract between tools and Agent.
    Tools receive this; never the Agent itself.
    Only expose what tools genuinely need.
    """
    # Read-only state
    session_id: Optional[str]
    plan_mode: bool

    # Callbacks (tools call these, Agent implements them)
    run_subagent: Callable[[str, str], Awaitable[str]]
    get_subagent_configs: Callable[[], Dict[str, Any]]
    get_subagent_display_description: Callable[[str, Any], str]

    save_todos: Callable[[List[dict]], Awaitable[None]]
    save_pending_asks: Callable[[List[dict]], Awaitable[None]]

    append_recent_task: Callable[[dict], None]
    update_recent_task: Callable[[int, dict], None]
```

**Impact:** All tool `create_xxx_tool(agent_ref)` signatures change to `create_xxx_tool(ctx: AgentContext)`.

**_protocol.py simplification:** Remove all `_private` attributes that were only exposed for tools. Protocol keeps only what agent/ internal modules (events, prompts, session) need.

### 2. Declarative Tool Registration

Replace the coupling hub in `agent/tools.py` with a self-registration pattern.

**New file: `tools/_registry.py`**

```python
from dataclasses import dataclass
from typing import Callable, Any
from pydantic import BaseModel

@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: type[BaseModel]
    factory: Callable[[Any], Callable]  # AgentContext -> execute_fn
    plan_mode_blocked: bool = False

_TOOL_REGISTRY: list[ToolDefinition] = []

def register(defn: ToolDefinition) -> None:
    _TOOL_REGISTRY.append(defn)

def get_all() -> list[ToolDefinition]:
    return list(_TOOL_REGISTRY)
```

**Each tool self-registers at module bottom:**

```python
# tools/todo_write.py
register(ToolDefinition(
    name="todo_write",
    description="...",
    parameters=TodoWriteParams,
    factory=_make_execute,
    plan_mode_blocked=True,
))
```

**agent/tools.py simplifies to ~80 lines:** Uniform pipeline loop over `get_all()`, applying hooks -> guardrails -> plan_mode wrapping.

### 3. God Module Splits

#### 3a. main.py (532 lines) -> cli/ subpackage

```
basket_assistant/
├── cli/
│   ├── __init__.py          # main(), main_async() — routing only (~60 lines)
│   ├── parser.py            # Argument parsing logic (~80 lines)
│   ├── gateway_cmd.py       # basket gateway start/stop/status (~100 lines)
│   ├── agent_cmd.py         # basket agent list/add/remove (~100 lines)
│   ├── config_cmd.py        # basket init (~30 lines)
│   ├── remote_cmd.py        # basket --remote (~30 lines)
│   ├── relay_cmd.py         # basket relay (~30 lines)
│   └── run_cmd.py           # Interactive + one-shot + TUI attach (~60 lines)
```

`main.py` becomes a thin re-export: `from .cli import main, main_async`.

#### 3b. settings_full.py (434 lines) -> core/settings/ subpackage

```
core/settings/
├── __init__.py              # Re-exports
├── models.py                # Pydantic: Settings, ModelSettings, AgentSettings, etc. (~120 lines)
├── manager.py               # SettingsManager (~80 lines)
├── resolver.py              # AgentConfigResolver (~80 lines)
├── migration.py             # migrate_legacy_to_agents, load_settings (~60 lines)
```

#### 3c. session_manager.py (462 lines) -> core/session/ subpackage

```
core/session/
├── __init__.py              # Re-exports
├── models.py                # SessionEntry, SessionMetadata (~60 lines)
├── serialization.py         # message_to_entry_data, entry_data_to_message (~50 lines)
├── store.py                 # JSONL I/O: append_entry, read_entries (~80 lines)
├── manager.py               # SessionManager high-level API (~150 lines)
```

**Backward compatibility:** All `__init__.py` files re-export public names so existing `from ..core import Settings, SettingsManager, SessionManager` continue to work.

### 4. Circular Import Fix + Import Rules

#### 4a. publisher.py fix

```python
# BEFORE (circular)
if TYPE_CHECKING:
    from basket_assistant.agent import AssistantAgent

# AFTER (safe)
if TYPE_CHECKING:
    from basket_assistant.agent._protocol import AssistantAgentProtocol
```

#### 4b. Import rules (enforced by convention + documented)

```
# IMPORT RULES (basket-assistant)
#
# 1. tools/*.py -> only import AgentContext (from agent.context), never AssistantAgent
# 2. agent/ internal modules -> use AssistantAgentProtocol (from ._protocol)
# 3. Never import AssistantAgent concrete class in TYPE_CHECKING (only agent/__init__.py can)
# 4. core/ never imports agent/ (one-way dependency: agent -> core)
```

---

## Module Dependency Topology (After)

```
TIER 5: cli/ (routing only, ~60 lines)
  |
TIER 4: AssistantAgent (agent/__init__.py, slimmed)
  |-- agent/tools.py (uniform registration pipeline, ~80 lines)
  |-- agent/events.py (unchanged, well-split)
  |-- agent/prompts.py (unchanged)
  |-- agent/session.py (unchanged)
  |-- agent/context.py (NEW: AgentContext dataclass)
  |
TIER 3: Core Services
  |-- core/settings/ (split from settings_full.py)
  |-- core/session/ (split from session_manager.py)
  |-- core/events/publisher.py (fixed: uses Protocol)
  |
TIER 2: Safety & Hooks (unchanged)
  |-- guardrails/
  |-- hooks/
  |
TIER 1: Data + Tools
  |-- tools/ (each self-registers, depends only on AgentContext)
  |-- tools/_registry.py (NEW: ToolDefinition + registry)
  |-- core/messages.py
```

---

## Non-Goals

- Not changing basket-agent or basket-ai packages
- Not changing the event system (already refactored recently)
- Not changing the interaction modes (cli/tui)
- Not adding new features, just restructuring existing code

---

## Risk Mitigation

- **Backward-compatible re-exports**: `core/__init__.py` re-exports from split subpackages
- **Test-driven**: Run existing tests after each phase to catch regressions
- **Incremental phases**: Can be done in 4 independent phases (context, registry, splits, fix)

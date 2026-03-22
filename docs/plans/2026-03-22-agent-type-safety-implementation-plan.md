# Agent Module Type Safety Refactoring — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate ~90 `Any` type annotations and defensive `getattr` calls across the basket-assistant agent module by introducing a `typing.Protocol` and using direct attribute access.

**Architecture:** Create a single `AssistantAgentProtocol` in `agent/_protocol.py` that declares all attributes accessed by helper modules. Change all `agent: Any` signatures to use the Protocol. Replace `getattr(obj, "known_field", default)` with direct `obj.known_field` access for Pydantic models and Protocol-declared types.

**Tech Stack:** Python 3.12, typing.Protocol, Pydantic v2, pytest, pytest-asyncio

---

### Task 1: Create AssistantAgentProtocol

**Files:**
- Create: `packages/basket-assistant/basket_assistant/agent/_protocol.py`

**Step 1: Write the Protocol file**

```python
"""Protocol defining the structural type contract for AssistantAgent.

All helper modules in agent/ (tools, events, prompts, session, gateway_slash)
and external callers (tools/task.py, commands/, etc.) should type their
agent parameter as AssistantAgentProtocol instead of Any.
"""
from __future__ import annotations

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
    settings_manager: Any  # SettingsManager — avoid circular
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
    _recent_tasks: Optional[List[dict]]

    # ── Tool & Plugin State ──
    _plan_mode: bool
    _plugin_loader: Any  # Optional[PluginLoader] — typed as Any to avoid coupling
    _guardrail_engine: Optional[GuardrailEngine]
    _assistant_event_handlers: Dict[str, List[Callable]]
    _todo_show_full: bool

    # ── Trajectory ──
    _trajectory_recorder: Optional[Any]
    _trajectory_handlers_registered: bool

    # ── Hooks ──
    hook_runner: HookRunner
```

**Step 2: Verify import works**

Run: `cd packages/basket-assistant && poetry run python -c "from basket_assistant.agent._protocol import AssistantAgentProtocol; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add packages/basket-assistant/basket_assistant/agent/_protocol.py
git commit -m "feat: add AssistantAgentProtocol for type-safe agent parameter passing"
```

---

### Task 2: Fix AssistantAgent.__init__ — add missing attributes for Protocol conformance

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/agent/__init__.py`

**Step 1: Add `_trajectory_handlers_registered` and `_trajectory_recorder` to `_setup_state()`**

In `_setup_state()`, after the `_assistant_event_handlers` line, add:

```python
self._trajectory_recorder: Optional[Any] = None
self._trajectory_handlers_registered: bool = False
```

**Step 2: Replace `getattr` with direct access in `__init__`**

Replace in `__init__`:
```python
# OLD
settings_hooks = getattr(self.settings, "hooks", None) or {}
```
The `Settings` Pydantic model does NOT have a `hooks` field. Check if `hooks` is defined in `settings_full.py`.

> **IMPORTANT:** If `Settings` does not define `hooks`, this `getattr` is genuinely needed (defensive for optional/dynamic field). In that case, keep it but add a `# type: ignore[attr-defined]` comment. Verify by reading `settings_full.py`.

In `_setup_state()`, replace:
```python
# OLD
getattr(self.settings.permissions, "default_mode", "default") == "plan"
# NEW
self.settings.permissions.default_mode == "plan"
```

```python
# OLD
workspace_dir = getattr(self.settings, "workspace_dir", None)
# NEW
workspace_dir = self.settings.workspace_dir
```

```python
# OLD
guardrails_enabled = getattr(self.settings, "guardrails_enabled", True)
```
> Check if `guardrails_enabled` exists on Settings. If NOT, keep the `getattr` with comment.

**Step 3: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_coding_agent_integration.py tests/test_settings.py -v --tb=short`
Expected: All PASS

**Step 4: Commit**

```bash
git add packages/basket-assistant/basket_assistant/agent/__init__.py
git commit -m "refactor: replace getattr with direct access in AssistantAgent.__init__"
```

---

### Task 3: Refactor `agent/prompts.py` — typed signatures, eliminate getattr

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/agent/prompts.py`

**Step 1: Replace imports**

```python
# OLD
from typing import Any, Dict, List, Optional

# NEW
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from ._protocol import AssistantAgentProtocol

from ..core import Settings, SubAgentConfig, get_skill_full_content, load_agents_from_dirs
```

**Step 2: Replace function signatures and getattr calls**

`get_subagent_configs`:
```python
# OLD
def get_subagent_configs(agent: Any) -> Dict[str, SubAgentConfig]:
    ...
    default_agent = getattr(agent.settings, "default_agent", None)

# NEW
def get_subagent_configs(agent: AssistantAgentProtocol) -> Dict[str, SubAgentConfig]:
    ...
    default_agent = agent.settings.default_agent
```

`get_skills_dirs`:
```python
# OLD
def get_skills_dirs(settings: Any, ...) -> List[Path]:

# NEW
def get_skills_dirs(settings: Settings, ...) -> List[Path]:
```

`_resolve_main_agent_workspace_dir`:
```python
# OLD
def _resolve_main_agent_workspace_dir(settings: Any) -> Optional[Path]:
    default_agent = getattr(settings, "default_agent", None)
    agents = getattr(settings, "agents", None) or {}
    ...
    raw = getattr(cfg, "workspace_dir", None)

# NEW
def _resolve_main_agent_workspace_dir(settings: Settings) -> Optional[Path]:
    default_agent = settings.default_agent
    agents = settings.agents
    ...
    raw = cfg.workspace_dir
```

`get_system_prompt_base`:
```python
# OLD
def get_system_prompt_base(settings: Optional[Any] = None) -> str:
    if getattr(settings, "skip_bootstrap", False):

# NEW
def get_system_prompt_base(settings: Optional[Settings] = None) -> str:
    if getattr(settings, "skip_bootstrap", False):  # keep: skip_bootstrap may not be on Settings
```

`get_system_prompt_for_run`:
```python
# OLD
def get_system_prompt_for_run(agent: Any, ...) -> str:

# NEW
def get_system_prompt_for_run(agent: AssistantAgentProtocol, ...) -> str:
```

**Step 3: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_prompts_workspace.py tests/test_prompts_skills_paths.py -v --tb=short`
Expected: All PASS

**Step 4: Commit**

```bash
git add packages/basket-assistant/basket_assistant/agent/prompts.py
git commit -m "refactor: type prompts.py — replace Any with Settings/Protocol, eliminate getattr"
```

---

### Task 4: Refactor `agent/tools.py` — typed signatures, eliminate getattr

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/agent/tools.py`

**Step 1: Replace imports**

```python
# OLD
from typing import Any, Dict, List

# NEW
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from ._protocol import AssistantAgentProtocol
```

**Step 2: Replace all 7 `agent: Any` signatures**

Every function gets `agent: AssistantAgentProtocol`:
- `_get_plugin_skill_dirs(agent: AssistantAgentProtocol)`
- `get_registerable_tools(agent: AssistantAgentProtocol)`
- `filter_tools_for_subagent(agent: AssistantAgentProtocol, cfg: SubAgentConfig)`
- `get_subagent_display_description(agent: AssistantAgentProtocol, name: str, cfg: SubAgentConfig)`
- `_resolve_subagent_workspace_path(agent: AssistantAgentProtocol, ...)`
- `run_subagent(agent: AssistantAgentProtocol, ...)`
- `wrap_tool_with_hooks(agent: AssistantAgentProtocol, ...)`
- `register_tools(agent: AssistantAgentProtocol)`

**Step 3: Replace getattr calls**

```python
# OLD: _get_plugin_skill_dirs
loader = getattr(agent, "_plugin_loader", None)
# NEW
loader = agent._plugin_loader

# OLD: _resolve_subagent_workspace_path
raw = getattr(cfg, "workspace_dir", None)
agent_dir_raw = getattr(cfg, "agent_dir", None)
# NEW
raw = cfg.workspace_dir
agent_dir_raw = cfg.agent_dir

# OLD: run_subagent (message traversal lines 184-188) — KEEP getattr on msg objects (Union type)

# OLD: wrap_tool_with_hooks
runner = getattr(agent, "hook_runner", None)
# NEW
runner = agent.hook_runner

# OLD: register_tools
engine = getattr(agent, "_guardrail_engine", None)
# NEW
engine = agent._guardrail_engine
```

**Step 4: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_coding_agent_integration.py tests/test_task_tool.py tests/test_skill_tool.py -v --tb=short`
Expected: All PASS

**Step 5: Commit**

```bash
git add packages/basket-assistant/basket_assistant/agent/tools.py
git commit -m "refactor: type tools.py — replace Any with Protocol, eliminate getattr on known types"
```

---

### Task 5: Refactor `agent/events.py` — typed signatures, eliminate getattr

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/agent/events.py`

**Step 1: Replace imports**

```python
# OLD
from typing import Any, Dict, List, Optional

# NEW
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from ._protocol import AssistantAgentProtocol
```

**Step 2: Replace all 8 `agent: Any` signatures with `agent: AssistantAgentProtocol`**

Functions: `setup_event_handlers`, `setup_logging_handlers`, `emit_assistant_event`, `messages_for_hook_payload`, `get_trajectory_dir`, `on_trajectory_event`, `ensure_trajectory_handlers`, `run_with_trajectory_if_enabled`.

**Step 3: Replace getattr calls**

```python
# OLD: ensure_trajectory_handlers
if getattr(agent, "_trajectory_handlers_registered", False):
# NEW
if agent._trajectory_handlers_registered:

# OLD: on_trajectory_event
recorder = getattr(agent, "_trajectory_recorder", None)
# NEW
recorder = agent._trajectory_recorder

# OLD: messages_for_hook_payload — KEEP getattr on msg (Union type)
# getattr(msg, "role", None) — KEEP
# getattr(msg, "content", None) — KEEP

# OLD: run_with_trajectory_if_enabled — KEEP getattr on msg (Union type)
# getattr(msg, "role", None) — KEEP
# getattr(msg, "content", "") — KEEP
```

**Step 4: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_coding_agent_integration.py tests/test_hook_runner.py -v --tb=short`
Expected: All PASS

**Step 5: Commit**

```bash
git add packages/basket-assistant/basket_assistant/agent/events.py
git commit -m "refactor: type events.py — replace Any with Protocol, eliminate getattr on known types"
```

---

### Task 6: Refactor `agent/session.py` — typed signatures, eliminate getattr

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/agent/session.py`

**Step 1: Replace imports and signatures**

```python
# OLD
from typing import Any, Optional

# NEW
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ._protocol import AssistantAgentProtocol
```

Replace both functions:
- `set_session_id(agent: AssistantAgentProtocol, ...)`
- `try_resume_pending_ask(agent: AssistantAgentProtocol, ...)`

**Step 2: Replace getattr calls**

```python
# OLD: set_session_id
hook_runner = getattr(agent, "hook_runner", None)
# NEW
hook_runner = agent.hook_runner

# OLD: try_resume_pending_ask — KEEP getattr on msg (Union type)
# getattr(msg, "role", None) — KEEP
# getattr(msg, "tool_call_id", None) — KEEP
```

**Step 3: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_session_manager.py tests/test_coding_agent_integration.py -v --tb=short`
Expected: All PASS

**Step 4: Commit**

```bash
git add packages/basket-assistant/basket_assistant/agent/session.py
git commit -m "refactor: type session.py — replace Any with Protocol, direct hook_runner access"
```

---

### Task 7: Refactor `agent/gateway_slash.py` — typed signature, eliminate getattr

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/agent/gateway_slash.py`

**Step 1: Replace imports and signature**

```python
# OLD
from typing import Any, Awaitable, Callable, List, Optional, Tuple

# NEW
from __future__ import annotations
from typing import TYPE_CHECKING, Awaitable, Callable, List, Optional, Tuple

if TYPE_CHECKING:
    from ._protocol import AssistantAgentProtocol
```

Replace: `try_process_gateway_slash(agent: AssistantAgentProtocol, ...)`

**Step 2: Replace getattr calls**

```python
# OLD
old_sink = getattr(agent, "_plugin_install_progress_sink", None)
# This field is NOT on Protocol (dynamically set). Keep getattr.

# OLD
pl = getattr(agent, "_plugin_loader", None)
# NEW
pl = agent._plugin_loader

# OLD
getter = getattr(pl, "get_all_commands_dirs", None)
# Keep — pl is typed as Any in Protocol, so getattr is appropriate here.
```

**Step 3: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_gateway_slash.py -v --tb=short`
Expected: All PASS

**Step 4: Commit**

```bash
git add packages/basket-assistant/basket_assistant/agent/gateway_slash.py
git commit -m "refactor: type gateway_slash.py — replace Any with Protocol"
```

---

### Task 8: Refactor caller `tools/task.py` — eliminate getattr

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/tools/task.py`

**Step 1: Replace imports and signatures**

```python
# OLD
from typing import Any, List

# NEW
from __future__ import annotations
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ..agent._protocol import AssistantAgentProtocol
```

Replace:
- `create_task_tool(agent_ref: AssistantAgentProtocol)`
- `create_parallel_task_tool(agent_ref: AssistantAgentProtocol)`

**Step 2: Replace getattr calls**

```python
# OLD
desc = getattr(agent_ref, "get_subagent_display_description", None)
label = (desc(name, cfg) if callable(desc) else (getattr(cfg, "description", "") or name)).strip() or name
# NEW
label = agent_ref.get_subagent_display_description(name, cfg)

# OLD
parent_session_id = getattr(agent_ref, "_session_id", None)
# NEW
parent_session_id = agent_ref._session_id

# OLD
recent = getattr(agent_ref, "_recent_tasks", None)
# NEW
recent = agent_ref._recent_tasks
```

> **NOTE:** `get_subagent_display_description` needs to be added to the Protocol. Add it as a method signature:
> ```python
> def get_subagent_display_description(self, name: str, cfg: Any) -> str: ...
> ```
> Also add `_get_subagent_configs` and `run_subagent` method signatures to Protocol if called.

**Step 3: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_task_tool.py tests/test_parallel_task.py -v --tb=short`
Expected: All PASS

**Step 4: Commit**

```bash
git add packages/basket-assistant/basket_assistant/tools/task.py packages/basket-assistant/basket_assistant/agent/_protocol.py
git commit -m "refactor: type task.py — replace Any with Protocol, eliminate getattr"
```

---

### Task 9: Refactor caller `tools/todo_write.py` — eliminate getattr

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/tools/todo_write.py`

**Step 1: Replace imports and signature**

```python
# OLD
from typing import Any, List, Literal

# NEW
from __future__ import annotations
from typing import TYPE_CHECKING, Any, List, Literal

if TYPE_CHECKING:
    from ..agent._protocol import AssistantAgentProtocol
```

Replace: `create_todo_write_tool(agent_ref: AssistantAgentProtocol)`

**Step 2: Replace getattr calls**

```python
# OLD
session_id = getattr(agent_ref, "_session_id", None)
if session_id and getattr(agent_ref, "session_manager", None):
# NEW
session_id = agent_ref._session_id
if session_id and agent_ref.session_manager:
```

**Step 3: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_todo_write.py -v --tb=short`
Expected: All PASS

**Step 4: Commit**

```bash
git add packages/basket-assistant/basket_assistant/tools/todo_write.py
git commit -m "refactor: type todo_write.py — replace Any with Protocol, eliminate getattr"
```

---

### Task 10: Refactor caller `tools/web_search.py` — type settings parameter

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/tools/web_search.py`

**Step 1: Replace imports and signature**

```python
# OLD
from typing import Any, Optional

# NEW
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..core.configuration.models import Settings
```

Replace: `create_web_search_tool(settings: Settings)`

**Step 2: Replace getattr**

```python
# OLD
provider = (getattr(settings, "web_search_provider", None) or "").strip().lower()
# NEW
provider = (settings.web_search_provider or "").strip().lower()
```

**Step 3: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_web_search.py -v --tb=short`
Expected: All PASS

**Step 4: Commit**

```bash
git add packages/basket-assistant/basket_assistant/tools/web_search.py
git commit -m "refactor: type web_search.py — replace Any with Settings, eliminate getattr"
```

---

### Task 11: Refactor `commands/builtin/model.py` — eliminate getattr on Model

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/commands/builtin/model.py`

**Step 1: Replace imports and signature**

```python
# OLD
from typing import TYPE_CHECKING, Any

# NEW
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from basket_assistant.agent._protocol import AssistantAgentProtocol
    from basket_assistant.commands.registry import CommandRegistry
```

Replace:
- `handle_model(agent: AssistantAgentProtocol, ...)`
- `register(registry: CommandRegistry, agent: AssistantAgentProtocol)`

**Step 2: Replace ALL getattr on `agent.model`**

`agent.model` is `Model` (Pydantic) — all fields are declared.

```python
# OLD
provider = getattr(model, "provider", "unknown")
model_id = getattr(model, "model_id", getattr(model, "id", "unknown"))
ctx_window = getattr(model, "context_window", "unknown")
# NEW
provider = agent.model.provider
model_id = agent.model.model_id
ctx_window = agent.model.context_window

# OLD
context_window = getattr(agent.model, "context_window", 128_000)
max_tokens = getattr(agent.model, "max_tokens", 4096)
base_url = getattr(agent.model, "base_url", None) or getattr(agent.model, "baseUrl", None)
# NEW
context_window = agent.model.context_window
max_tokens = agent.model.max_tokens
base_url = agent.model.base_url

# OLD
old_provider = getattr(agent.model, "provider", "unknown")
old_model_id = getattr(agent.model, "model_id", getattr(agent.model, "id", "unknown"))
# NEW
old_provider = agent.model.provider
old_model_id = agent.model.model_id
```

**Step 3: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/commands/ -v --tb=short`
Expected: All PASS

**Step 4: Commit**

```bash
git add packages/basket-assistant/basket_assistant/commands/builtin/model.py
git commit -m "refactor: type model.py — replace 7 getattr(model, ...) with direct Model access"
```

---

### Task 12: Refactor remaining commands — help, clear, compact, plugin, skill_save

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/commands/builtin/help.py`
- Modify: `packages/basket-assistant/basket_assistant/commands/builtin/clear.py`
- Modify: `packages/basket-assistant/basket_assistant/commands/builtin/compact.py`
- Modify: `packages/basket-assistant/basket_assistant/commands/builtin/plugin.py`
- Modify: `packages/basket-assistant/basket_assistant/commands/builtin/skill_save.py`

**Step 1: For each file, add Protocol import and replace `agent: Any`**

All 5 files follow same pattern:

```python
# ADD
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from basket_assistant.agent._protocol import AssistantAgentProtocol

# REPLACE
def handle_xxx(agent: Any, ...) → handle_xxx(agent: AssistantAgentProtocol, ...)
def register(registry: CommandRegistry, agent: Any) → register(registry: CommandRegistry, agent: AssistantAgentProtocol)
```

**Step 2: Replace specific getattr calls**

**help.py:**
```python
# OLD
index = getattr(agent, "_slash_commands_index", None) or {}
# Keep — _slash_commands_index is dynamically set by InteractionMode, not in Protocol
```

**clear.py:**
```python
# OLD
model_id = getattr(agent.model, "model_id", "")
# NEW
model_id = agent.model.model_id
```

**compact.py:**
```python
# OLD
context_window = getattr(agent.model, "context_window", 128_000)
# NEW
context_window = agent.model.context_window
```

**plugin.py:**
```python
# OLD
progress_sink = getattr(agent, "_plugin_install_progress_sink", None)
# Keep — dynamically set, not in Protocol
```

**skill_save.py:**
```python
# OLD
draft = getattr(agent, "_pending_skill_draft", None)
# Keep — dynamically set, not in Protocol
```

**Step 3: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/commands/ -v --tb=short`
Expected: All PASS

**Step 4: Commit**

```bash
git add packages/basket-assistant/basket_assistant/commands/builtin/help.py \
       packages/basket-assistant/basket_assistant/commands/builtin/clear.py \
       packages/basket-assistant/basket_assistant/commands/builtin/compact.py \
       packages/basket-assistant/basket_assistant/commands/builtin/plugin.py \
       packages/basket-assistant/basket_assistant/commands/builtin/skill_save.py
git commit -m "refactor: type command handlers — replace Any with Protocol, eliminate getattr on Model"
```

---

### Task 13: Refactor `interaction/modes/base.py` — typed signature, eliminate getattr

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/interaction/modes/base.py`

**Step 1: Replace imports and constructor signature**

```python
# OLD
from typing import Any, List, Optional, Tuple

# NEW
from __future__ import annotations
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

if TYPE_CHECKING:
    from basket_assistant.agent._protocol import AssistantAgentProtocol
```

Replace: `def __init__(self, agent: AssistantAgentProtocol) -> None:`

**Step 2: Replace getattr calls**

```python
# OLD
pl = getattr(agent, "_plugin_loader", None)
if pl is not None:
    getter = getattr(pl, "get_all_commands_dirs", None)
    if callable(getter):
        out = getter()
        if isinstance(out, list):
            plugin_cmd_dirs = out

# NEW (partially — _plugin_loader is Any in Protocol, so keep getter check)
pl = agent._plugin_loader
if pl is not None:
    getter = getattr(pl, "get_all_commands_dirs", None)
    if callable(getter):
        out = getter()
        if isinstance(out, list):
            plugin_cmd_dirs = out
```

**Step 3: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/interaction/modes/ -v --tb=short`
Expected: All PASS

**Step 4: Commit**

```bash
git add packages/basket-assistant/basket_assistant/interaction/modes/base.py
git commit -m "refactor: type base.py — replace Any with Protocol in InteractionMode"
```

---

### Task 14: Full test suite validation

**Files:**
- None (verification only)

**Step 1: Run full test suite**

Run: `cd packages/basket-assistant && poetry run pytest -v --tb=short 2>&1 | tail -30`
Expected: All tests PASS, no regressions

**Step 2: Count remaining `Any` in agent module**

Run: `grep -rn "agent: Any" packages/basket-assistant/basket_assistant/agent/ | grep -v __pycache__`
Expected: 0 matches (none remaining in agent/ module)

**Step 3: Count remaining `getattr` in source (exclude tests)**

Run: `grep -rn "getattr" packages/basket-assistant/basket_assistant/ --include="*.py" | grep -v __pycache__ | wc -l`
Expected: ~10-15 remaining (message Union types, dynamic fields, settings_full.py path traversal)

**Step 4: Commit (if any fixes needed)**

No commit if all passes. If fixes needed, fix and commit with:
```bash
git commit -m "fix: address test failures from type safety refactoring"
```

---

### Task 15: Final commit — update design doc status

**Files:**
- Modify: `docs/plans/2026-03-22-agent-module-type-safety-design.md`

**Step 1: Update status**

Change `**Status:** Approved` to `**Status:** Implemented`

**Step 2: Commit**

```bash
git add docs/plans/2026-03-22-agent-module-type-safety-design.md
git commit -m "docs: mark agent type safety design as implemented"
```

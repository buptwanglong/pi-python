# basket-assistant Module Restructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restructure basket-assistant to eliminate circular imports, decouple tools from Agent internals via AgentContext, introduce declarative tool registration, and split 3 god modules into focused subpackages.

**Architecture:** Four independent phases executed sequentially. Phase 1 introduces AgentContext as the tool-Agent boundary. Phase 2 adds declarative tool registry. Phase 3 splits god modules. Phase 4 fixes the one real circular import and documents import rules. Each phase is independently testable.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest + pytest-asyncio, Poetry monorepo

---

## Phase 1: AgentContext Interface (decouple tools from Agent)

### Task 1: Create AgentContext dataclass

**Files:**
- Create: `packages/basket-assistant/basket_assistant/agent/context.py`
- Test: `packages/basket-assistant/tests/test_agent_context.py`

**Step 1: Write the failing test**

```python
# tests/test_agent_context.py
"""Tests for AgentContext — the public contract between tools and Agent."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from basket_assistant.agent.context import AgentContext


def test_agent_context_is_frozen():
    """AgentContext should be immutable (frozen dataclass)."""
    ctx = AgentContext(
        session_id="test-session",
        plan_mode=False,
        run_subagent=AsyncMock(),
        get_subagent_configs=MagicMock(return_value={}),
        get_subagent_display_description=MagicMock(return_value="desc"),
        save_todos=AsyncMock(),
        save_pending_asks=AsyncMock(),
        append_recent_task=MagicMock(),
        update_recent_task=MagicMock(),
        settings=MagicMock(),
    )
    with pytest.raises(AttributeError):
        ctx.session_id = "changed"


def test_agent_context_fields_accessible():
    """All declared fields should be accessible."""
    mock_settings = MagicMock()
    ctx = AgentContext(
        session_id="s1",
        plan_mode=True,
        run_subagent=AsyncMock(),
        get_subagent_configs=MagicMock(return_value={"explore": {}}),
        get_subagent_display_description=MagicMock(return_value="Explorer"),
        save_todos=AsyncMock(),
        save_pending_asks=AsyncMock(),
        append_recent_task=MagicMock(),
        update_recent_task=MagicMock(),
        settings=mock_settings,
    )
    assert ctx.session_id == "s1"
    assert ctx.plan_mode is True
    assert ctx.get_subagent_configs() == {"explore": {}}
    assert ctx.settings is mock_settings


def test_agent_context_none_session_id():
    """session_id can be None (no active session)."""
    ctx = AgentContext(
        session_id=None,
        plan_mode=False,
        run_subagent=AsyncMock(),
        get_subagent_configs=MagicMock(return_value={}),
        get_subagent_display_description=MagicMock(return_value=""),
        save_todos=AsyncMock(),
        save_pending_asks=AsyncMock(),
        append_recent_task=MagicMock(),
        update_recent_task=MagicMock(),
        settings=MagicMock(),
    )
    assert ctx.session_id is None
```

**Step 2: Run test to verify it fails**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_agent_context.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'basket_assistant.agent.context'`

**Step 3: Write minimal implementation**

```python
# basket_assistant/agent/context.py
"""AgentContext: public contract between tools and Agent.

Tools receive an AgentContext instance — never the Agent itself.
This decouples tools from Agent internals and makes the boundary explicit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional


@dataclass(frozen=True)
class AgentContext:
    """Immutable context provided to tool factory functions.

    Only exposes what tools genuinely need. Agent implements
    the callbacks; tools call them without knowing Agent internals.
    """

    # ── Read-only state ──
    session_id: Optional[str]
    plan_mode: bool
    settings: Any  # Settings — typed as Any to avoid coupling

    # ── Callbacks (tools call these, Agent implements them) ──
    run_subagent: Callable[[str, str], Awaitable[str]]
    get_subagent_configs: Callable[[], Dict[str, Any]]
    get_subagent_display_description: Callable[[str, Any], str]

    save_todos: Callable[[List[dict]], Awaitable[None]]
    save_pending_asks: Callable[[List[dict]], Awaitable[None]]

    append_recent_task: Callable[[dict], None]
    update_recent_task: Callable[[int, dict], None]
```

**Step 4: Run test to verify it passes**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_agent_context.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add packages/basket-assistant/basket_assistant/agent/context.py packages/basket-assistant/tests/test_agent_context.py
git commit -m "feat: add AgentContext dataclass — tool-Agent boundary contract"
```

---

### Task 2: Add `build_tool_context()` method to AssistantAgent

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/agent/__init__.py`
- Test: `packages/basket-assistant/tests/test_agent_context.py` (append)

**Step 1: Write the failing test**

Append to `tests/test_agent_context.py`:

```python
@pytest.mark.asyncio
async def test_assistant_agent_build_tool_context(mock_coding_agent):
    """AssistantAgent.build_tool_context() returns a valid AgentContext."""
    agent = await mock_coding_agent
    ctx = agent.build_tool_context()

    assert isinstance(ctx, AgentContext)
    assert ctx.session_id == agent._session_id
    assert ctx.plan_mode == agent._plan_mode
    assert ctx.settings is agent.settings
    assert callable(ctx.run_subagent)
    assert callable(ctx.get_subagent_configs)
    assert callable(ctx.save_todos)
    assert callable(ctx.append_recent_task)
```

**Step 2: Run test to verify it fails**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_agent_context.py::test_assistant_agent_build_tool_context -v`
Expected: FAIL with `AttributeError: 'AssistantAgent' object has no attribute 'build_tool_context'`

**Step 3: Write minimal implementation**

Add to `basket_assistant/agent/__init__.py` inside `AssistantAgent` class (after `_setup_state`):

```python
    def build_tool_context(self) -> "AgentContext":
        """Build an AgentContext snapshot for tool factory functions.

        Returns a frozen dataclass exposing only what tools need.
        Called once during register_tools(); tools keep the reference.
        """
        from .context import AgentContext

        async def _save_todos(todos: list) -> None:
            self._current_todos = todos
            if self._session_id and self.session_manager:
                await self.session_manager.save_todos(self._session_id, todos)

        async def _save_pending_asks(asks: list) -> None:
            self._pending_asks = asks
            if self._session_id and self.session_manager:
                await self.session_manager.save_pending_asks(self._session_id, asks)

        def _append_recent_task(record: dict) -> None:
            self._recent_tasks.append(record)

        def _update_recent_task(index: int, updates: dict) -> None:
            if 0 <= index < len(self._recent_tasks):
                self._recent_tasks[index].update(updates)

        return AgentContext(
            session_id=self._session_id,
            plan_mode=self._plan_mode,
            settings=self.settings,
            run_subagent=self.run_subagent,
            get_subagent_configs=self._get_subagent_configs,
            get_subagent_display_description=self.get_subagent_display_description,
            save_todos=_save_todos,
            save_pending_asks=_save_pending_asks,
            append_recent_task=_append_recent_task,
            update_recent_task=_update_recent_task,
        )
```

Add import at top of file: `from .context import AgentContext`

**Step 4: Run test to verify it passes**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_agent_context.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add packages/basket-assistant/basket_assistant/agent/__init__.py packages/basket-assistant/tests/test_agent_context.py
git commit -m "feat: add build_tool_context() to AssistantAgent"
```

---

### Task 3: Migrate `todo_write.py` to use AgentContext

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/tools/todo_write.py`
- Modify: `packages/basket-assistant/tests/test_todo_write.py`

**Step 1: Update test to use AgentContext**

Read `tests/test_todo_write.py` first. Then update the test fixtures to use `AgentContext` instead of MagicMock agent_ref:

```python
# Replace agent_ref fixtures with AgentContext fixtures
from basket_assistant.agent.context import AgentContext
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def tool_context():
    saved_todos = []
    async def save_todos(todos):
        saved_todos.clear()
        saved_todos.extend(todos)
    ctx = AgentContext(
        session_id="test-session",
        plan_mode=False,
        run_subagent=AsyncMock(),
        get_subagent_configs=MagicMock(return_value={}),
        get_subagent_display_description=MagicMock(return_value=""),
        save_todos=save_todos,
        save_pending_asks=AsyncMock(),
        append_recent_task=MagicMock(),
        update_recent_task=MagicMock(),
        settings=MagicMock(),
    )
    return ctx, saved_todos
```

**Step 2: Run test to verify it fails**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_todo_write.py -v`
Expected: FAIL (signature mismatch or attribute errors)

**Step 3: Update todo_write.py to use AgentContext**

```python
# tools/todo_write.py — UPDATED
from __future__ import annotations

from typing import Any, List, Literal

from pydantic import BaseModel, Field

TodoStatus = Literal["pending", "in_progress", "completed", "cancelled"]


class TodoItem(BaseModel):
    id: str | None = Field(None, description="Optional unique id for the task")
    content: str = Field(..., description="Task description")
    status: TodoStatus = Field(..., description="Current state: pending, in_progress, completed, or cancelled")


class TodoWriteParams(BaseModel):
    todos: List[TodoItem] = Field(..., description="Full list of tasks. Each call replaces the entire list.")


def create_todo_write_tool(ctx) -> dict:
    """Create the todo_write tool.

    Args:
        ctx: AgentContext with session_id and save_todos callback.
    """
    description = (
        "Create or update the structured task list for the current session. "
        "Each call replaces the entire list. Use to track progress on multi-step tasks.\n\n"
        "When to use: complex multi-step tasks (3+ steps), non-trivial tasks, user asks for a todo list, "
        "user provides multiple tasks, after new instructions or after completing a step, or when starting a new task (mark as in_progress). "
        "Prefer at most one task in_progress at a time.\n\n"
        "When NOT to use: single straightforward task, trivial task, completable in fewer than 3 steps, or purely conversational requests.\n\n"
        "Parameter: todos = full list of items, each with id (optional), content, status (pending|in_progress|completed|cancelled)."
    )

    async def execute_todo_write(todos: List[Any]) -> str:
        if not isinstance(todos, list):
            return "Error: todos must be a list."
        serialized = []
        for item in todos:
            if isinstance(item, TodoItem):
                serialized.append(item.model_dump())
            elif isinstance(item, dict):
                serialized.append({
                    "id": item.get("id"),
                    "content": item.get("content", ""),
                    "status": item.get("status", "pending"),
                })
            else:
                serialized.append({"id": None, "content": str(item), "status": "pending"})
        await ctx.save_todos(serialized)
        n = len(serialized)
        return f"Todo list updated ({n} item{'s' if n != 1 else ''})."

    return {
        "name": "todo_write",
        "description": description,
        "parameters": TodoWriteParams,
        "execute_fn": execute_todo_write,
    }


__all__ = ["TodoItem", "TodoStatus", "TodoWriteParams", "create_todo_write_tool"]
```

**Step 4: Run test to verify it passes**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_todo_write.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/basket-assistant/basket_assistant/tools/todo_write.py packages/basket-assistant/tests/test_todo_write.py
git commit -m "refactor: migrate todo_write tool to use AgentContext"
```

---

### Task 4: Migrate `task.py` and `dag_task.py` to use AgentContext

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/tools/task.py`
- Modify: `packages/basket-assistant/basket_assistant/tools/dag_task.py`
- Modify: `packages/basket-assistant/tests/test_task_tool.py`
- Modify: `packages/basket-assistant/tests/test_parallel_task.py`

**Step 1: Update task.py**

Replace all `agent_ref: AssistantAgentProtocol` with `ctx` (AgentContext). Key changes:

- `agent_ref._get_subagent_configs()` → `ctx.get_subagent_configs()`
- `agent_ref.get_subagent_display_description(name, cfg)` → `ctx.get_subagent_display_description(name, cfg)`
- `agent_ref._session_id` → `ctx.session_id`
- `agent_ref._recent_tasks.append(...)` → `ctx.append_recent_task(...)`
- `recent[-1]["status"] = "completed"` → `ctx.update_recent_task(-1, {"status": "completed", ...})`
- `await agent_ref.run_subagent(...)` → `await ctx.run_subagent(...)`

Remove `TYPE_CHECKING` import of `AssistantAgentProtocol`.

**Step 2: Update dag_task.py**

Replace `agent_ref: Any` with `ctx`. Only change:
- `await agent_ref.run_subagent(...)` → `await ctx.run_subagent(...)`

**Step 3: Update tests**

Update `test_task_tool.py` and `test_parallel_task.py` fixtures to use `AgentContext` instead of MagicMock with `_get_subagent_configs`, `_session_id`, `_recent_tasks`.

**Step 4: Run all tool tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_task_tool.py tests/test_parallel_task.py tests/test_orchestration/ -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/basket-assistant/basket_assistant/tools/task.py packages/basket-assistant/basket_assistant/tools/dag_task.py packages/basket-assistant/tests/test_task_tool.py packages/basket-assistant/tests/test_parallel_task.py
git commit -m "refactor: migrate task and dag_task tools to use AgentContext"
```

---

### Task 5: Migrate `ask_user_question.py` and update `agent/tools.py` to pass AgentContext

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/tools/ask_user_question.py`
- Modify: `packages/basket-assistant/basket_assistant/agent/tools.py`
- Modify: `packages/basket-assistant/basket_assistant/agent/__init__.py`

**Step 1: Update ask_user_question.py**

Change `create_ask_user_question_tool(agent_ref: Any)` → `create_ask_user_question_tool(ctx)`. Since it currently doesn't use `agent_ref`, this is just a signature change.

**Step 2: Update agent/tools.py — pass ctx to factory functions**

In `register_tools()`, add `ctx = agent.build_tool_context()` at the top, then pass `ctx` to all factory calls:

```python
def register_tools(agent: AssistantAgentProtocol) -> None:
    ctx = agent.build_tool_context()
    # ... existing wrapping logic ...
    # Change: create_todo_write_tool(agent) → create_todo_write_tool(ctx)
    # Change: create_task_tool(agent) → create_task_tool(ctx)
    # Change: create_ask_user_question_tool(agent) → create_ask_user_question_tool(ctx)
    # Note: create_skill_tool and create_web_search_tool don't use agent_ref, keep as-is
```

Also update `get_registerable_tools()` and `filter_tools_for_subagent()` similarly.

**Step 3: Run full test suite**

Run: `cd packages/basket-assistant && poetry run pytest tests/ -v --timeout=60`
Expected: PASS (all existing tests still pass)

**Step 4: Commit**

```bash
git add packages/basket-assistant/basket_assistant/tools/ask_user_question.py packages/basket-assistant/basket_assistant/agent/tools.py packages/basket-assistant/basket_assistant/agent/__init__.py
git commit -m "refactor: wire AgentContext through tool registration pipeline"
```

---

### Task 6: Clean up `_protocol.py` — remove tool-only attributes

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/agent/_protocol.py`

**Step 1: Remove attributes that are now only accessed via AgentContext**

Remove from Protocol:
- `_current_todos` (tools use `ctx.save_todos`)
- `_pending_asks` (tools use `ctx.save_pending_asks`)
- `_recent_tasks` (tools use `ctx.append_recent_task` / `ctx.update_recent_task`)

Keep (still needed by agent/ internal modules: session.py, events.py, prompts.py):
- `_session_id`, `_plan_mode`, `_default_system_prompt`, `_plugin_loader`
- `_guardrail_engine`, `_todo_show_full`
- All methods

Add `build_tool_context` method signature to Protocol.

**Step 2: Run full test suite**

Run: `cd packages/basket-assistant && poetry run pytest tests/ -v --timeout=60`
Expected: PASS

**Step 3: Commit**

```bash
git add packages/basket-assistant/basket_assistant/agent/_protocol.py
git commit -m "refactor: slim down AssistantAgentProtocol — remove tool-only attributes"
```

---

## Phase 2: Declarative Tool Registry

### Task 7: Create ToolDefinition and registry

**Files:**
- Create: `packages/basket-assistant/basket_assistant/tools/_registry.py`
- Test: `packages/basket-assistant/tests/test_tool_registry.py`

**Step 1: Write the failing test**

```python
# tests/test_tool_registry.py
"""Tests for declarative tool registry."""

import pytest
from pydantic import BaseModel, Field

from basket_assistant.tools._registry import ToolDefinition, register, get_all, clear


class DummyParams(BaseModel):
    text: str = Field(..., description="Input text")


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear registry before each test."""
    clear()
    yield
    clear()


def test_register_and_get_all():
    defn = ToolDefinition(
        name="dummy",
        description="A dummy tool",
        parameters=DummyParams,
        factory=lambda ctx: (lambda **kw: "ok"),
    )
    register(defn)
    all_tools = get_all()
    assert len(all_tools) == 1
    assert all_tools[0].name == "dummy"


def test_get_all_returns_copy():
    """Mutations to returned list should not affect registry."""
    defn = ToolDefinition(
        name="dummy",
        description="A dummy tool",
        parameters=DummyParams,
        factory=lambda ctx: (lambda **kw: "ok"),
    )
    register(defn)
    result = get_all()
    result.clear()
    assert len(get_all()) == 1


def test_plan_mode_blocked_default_false():
    defn = ToolDefinition(
        name="dummy",
        description="A dummy tool",
        parameters=DummyParams,
        factory=lambda ctx: (lambda **kw: "ok"),
    )
    assert defn.plan_mode_blocked is False


def test_plan_mode_blocked_true():
    defn = ToolDefinition(
        name="dummy",
        description="A dummy tool",
        parameters=DummyParams,
        factory=lambda ctx: (lambda **kw: "ok"),
        plan_mode_blocked=True,
    )
    assert defn.plan_mode_blocked is True
```

**Step 2: Run test to verify it fails**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_tool_registry.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# tools/_registry.py
"""Declarative tool registry.

Each tool module registers a ToolDefinition at import time.
agent/tools.py collects all definitions and applies uniform wrapping.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List

from pydantic import BaseModel


@dataclass(frozen=True)
class ToolDefinition:
    """Metadata for a single tool. Each tool module exports one."""

    name: str
    description: str
    parameters: type[BaseModel]
    factory: Callable[[Any], Callable]  # AgentContext -> execute_fn
    plan_mode_blocked: bool = False


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
```

**Step 4: Run test to verify it passes**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_tool_registry.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add packages/basket-assistant/basket_assistant/tools/_registry.py packages/basket-assistant/tests/test_tool_registry.py
git commit -m "feat: add declarative ToolDefinition registry"
```

---

### Task 8: Convert static tools to self-registering

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/tools/read.py`
- Modify: `packages/basket-assistant/basket_assistant/tools/write.py`
- Modify: `packages/basket-assistant/basket_assistant/tools/edit.py`
- Modify: `packages/basket-assistant/basket_assistant/tools/bash.py`
- Modify: `packages/basket-assistant/basket_assistant/tools/grep.py`
- Modify: `packages/basket-assistant/basket_assistant/tools/web_fetch.py`

**Step 1: Add self-registration to each static tool**

For each file, append at the bottom (example for read.py):

```python
# ── Self-registration ──
from ._registry import ToolDefinition, register

register(ToolDefinition(
    name=READ_TOOL["name"],
    description=READ_TOOL["description"],
    parameters=ReadParams,
    factory=lambda ctx: read_file,  # Static tools ignore ctx
))
```

Repeat for write, edit, bash, grep, web_fetch. For write/edit/bash, set `plan_mode_blocked=True`.

**Step 2: Run existing tool tests to ensure no regressions**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_read_tool.py tests/test_write_tool.py tests/test_edit_tool.py tests/test_bash_tool.py tests/test_grep_tool.py tests/test_web_fetch.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add packages/basket-assistant/basket_assistant/tools/read.py packages/basket-assistant/basket_assistant/tools/write.py packages/basket-assistant/basket_assistant/tools/edit.py packages/basket-assistant/basket_assistant/tools/bash.py packages/basket-assistant/basket_assistant/tools/grep.py packages/basket-assistant/basket_assistant/tools/web_fetch.py
git commit -m "refactor: static tools self-register via ToolDefinition"
```

---

### Task 9: Convert factory tools to self-registering

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/tools/todo_write.py`
- Modify: `packages/basket-assistant/basket_assistant/tools/task.py`
- Modify: `packages/basket-assistant/basket_assistant/tools/ask_user_question.py`
- Modify: `packages/basket-assistant/basket_assistant/tools/web_search.py`
- Modify: `packages/basket-assistant/basket_assistant/tools/skill.py`
- Modify: `packages/basket-assistant/basket_assistant/tools/dag_task.py`

**Step 1: Add self-registration to factory tools**

These tools produce their descriptions dynamically (e.g., task.py builds description from subagent list). The registry `factory` callback receives `ctx` and returns the execute function. Description can be built inside the factory:

```python
# Example for todo_write.py (append at bottom)
from ._registry import ToolDefinition, register

def _make_todo_write(ctx):
    tool = create_todo_write_tool(ctx)
    return tool["execute_fn"]

register(ToolDefinition(
    name="todo_write",
    description=TodoWriteParams.__doc__ or "...",  # Static fallback
    parameters=TodoWriteParams,
    factory=_make_todo_write,
    plan_mode_blocked=True,
))
```

**Note:** For tools with dynamic descriptions (task.py, skill.py), we need a `description_factory` or the factory returns both. Extend ToolDefinition:

```python
@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str  # Static fallback
    parameters: type[BaseModel]
    factory: Callable[[Any], Callable]
    plan_mode_blocked: bool = False
    description_factory: Callable[[Any], str] | None = None  # ctx -> dynamic description
```

**Step 2: Run all tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/ -v --timeout=60`
Expected: PASS

**Step 3: Commit**

```bash
git add packages/basket-assistant/basket_assistant/tools/
git commit -m "refactor: factory tools self-register via ToolDefinition"
```

---

### Task 10: Simplify `agent/tools.py` to use registry

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/agent/tools.py`
- Modify: `packages/basket-assistant/basket_assistant/tools/__init__.py`

**Step 1: Rewrite `register_tools()` to loop over registry**

```python
# agent/tools.py — SIMPLIFIED (~80 lines)
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..guardrails.engine import GuardrailEngine
from ..hooks.tool_hooks import wrap_tool_execute_with_hooks
from ..tools._registry import get_all

if TYPE_CHECKING:
    from ._protocol import AssistantAgentProtocol

PLAN_MODE_FORBIDDEN_TOOLS = frozenset({"write", "edit", "bash", "todo_write"})
PLAN_MODE_DISABLED_MESSAGE = (
    "Plan mode is on. This action is disabled. Only analysis and planning are allowed."
)


def _wrap_for_plan_mode(fn, get_plan_mode):
    async def wrapped(**kwargs):
        if get_plan_mode():
            return PLAN_MODE_DISABLED_MESSAGE
        return await fn(**kwargs)
    return wrapped


def _wrap_for_guardrails(fn, engine: GuardrailEngine, tool_name: str):
    async def wrapped(**kwargs):
        result = engine.evaluate(tool_name, kwargs)
        if not result.allowed:
            return f"⛔ Guardrail blocked: {result.message}"
        return await fn(**kwargs)
    return wrapped


def wrap_tool_with_hooks(agent, name: str, execute_fn):
    runner = agent.hook_runner
    if runner is None:
        return execute_fn
    return wrap_tool_execute_with_hooks(name, execute_fn, runner, get_cwd=lambda: Path.cwd())


def register_tools(agent: AssistantAgentProtocol) -> None:
    """Register all tools from the declarative registry."""
    # Ensure all tool modules are imported (triggers self-registration)
    import basket_assistant.tools  # noqa: F401

    ctx = agent.build_tool_context()
    get_plan = lambda: agent._plan_mode
    engine = agent._guardrail_engine

    for defn in get_all():
        fn = defn.factory(ctx)

        # Build dynamic description if available
        desc = defn.description
        if defn.description_factory:
            desc = defn.description_factory(ctx)

        # Wrapping pipeline: plan_mode → guardrails → hooks → original
        fn = wrap_tool_with_hooks(agent, defn.name, fn)
        if engine is not None:
            fn = _wrap_for_guardrails(fn, engine, defn.name)
        if defn.plan_mode_blocked or defn.name in PLAN_MODE_FORBIDDEN_TOOLS:
            fn = _wrap_for_plan_mode(fn, get_plan)

        agent.agent.register_tool(
            name=defn.name,
            description=desc,
            parameters=defn.parameters,
            execute_fn=fn,
        )
```

**Step 2: Update `tools/__init__.py` to import all tool modules (triggering registration)**

Keep `BUILT_IN_TOOLS` and `__all__` for backward compatibility, but the primary registration path is now the registry.

**Step 3: Run full test suite**

Run: `cd packages/basket-assistant && poetry run pytest tests/ -v --timeout=60`
Expected: PASS

**Step 4: Remove subagent-related functions that moved to tools or ctx**

Move `run_subagent()`, `get_registerable_tools()`, `filter_tools_for_subagent()`, `get_subagent_display_description()` into standalone module or keep in `agent/tools.py` as thin wrappers.

**Step 5: Commit**

```bash
git add packages/basket-assistant/basket_assistant/agent/tools.py packages/basket-assistant/basket_assistant/tools/__init__.py
git commit -m "refactor: agent/tools.py uses declarative registry — uniform pipeline"
```

---

## Phase 3: God Module Splits

### Task 11: Split `settings_full.py` into `core/settings/` subpackage

**Files:**
- Create: `packages/basket-assistant/basket_assistant/core/settings/__init__.py`
- Create: `packages/basket-assistant/basket_assistant/core/settings/models.py`
- Create: `packages/basket-assistant/basket_assistant/core/settings/manager.py`
- Create: `packages/basket-assistant/basket_assistant/core/settings/resolver.py`
- Create: `packages/basket-assistant/basket_assistant/core/settings/migration.py`
- Remove: `packages/basket-assistant/basket_assistant/core/settings_full.py` (after re-exports work)
- Modify: `packages/basket-assistant/basket_assistant/core/__init__.py`

**Step 1: Create `settings/models.py`**

Move these from `settings_full.py`:
- `AgentConfig` class (lines 26-44)
- `ModelSettings` class (lines 85-96)
- `AgentSettings` class (lines 98-103)
- `PermissionsSettings` class (lines 106-109)
- `SubAgentConfig` class (lines 112-128)
- `Settings` class (lines 131-168)
- `DEFAULT_TRAJECTORY_DIR` constant

**Step 2: Create `settings/manager.py`**

Move `SettingsManager` class (lines 369-435).

**Step 3: Create `settings/resolver.py`**

Move `AgentConfigResolver` class (lines 224-307).

**Step 4: Create `settings/migration.py`**

Move `migrate_legacy_to_agents()`, `resolve_agent_config()`, `load_settings()` functions (lines 47-361).

**Step 5: Create `settings/__init__.py` with re-exports**

```python
from .models import (
    AgentConfig, AgentSettings, ModelSettings, PermissionsSettings,
    Settings, SubAgentConfig, DEFAULT_TRAJECTORY_DIR,
)
from .manager import SettingsManager
from .resolver import AgentConfigResolver
from .migration import load_settings, migrate_legacy_to_agents, resolve_agent_config

__all__ = [
    "AgentConfig", "AgentSettings", "ModelSettings", "PermissionsSettings",
    "Settings", "SubAgentConfig", "DEFAULT_TRAJECTORY_DIR",
    "SettingsManager", "AgentConfigResolver",
    "load_settings", "migrate_legacy_to_agents", "resolve_agent_config",
]
```

**Step 6: Update `core/__init__.py`**

Change `from .settings_full import ...` to `from .settings import ...`.

**Step 7: Run settings tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_settings.py tests/test_settings_multi_agent.py tests/core/configuration/ -v`
Expected: PASS

**Step 8: Delete `settings_full.py`**

Only after all tests pass.

**Step 9: Commit**

```bash
git add packages/basket-assistant/basket_assistant/core/settings/ packages/basket-assistant/basket_assistant/core/__init__.py
git rm packages/basket-assistant/basket_assistant/core/settings_full.py
git commit -m "refactor: split settings_full.py into core/settings/ subpackage"
```

---

### Task 12: Split `session_manager.py` into `core/session/` subpackage

**Files:**
- Create: `packages/basket-assistant/basket_assistant/core/session/__init__.py`
- Create: `packages/basket-assistant/basket_assistant/core/session/models.py`
- Create: `packages/basket-assistant/basket_assistant/core/session/serialization.py`
- Create: `packages/basket-assistant/basket_assistant/core/session/store.py`
- Create: `packages/basket-assistant/basket_assistant/core/session/manager.py`
- Remove: `packages/basket-assistant/basket_assistant/core/session_manager.py`
- Modify: `packages/basket-assistant/basket_assistant/core/__init__.py`

**Step 1: Create `session/models.py`**

Move: `SessionEntry`, `SessionMetadata`, `_sanitize_agent_name` from `session_manager.py`.

**Step 2: Create `session/serialization.py`**

Move: `message_to_entry_data`, `entry_data_to_message`, `entry_data_to_message_safe` (currently static methods on SessionManager).

**Step 3: Create `session/store.py`**

Move low-level JSONL I/O: `append_entry`, `read_entries`, path helpers (`_get_session_path`, `_get_todos_path`, `_get_pending_ask_path`). This becomes a `SessionStore` class or standalone functions.

**Step 4: Create `session/manager.py`**

Keep `SessionManager` as the high-level API, but it delegates to store and serialization modules. Include: `create_session`, `ensure_session`, `list_sessions`, `delete_session`, `append_messages`, `load_messages`, `update_metadata`, `save_todos`, `load_todos`, `save_pending_asks`, `load_pending_asks`.

**Step 5: Create `session/__init__.py` with re-exports**

```python
from .models import SessionEntry, SessionMetadata
from .manager import SessionManager

__all__ = ["SessionEntry", "SessionMetadata", "SessionManager"]
```

**Step 6: Update `core/__init__.py`**

Change `from .session_manager import ...` to `from .session import ...`.

**Step 7: Run session tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_session_manager.py -v`
Expected: PASS

**Step 8: Delete `session_manager.py`**

Only after all tests pass.

**Step 9: Commit**

```bash
git add packages/basket-assistant/basket_assistant/core/session/ packages/basket-assistant/basket_assistant/core/__init__.py
git rm packages/basket-assistant/basket_assistant/core/session_manager.py
git commit -m "refactor: split session_manager.py into core/session/ subpackage"
```

---

### Task 13: Split `main.py` into `cli/` subpackage

**Files:**
- Create: `packages/basket-assistant/basket_assistant/cli/__init__.py`
- Create: `packages/basket-assistant/basket_assistant/cli/parser.py`
- Create: `packages/basket-assistant/basket_assistant/cli/gateway_cmd.py`
- Create: `packages/basket-assistant/basket_assistant/cli/agent_cmd.py`
- Create: `packages/basket-assistant/basket_assistant/cli/config_cmd.py`
- Create: `packages/basket-assistant/basket_assistant/cli/remote_cmd.py`
- Create: `packages/basket-assistant/basket_assistant/cli/relay_cmd.py`
- Create: `packages/basket-assistant/basket_assistant/cli/run_cmd.py`
- Modify: `packages/basket-assistant/basket_assistant/main.py` (thin wrapper)

**Step 1: Create `cli/parser.py`**

Extract argument parsing into a `ParsedArgs` dataclass and `parse_args()` function. Include all flag parsing (--debug, --plan, --session, --remote, --bind, --port, --agent, --max-cols, --live-rows, etc.).

```python
@dataclass
class ParsedArgs:
    command: str  # "init", "agent", "gateway", "remote", "relay", "tui", "tui-native", "run", "once", "help", "version"
    debug: bool = False
    plan_mode: bool = False
    session_id: str | None = None
    # ... all other flags
    remaining_args: list[str] = field(default_factory=list)
```

**Step 2: Create each command module**

Each module exports an `async def run(parsed: ParsedArgs) -> int` function containing the logic currently in `main_async()`.

**Step 3: Create `cli/__init__.py` as router**

```python
async def main_async(args=None):
    parsed = parse_args(args)
    setup_logging(parsed)
    match parsed.command:
        case "help": ...
        case "version": ...
        case "init": return await config_cmd.run(parsed)
        # ... etc
```

**Step 4: Update `main.py` to delegate**

```python
# main.py — thin wrapper for backward compatibility
from .cli import main, main_async  # noqa: F401

if __name__ == "__main__":
    import sys
    sys.exit(main())
```

**Step 5: Run CLI tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_agent_cli.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add packages/basket-assistant/basket_assistant/cli/ packages/basket-assistant/basket_assistant/main.py
git commit -m "refactor: split main.py into cli/ subpackage with command routing"
```

---

## Phase 4: Circular Import Fix + Import Rules

### Task 14: Fix publisher.py circular import

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/core/events/publisher.py`

**Step 1: Update import**

```python
# BEFORE
if TYPE_CHECKING:
    from basket_assistant.agent import AssistantAgent

# AFTER
if TYPE_CHECKING:
    from basket_assistant.agent._protocol import AssistantAgentProtocol
```

Update type annotation: `def __init__(self, agent: AssistantAgent)` → `def __init__(self, agent: AssistantAgentProtocol)`

**Step 2: Run publisher tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/core/events/test_publisher.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add packages/basket-assistant/basket_assistant/core/events/publisher.py
git commit -m "fix: publisher.py uses Protocol instead of concrete AssistantAgent — eliminates circular import"
```

---

### Task 15: Add import rules documentation and verify full test suite

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/agent/_protocol.py` (add docstring with rules)
- Modify: `CLAUDE.md` (add import rules section)

**Step 1: Add import rules to `_protocol.py` docstring**

```python
"""Protocol defining the structural type contract for AssistantAgent.

IMPORT RULES (basket-assistant):
1. tools/*.py → only import AgentContext (from agent.context), never AssistantAgent
2. agent/ internal modules → use AssistantAgentProtocol (from ._protocol)
3. Never import AssistantAgent in TYPE_CHECKING (only agent/__init__.py can)
4. core/ never imports agent/ (one-way dependency: agent → core)
"""
```

**Step 2: Run FULL test suite**

Run: `cd packages/basket-assistant && poetry run pytest tests/ -v --timeout=120`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add packages/basket-assistant/basket_assistant/agent/_protocol.py CLAUDE.md
git commit -m "docs: add import rules to prevent future circular dependencies"
```

---

### Task 16: Final verification — import cycle check

**Files:** None (verification only)

**Step 1: Verify no import cycles at runtime**

```bash
cd packages/basket-assistant
python -c "from basket_assistant.agent import AssistantAgent; print('OK: no import cycle')"
python -c "from basket_assistant.core.events.publisher import EventPublisher; print('OK: publisher imports clean')"
python -c "from basket_assistant.tools._registry import get_all; print(f'OK: {len(get_all())} tools registered')"
```

**Step 2: Run full test suite one final time**

Run: `cd packages/basket-assistant && poetry run pytest tests/ -v --timeout=120`
Expected: ALL PASS

**Step 3: Final commit with summary**

```bash
git commit --allow-empty -m "chore: basket-assistant module restructure complete

Phase 1: AgentContext interface (tools decoupled from Agent internals)
Phase 2: Declarative tool registry (self-registering ToolDefinition)
Phase 3: God module splits (main.py→cli/, settings→settings/, session→session/)
Phase 4: Circular import fix (publisher.py) + import rules"
```

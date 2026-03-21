# Phase 2 Extensibility Alignment: /model + BASKET.md + Hook Naming

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the three P1 gaps from the extensibility gap analysis: `/model` runtime model switching, `BASKET.md` project instruction files (CLAUDE.md equivalent), and hook event naming unification with Claude Code.

**Architecture:** `/model` creates a new Model object via `get_model()` and swaps it into both `AssistantAgent.model` and `Agent.model`. BASKET.md is loaded from `.basket/BASKET.md` (project) and `~/.basket/BASKET.md` (user), injected as the first section in `compose_system_prompt_from_workspace()`. Hook naming adds `PreToolUse`/`PostToolUse`/`Stop`/`Notification` as aliases for existing `tool.execute.before`/`tool.execute.after` event names, with backward compatibility.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest + pytest-asyncio

---

## Feature A: `/model` Runtime Model Switch

### Task 1: Write failing tests for `/model` command handler

**Files:**
- Modify: `packages/basket-assistant/tests/interaction/commands/test_handlers.py`

**Step 1: Write the failing tests**

Add `MockModelForSwitch` class after `MockModelWithWindow` (around line 97):

```python
class MockModelForSwitch:
    """Mock model with all attributes needed for /model switch."""

    def __init__(self, provider="anthropic", model_id="claude-sonnet-4", context_window=128000):
        self.provider = provider
        self.model_id = model_id
        self.context_window = context_window
```

Update `MockSettings` to include `api_keys` (add after line 41):

```python
class MockSettings:
    def __init__(self):
        self.model = MockModel()
        self.agent = MockAgentSettings()
        self.workspace_dir = "/home/user/.basket/workspace"
        self.api_keys = {}

    def to_dict(self):
        return {
            "model": {
                "provider": "anthropic",
                "model_id": "claude-sonnet-4",
            },
            "agent": {
                "max_turns": 25,
                "auto_save": True,
            },
            "workspace_dir": self.workspace_dir,
        }
```

Add `MockAgentInner` class to simulate `agent.agent` (the inner basket_agent.Agent):

```python
class MockAgentInner:
    """Mock inner Agent (basket_agent.Agent) for model switch tests."""

    def __init__(self, model):
        self.model = model
```

Update `MockAgent.__init__` to include `self.agent` (inner agent):

```python
class MockAgent:
    def __init__(self):
        self.settings = MockSettings()
        self.session_manager = MockSessionManager()
        self.model = MockModel()
        self._todo_show_full = False
        self.plan_mode = False
        self.conversation = []
        self.context = MockContext()
        self._current_todos = []
        self._pending_asks = []
        self._session_id = None
        self.agent = MockAgentInner(self.model)  # inner Agent
```

Add to `TestBuiltinCommandHandlers`:

```python
@pytest.mark.asyncio
async def test_handle_model_switch_success(self):
    """Test /model switches model successfully."""
    agent = MockAgent()
    agent.model = MockModelForSwitch(provider="anthropic", model_id="old-model")
    agent.agent = MockAgentInner(agent.model)
    handlers = BuiltinCommandHandlers(agent)

    success, error = await handlers.handle_model("openai/gpt-4o")

    assert success is True
    assert error == ""
    assert agent.model.model_id == "gpt-4o"
    assert agent.model.provider == "openai"
    # Inner agent model should also be updated
    assert agent.agent.model.model_id == "gpt-4o"

@pytest.mark.asyncio
async def test_handle_model_no_args_shows_current(self):
    """Test /model with no args shows current model."""
    agent = MockAgent()
    handlers = BuiltinCommandHandlers(agent)

    success, error = await handlers.handle_model("")

    assert success is True
    assert error == ""

@pytest.mark.asyncio
async def test_handle_model_invalid_format(self):
    """Test /model with invalid format returns error."""
    agent = MockAgent()
    handlers = BuiltinCommandHandlers(agent)

    success, error = await handlers.handle_model("invalid")

    assert success is False
    assert "Usage:" in error

@pytest.mark.asyncio
async def test_handle_model_with_context_window(self):
    """Test /model with context_window override."""
    agent = MockAgent()
    agent.model = MockModelForSwitch()
    agent.agent = MockAgentInner(agent.model)
    handlers = BuiltinCommandHandlers(agent)

    success, error = await handlers.handle_model("openai/gpt-4o --context-window 64000")

    assert success is True
    assert agent.model.context_window == 64000
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/basket-assistant && poetry run pytest tests/interaction/commands/test_handlers.py -v -k "model"`
Expected: FAIL — `AttributeError: 'BuiltinCommandHandlers' has no attribute 'handle_model'`

**Step 3: Commit**

```bash
git add packages/basket-assistant/tests/interaction/commands/test_handlers.py
git commit -m "test: add failing tests for /model command handler"
```

---

### Task 2: Implement `/model` command handler

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/interaction/commands/handlers.py:1-9` (add import)
- Modify: `packages/basket-assistant/basket_assistant/interaction/commands/handlers.py:163-209` (add handler after handle_compact)

**Step 1: Add `handle_model` method to `BuiltinCommandHandlers`**

Add after `handle_compact` (after line 208):

```python
async def handle_model(self, args: str) -> tuple[bool, str]:
    """Handle /model command — show current model or switch to a new one.

    Format: /model <provider>/<model_id> [--context-window <int>]
    Example: /model openai/gpt-4o
             /model anthropic/claude-sonnet-4 --context-window 200000

    Args:
        args: Command arguments (provider/model_id or empty to show current)

    Returns:
        Tuple of (success, error_message)
    """
    args = args.strip()

    # No args: show current model
    if not args:
        model = self.agent.model
        provider = getattr(model, "provider", "unknown")
        model_id = getattr(model, "model_id", "unknown")
        ctx_window = getattr(model, "context_window", "unknown")
        print(f"Current model: {provider}/{model_id} (context_window={ctx_window})")
        return True, ""

    # Parse args: provider/model_id [--context-window N]
    parts = args.split()
    model_spec = parts[0]

    if "/" not in model_spec:
        return False, (
            "Usage: /model <provider>/<model_id> [--context-window <int>]\n"
            "Example: /model openai/gpt-4o"
        )

    provider, model_id = model_spec.split("/", 1)
    if not provider or not model_id:
        return False, (
            "Usage: /model <provider>/<model_id> [--context-window <int>]\n"
            "Example: /model openai/gpt-4o"
        )

    # Parse optional flags
    context_window = getattr(self.agent.model, "context_window", 128_000)
    max_tokens = getattr(self.agent.model, "max_tokens", 4096)
    base_url = getattr(self.agent.model, "base_url", None) or getattr(self.agent.model, "baseUrl", None)

    i = 1
    while i < len(parts):
        if parts[i] == "--context-window" and i + 1 < len(parts):
            try:
                context_window = int(parts[i + 1])
            except ValueError:
                return False, f"Invalid context-window value: {parts[i + 1]}"
            i += 2
        else:
            i += 1

    # Create new model
    try:
        from basket_ai.api import get_model

        model_kwargs = {
            "context_window": context_window,
            "max_tokens": max_tokens,
        }
        if base_url:
            model_kwargs["base_url"] = str(base_url)

        new_model = get_model(provider, model_id, **model_kwargs)

        # Swap model in both AssistantAgent and inner Agent
        old_provider = getattr(self.agent.model, "provider", "unknown")
        old_model_id = getattr(self.agent.model, "model_id", "unknown")

        self.agent.model = new_model
        if hasattr(self.agent, "agent") and hasattr(self.agent.agent, "model"):
            self.agent.agent.model = new_model

        print(
            f"Model switched: {old_provider}/{old_model_id} → {provider}/{model_id} "
            f"(context_window={context_window})"
        )
        return True, ""

    except Exception as e:
        return False, f"Failed to switch model: {e}"
```

**Step 2: Register `/model` in `register_builtin_commands`**

Add after the `/compact` registration block (after line 343):

```python
# Register /model command
registry.register(
    name="model",
    handler=handlers.handle_model,
    description="Show current model or switch to a different one",
    usage="/model [provider/model_id] [--context-window N]",
    aliases=["model", "/model"],
)
```

**Step 3: Update `/help` text**

In `handle_help`, add `/model` line (after `/compact` line, around line 39):

```
  /model [provider/id]  Show or switch the current LLM model
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/basket-assistant && poetry run pytest tests/interaction/commands/test_handlers.py -v -k "model"`
Expected: All 4 model tests PASS

**Step 5: Run all handler tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/interaction/commands/test_handlers.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add packages/basket-assistant/basket_assistant/interaction/commands/handlers.py
git commit -m "feat: implement /model command for runtime model switching"
```

---

### Task 3: Add /model registration verification tests

**Files:**
- Modify: `packages/basket-assistant/tests/interaction/commands/test_handlers.py`

**Step 1: Update `TestRegisterBuiltinCommands`**

Add to `test_register_builtin_commands` (around line 409):

```python
assert registry.get_command("model") is not None
```

Add to `test_command_aliases` (around line 425):

```python
assert registry.get_command("/model") is not None
```

**Step 2: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/interaction/commands/test_handlers.py::TestRegisterBuiltinCommands -v`
Expected: PASS

**Step 3: Commit**

```bash
git add packages/basket-assistant/tests/interaction/commands/test_handlers.py
git commit -m "test: verify /model command registration and aliases"
```

---

## Feature B: BASKET.md Project Instruction Files

### Task 4: Write failing tests for BASKET.md loading

**Files:**
- Create: `packages/basket-assistant/tests/test_basket_md_loading.py`

**Step 1: Write the failing tests**

```python
"""Tests for BASKET.md / CLAUDE.md project instruction file loading."""

import pytest
from pathlib import Path

from basket_assistant.core.workspace_bootstrap import (
    load_project_instructions,
)


class TestLoadProjectInstructions:
    """Test loading BASKET.md and CLAUDE.md project instruction files."""

    def test_loads_basket_md_from_project(self, tmp_path):
        """Test loading .basket/BASKET.md from project root."""
        basket_dir = tmp_path / ".basket"
        basket_dir.mkdir()
        (basket_dir / "BASKET.md").write_text("# Project Rules\nBe helpful.", encoding="utf-8")

        result = load_project_instructions(project_root=tmp_path)

        assert result is not None
        assert "Project Rules" in result
        assert "Be helpful" in result

    def test_loads_claude_md_from_project(self, tmp_path):
        """Test loading .claude/CLAUDE.md as fallback."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "CLAUDE.md").write_text("# Claude Rules\nBe concise.", encoding="utf-8")

        result = load_project_instructions(project_root=tmp_path)

        assert result is not None
        assert "Claude Rules" in result

    def test_basket_md_takes_priority_over_claude_md(self, tmp_path):
        """Test that BASKET.md takes priority when both exist."""
        basket_dir = tmp_path / ".basket"
        basket_dir.mkdir()
        (basket_dir / "BASKET.md").write_text("Basket wins", encoding="utf-8")

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "CLAUDE.md").write_text("Claude loses", encoding="utf-8")

        result = load_project_instructions(project_root=tmp_path)

        assert "Basket wins" in result
        assert "Claude loses" not in result

    def test_loads_root_basket_md(self, tmp_path):
        """Test loading BASKET.md from project root (not .basket/ subdir)."""
        (tmp_path / "BASKET.md").write_text("Root instructions", encoding="utf-8")

        result = load_project_instructions(project_root=tmp_path)

        assert result is not None
        assert "Root instructions" in result

    def test_loads_root_claude_md(self, tmp_path):
        """Test loading CLAUDE.md from project root as fallback."""
        (tmp_path / "CLAUDE.md").write_text("Claude root instructions", encoding="utf-8")

        result = load_project_instructions(project_root=tmp_path)

        assert result is not None
        assert "Claude root instructions" in result

    def test_returns_none_when_no_files(self, tmp_path):
        """Test returns None when no instruction files exist."""
        result = load_project_instructions(project_root=tmp_path)

        assert result is None

    def test_returns_none_for_empty_file(self, tmp_path):
        """Test returns None when file exists but is empty."""
        basket_dir = tmp_path / ".basket"
        basket_dir.mkdir()
        (basket_dir / "BASKET.md").write_text("", encoding="utf-8")

        result = load_project_instructions(project_root=tmp_path)

        assert result is None

    def test_user_level_basket_md(self, tmp_path, monkeypatch):
        """Test loading ~/.basket/BASKET.md (user-level)."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        basket_dir = tmp_path / ".basket"
        basket_dir.mkdir(exist_ok=True)
        (basket_dir / "BASKET.md").write_text("User instructions", encoding="utf-8")

        result = load_project_instructions(project_root=tmp_path / "some-project")

        # User-level should be loaded when project-level is absent
        assert result is not None
        assert "User instructions" in result

    def test_priority_order(self, tmp_path):
        """Test full priority: .basket/BASKET.md > BASKET.md > .claude/CLAUDE.md > CLAUDE.md."""
        # Create all 4 files
        basket_dir = tmp_path / ".basket"
        basket_dir.mkdir()
        (basket_dir / "BASKET.md").write_text("Priority 1", encoding="utf-8")
        (tmp_path / "BASKET.md").write_text("Priority 2", encoding="utf-8")
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "CLAUDE.md").write_text("Priority 3", encoding="utf-8")
        (tmp_path / "CLAUDE.md").write_text("Priority 4", encoding="utf-8")

        result = load_project_instructions(project_root=tmp_path)

        assert "Priority 1" in result
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_basket_md_loading.py -v`
Expected: FAIL — `ImportError: cannot import name 'load_project_instructions'`

**Step 3: Commit**

```bash
git add packages/basket-assistant/tests/test_basket_md_loading.py
git commit -m "test: add failing tests for BASKET.md project instruction loading"
```

---

### Task 5: Implement BASKET.md loading function

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/core/workspace_bootstrap.py:1-15` (add function)

**Step 1: Add `load_project_instructions` function**

Add after `load_daily_memory` (after line 160):

```python
def load_project_instructions(
    project_root: Optional[Path] = None,
) -> Optional[str]:
    """Load project instruction file (BASKET.md or CLAUDE.md).

    Searches for instruction files in priority order:
    1. <project_root>/.basket/BASKET.md
    2. <project_root>/BASKET.md
    3. <project_root>/.claude/CLAUDE.md
    4. <project_root>/CLAUDE.md
    5. ~/.basket/BASKET.md (user-level fallback)
    6. ~/.claude/CLAUDE.md (user-level fallback)

    Returns the content of the first file found, or None if no file exists.
    """
    if project_root is None:
        project_root = Path.cwd()

    search_paths = [
        project_root / ".basket" / "BASKET.md",
        project_root / "BASKET.md",
        project_root / ".claude" / "CLAUDE.md",
        project_root / "CLAUDE.md",
        Path.home() / ".basket" / "BASKET.md",
        Path.home() / ".claude" / "CLAUDE.md",
    ]

    for path in search_paths:
        if path.exists() and path.is_file():
            try:
                content = path.read_text(encoding="utf-8").strip()
                if content:
                    logger.debug("Loaded project instructions from %s", path)
                    return content
            except Exception as e:
                logger.warning("Failed to read project instructions %s: %s", path, e)

    return None
```

**Step 2: Run tests to verify they pass**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_basket_md_loading.py -v`
Expected: All 9 tests PASS

**Step 3: Run existing workspace tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_workspace_bootstrap.py -v`
Expected: All existing tests PASS (no regressions)

**Step 4: Commit**

```bash
git add packages/basket-assistant/basket_assistant/core/workspace_bootstrap.py
git commit -m "feat: add load_project_instructions for BASKET.md/CLAUDE.md loading"
```

---

### Task 6: Inject BASKET.md into system prompt

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/agent/prompts.py:96-118` (modify compose function)
- Create: `packages/basket-assistant/tests/test_basket_md_prompt_injection.py`

**Step 1: Write the failing test**

```python
"""Tests for BASKET.md injection into system prompt."""

import pytest
from pathlib import Path

from basket_assistant.agent.prompts import compose_system_prompt_from_workspace


class TestBasketMdPromptInjection:
    """Test that project instructions are injected into the system prompt."""

    def test_basket_md_injected_before_sections(self, tmp_path):
        """Test BASKET.md content appears in system prompt."""
        # Setup workspace
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "IDENTITY.md").write_text("Name: TestBot", encoding="utf-8")
        (workspace / "AGENTS.md").write_text("You are helpful.", encoding="utf-8")

        # Setup project instructions
        basket_dir = tmp_path / ".basket"
        basket_dir.mkdir()
        (basket_dir / "BASKET.md").write_text(
            "# Project Rules\nAlways use TDD.", encoding="utf-8"
        )

        prompt = compose_system_prompt_from_workspace(
            workspace, project_root=tmp_path
        )

        assert "Project Rules" in prompt
        assert "Always use TDD" in prompt
        assert "TestBot" in prompt

    def test_no_basket_md_still_works(self, tmp_path):
        """Test system prompt works without BASKET.md."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "AGENTS.md").write_text("You are helpful.", encoding="utf-8")

        prompt = compose_system_prompt_from_workspace(workspace)

        assert "You are helpful" in prompt

    def test_basket_md_appears_after_identity_before_tools(self, tmp_path):
        """Test BASKET.md is placed as a labeled section."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "IDENTITY.md").write_text("Name: TestBot", encoding="utf-8")
        (workspace / "AGENTS.md").write_text("You are helpful.", encoding="utf-8")

        basket_dir = tmp_path / ".basket"
        basket_dir.mkdir()
        (basket_dir / "BASKET.md").write_text("Custom instructions here.", encoding="utf-8")

        prompt = compose_system_prompt_from_workspace(
            workspace, project_root=tmp_path
        )

        # Project instructions section should exist
        assert "Project instructions" in prompt
        assert "Custom instructions here" in prompt
```

**Step 2: Run test to verify it fails**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_basket_md_prompt_injection.py -v`
Expected: FAIL — `TypeError: compose_system_prompt_from_workspace() got an unexpected keyword argument 'project_root'`

**Step 3: Modify `compose_system_prompt_from_workspace` to accept `project_root`**

In `packages/basket-assistant/basket_assistant/agent/prompts.py`, modify the function signature and body (lines 96–118):

```python
def compose_system_prompt_from_workspace(
    workspace_dir: Path,
    skip_bootstrap: bool = False,
    include_daily_memory: bool = True,
    project_root: Optional[Path] = None,
) -> str:
    """
    Compose system prompt from workspace md files, optional daily memory,
    and optional project instructions (BASKET.md / CLAUDE.md).
    Returns assembled sections plus _TOOLS_SYSTEM_BLOCK.
    """
    sections = load_workspace_sections(workspace_dir, skip_bootstrap=skip_bootstrap)
    if include_daily_memory:
        daily = load_daily_memory(workspace_dir)
        if daily:
            existing = sections.get("memory", "")
            sections["memory"] = (existing + "\n\n" + daily).strip() if existing else daily

    # Load project instructions (BASKET.md / CLAUDE.md)
    from .workspace_bootstrap import load_project_instructions
    project_instructions = load_project_instructions(project_root)

    parts = []

    # Inject project instructions as the first section (before SECTION_ORDER)
    if project_instructions:
        parts.append(f"## Project instructions\n\n{project_instructions}")

    for key, title in SECTION_ORDER:
        if key in sections and sections[key]:
            parts.append(f"## {title}\n\n{sections[key]}")
    if not parts:
        return _builtin_base_prompt()
    composed = "\n\n".join(parts)
    return composed + "\n\n---\n\n" + _TOOLS_SYSTEM_BLOCK
```

Also update `get_system_prompt_base` to pass `project_root` (lines 142–163):

The `_resolve_main_agent_workspace_dir` already returns a workspace path. We need to pass `project_root=Path.cwd()` to `compose_system_prompt_from_workspace`. Modify `get_system_prompt_base`:

```python
def get_system_prompt_base(settings: Optional[Any] = None) -> str:
    if settings is None:
        from ..core import SettingsManager
        settings = SettingsManager().load()
    if getattr(settings, "skip_bootstrap", False):
        return _builtin_base_prompt()
    workspace_dir = _resolve_main_agent_workspace_dir(settings)
    if workspace_dir is None:
        return _builtin_base_prompt()
    return compose_system_prompt_from_workspace(
        workspace_dir,
        skip_bootstrap=False,
        include_daily_memory=True,
        project_root=Path.cwd(),
    )
```

Add `from ..core.workspace_bootstrap import load_project_instructions` to the imports at line 7 (or use the existing lazy import inside the function).

**Step 4: Run tests to verify they pass**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_basket_md_prompt_injection.py -v`
Expected: All 3 tests PASS

**Step 5: Run existing prompt tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_prompts_workspace.py -v`
Expected: All existing tests PASS

**Step 6: Commit**

```bash
git add packages/basket-assistant/basket_assistant/agent/prompts.py packages/basket-assistant/tests/test_basket_md_prompt_injection.py
git commit -m "feat: inject BASKET.md/CLAUDE.md project instructions into system prompt"
```

---

## Feature C: Hook Event Naming Unification

### Task 7: Write failing tests for hook alias resolution

**Files:**
- Modify: `packages/basket-assistant/tests/test_hook_runner.py`

**Step 1: Write the failing tests**

Add after the existing tests (after line 207):

```python
# -------------------------------------------------------
# Hook event alias tests (Claude Code naming alignment)
# -------------------------------------------------------

def test_hook_def_matches_pretooluse_alias():
    """PreToolUse alias resolves to tool.execute.before."""
    d = HookDef("x", matcher=None)
    assert d.matches("PreToolUse", {"tool_name": "read"}) is True


def test_hook_def_matches_posttooluse_alias():
    """PostToolUse alias resolves to tool.execute.after."""
    d = HookDef("x", matcher="read")
    assert d.matches("PostToolUse", {"tool_name": "read"}) is True
    assert d.matches("PostToolUse", {"tool_name": "bash"}) is False


@pytest.mark.asyncio
async def test_hook_runner_pretooluse_alias(tmp_path):
    """Hooks registered under PreToolUse fire for tool.execute.before events."""
    script = tmp_path / "allow.sh"
    script.write_text('#!/bin/sh\necho \'{"permission":"allow"}\'\nexit 0\n')
    script.chmod(0o755)
    hooks = {
        "PreToolUse": [
            {"command": str(script), "timeout": 5},
        ],
    }
    runner = HookRunner(project_root=tmp_path, settings_hooks=hooks)
    result = await runner.run(
        "tool.execute.before",
        {"tool_name": "read", "arguments": {}},
        cwd=tmp_path,
    )
    assert result.get("permission") == "allow"


@pytest.mark.asyncio
async def test_hook_runner_posttooluse_alias(tmp_path):
    """Hooks registered under PostToolUse fire for tool.execute.after events."""
    script = tmp_path / "after.sh"
    script.write_text('#!/bin/sh\necho \'{"permission":"allow"}\'\nexit 0\n')
    script.chmod(0o755)
    hooks = {
        "PostToolUse": [
            {"command": str(script), "timeout": 5},
        ],
    }
    runner = HookRunner(project_root=tmp_path, settings_hooks=hooks)
    result = await runner.run(
        "tool.execute.after",
        {"tool_name": "read", "arguments": {}},
        cwd=tmp_path,
    )
    assert result.get("permission") == "allow"


@pytest.mark.asyncio
async def test_hook_runner_stop_alias(tmp_path):
    """Hooks registered under Stop fire for session.ended events."""
    script = tmp_path / "stop.sh"
    script.write_text('#!/bin/sh\necho \'{"permission":"allow"}\'\nexit 0\n')
    script.chmod(0o755)
    hooks = {
        "Stop": [
            {"command": str(script), "timeout": 5},
        ],
    }
    runner = HookRunner(project_root=tmp_path, settings_hooks=hooks)
    result = await runner.run(
        "session.ended",
        {},
        cwd=tmp_path,
    )
    assert result.get("permission") == "allow"


def test_merge_hook_defs_normalizes_aliases():
    """Merged hooks normalize Claude Code aliases to canonical names."""
    project = {"PreToolUse": [{"command": "pre.sh"}]}
    user = {"PostToolUse": [{"command": "post.sh"}]}
    settings = {"tool.execute.before": [{"command": "canonical.sh"}]}

    merged = _merge_hook_defs(project, user, settings)

    # Both PreToolUse and tool.execute.before should be under same canonical key
    assert "tool.execute.before" in merged
    assert len(merged["tool.execute.before"]) == 2
    assert "tool.execute.after" in merged
    assert len(merged["tool.execute.after"]) == 1
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_hook_runner.py -v -k "alias or pretooluse or posttooluse or stop or normaliz"`
Expected: FAIL — aliases not recognized

**Step 3: Commit**

```bash
git add packages/basket-assistant/tests/test_hook_runner.py
git commit -m "test: add failing tests for hook event naming aliases"
```

---

### Task 8: Implement hook event alias mapping

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/extensions/hook_runner.py:1-20` (add alias map)
- Modify: `packages/basket-assistant/basket_assistant/extensions/hook_runner.py:37-51` (update matches)
- Modify: `packages/basket-assistant/basket_assistant/extensions/hook_runner.py:107-130` (update merge)
- Modify: `packages/basket-assistant/basket_assistant/extensions/hook_runner.py:171-210` (update run)

**Step 1: Add alias mapping constant**

Add after `HOOK_EXIT_DENY = 2` (after line 19):

```python
# Claude Code → Basket canonical event name mapping
# Allows users to use either naming convention in hooks.json
HOOK_ALIAS_MAP = {
    "PreToolUse": "tool.execute.before",
    "PostToolUse": "tool.execute.after",
    "Stop": "session.ended",
    "Notification": "message.turn_done",
}

# Reverse map for matching: canonical → set of aliases
_CANONICAL_TO_ALIASES: dict[str, set[str]] = {}
for _alias, _canonical in HOOK_ALIAS_MAP.items():
    _CANONICAL_TO_ALIASES.setdefault(_canonical, set()).add(_alias)


def normalize_hook_event(event_name: str) -> str:
    """Normalize a hook event name to its canonical form.

    Maps Claude Code-style names (PreToolUse, PostToolUse, Stop, Notification)
    to Basket canonical names (tool.execute.before, tool.execute.after, etc.).
    Returns the input unchanged if it is already canonical.
    """
    return HOOK_ALIAS_MAP.get(event_name, event_name)
```

**Step 2: Update `HookDef.matches` to handle aliases**

Replace the `matches` method (lines 37–51):

```python
def matches(self, hook_name: str, input_data: Dict[str, Any]) -> bool:
    """Return True if this hook should run for the given event and input."""
    # Normalize hook_name so aliases map to canonical names
    canonical = normalize_hook_event(hook_name)

    if not self.matcher:
        return True
    if canonical in ("tool.execute.before", "tool.execute.after"):
        tool_name = input_data.get("tool_name") or ""
        if re.search(self.matcher, tool_name, re.IGNORECASE):
            return True
        # For bash tool, also match against command string
        if tool_name == "bash":
            cmd = (input_data.get("arguments") or {}).get("command") or ""
            if re.search(self.matcher, cmd):
                return True
        return False
    return True
```

**Step 3: Update `_merge_hook_defs` to normalize event names**

Replace the function (lines 107–130):

```python
def _merge_hook_defs(
    project: Dict[str, List[Dict[str, Any]]],
    user: Dict[str, List[Dict[str, Any]]],
    settings: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, List[HookDef]]:
    """Merge hook definitions: project first, then user, then settings (append).

    Event names are normalized so Claude Code aliases (PreToolUse, PostToolUse, etc.)
    are merged into their canonical Basket names.
    """
    all_events: Dict[str, List[HookDef]] = {}
    for source in (project, user, settings):
        for event_name, defs in source.items():
            canonical = normalize_hook_event(event_name)
            if canonical not in all_events:
                all_events[canonical] = []
            for d in defs:
                cmd = d.get("command")
                if not cmd:
                    continue
                cmd = _expand_command(cmd)
                all_events[canonical].append(
                    HookDef(
                        command=cmd,
                        timeout=d.get("timeout"),
                        matcher=d.get("matcher"),
                    )
                )
    return all_events
```

**Step 4: Update `HookRunner.run` to normalize event names**

In the `run` method (line 171), add normalization at the start of the method:

```python
async def run(
    self,
    hook_name: str,
    input_data: Dict[str, Any],
    output: Optional[Dict[str, Any]] = None,
    cwd: Optional[Path] = None,
) -> Dict[str, Any]:
    # Normalize hook_name so aliases resolve to canonical names
    canonical = normalize_hook_event(hook_name)
    # ... rest of method uses `canonical` instead of `hook_name` for dict lookup
```

Change `defs = self._hooks.get(hook_name, [])` to `defs = self._hooks.get(canonical, [])` and update all logger calls to use `canonical`.

**Step 5: Update `__all__` export**

Add to `__all__` at line 312:

```python
__all__ = ["HookRunner", "HookDef", "HOOK_EXIT_DENY", "HOOK_ALIAS_MAP", "normalize_hook_event"]
```

**Step 6: Run tests to verify they pass**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_hook_runner.py -v`
Expected: All tests PASS (existing + new alias tests)

**Step 7: Commit**

```bash
git add packages/basket-assistant/basket_assistant/extensions/hook_runner.py
git commit -m "feat: add Claude Code hook naming aliases (PreToolUse/PostToolUse/Stop/Notification)"
```

---

### Task 9: Full test suite verification

**Files:** None (verification only)

**Step 1: Run all basket-assistant tests**

Run: `cd packages/basket-assistant && poetry run pytest -v --ignore=tests/test_tui_mode.py --ignore=tests/adapters/test_tui.py --ignore=tests/interaction/modes/test_tui_mode.py --ignore=tests/interaction/modes/test_attach_mode.py`
Expected: All tests PASS (TUI tests excluded — pre-existing failures unrelated to our changes)

**Step 2: Run the three feature test files specifically**

Run: `cd packages/basket-assistant && poetry run pytest tests/interaction/commands/test_handlers.py tests/test_basket_md_loading.py tests/test_basket_md_prompt_injection.py tests/test_hook_runner.py -v`
Expected: All tests PASS

**Step 3: Verify no import issues**

Run: `cd packages/basket-assistant && poetry run python -c "from basket_assistant.interaction.commands.handlers import BuiltinCommandHandlers; from basket_assistant.core.workspace_bootstrap import load_project_instructions; from basket_assistant.extensions.hook_runner import HOOK_ALIAS_MAP, normalize_hook_event; print('All imports OK')"`
Expected: `All imports OK`

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: verify all tests pass after Phase 2 implementation"
```

---

## Summary of Changes

| File | Action | Description |
|------|--------|-------------|
| `handlers.py` | Modify | Add `handle_model()` method + register command + help text |
| `workspace_bootstrap.py` | Modify | Add `load_project_instructions()` function |
| `prompts.py` | Modify | Add `project_root` param to `compose_system_prompt_from_workspace()`, inject BASKET.md |
| `hook_runner.py` | Modify | Add `HOOK_ALIAS_MAP`, `normalize_hook_event()`, update `matches`/`_merge_hook_defs`/`run` |
| `test_handlers.py` | Modify | Add 4 `/model` tests + `MockModelForSwitch` + registration checks |
| `test_basket_md_loading.py` | Create | 9 tests for `load_project_instructions()` |
| `test_basket_md_prompt_injection.py` | Create | 3 tests for prompt injection |
| `test_hook_runner.py` | Modify | 6 tests for hook alias resolution |

**Total new tests:** 22
**Total new production code:** ~120 lines (1 handler + 1 loader function + 1 prompt modification + 1 alias system)
**Estimated effort:** ~45 minutes

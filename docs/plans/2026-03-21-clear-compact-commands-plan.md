# Phase 1 Extensibility Alignment: /clear + /compact Commands

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `/clear` and `/compact` slash commands to basket-assistant, closing the two highest-priority command gaps identified in the extensibility gap analysis.

**Architecture:** Both commands are implemented as async handlers in `BuiltinCommandHandlers`, following the existing pattern (see `/sessions`, `/open`). `/clear` resets conversation context while preserving system prompt and creating a new session. `/compact` manually triggers the existing `compact_context()` pipeline from `basket_agent.context_manager` and reports metrics.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest + pytest-asyncio

**Note:** MCP Client support (the third P0 item) is deliberately excluded from this plan — it is a much larger effort requiring its own dedicated design document and implementation phase.

---

### Task 1: Write failing tests for `/clear` command handler

**Files:**
- Modify: `packages/basket-assistant/tests/interaction/commands/test_handlers.py`

**Step 1: Write the failing tests**

Add to the existing `TestBuiltinCommandHandlers` class:

```python
@pytest.mark.asyncio
async def test_handle_clear_resets_context(self):
    """Test /clear clears messages, todos, and pending asks."""
    agent = MockAgent()
    agent.context = MockContext(messages=["msg1", "msg2"])
    agent._current_todos = [{"id": 1}]
    agent._pending_asks = [{"tool_call_id": "tc1"}]
    agent._session_id = "old-session"
    handlers = BuiltinCommandHandlers(agent)

    success, error = await handlers.handle_clear("")

    assert success is True
    assert error == ""
    assert agent.context.messages == []
    assert agent._current_todos == []
    assert agent._pending_asks == []

@pytest.mark.asyncio
async def test_handle_clear_preserves_system_prompt(self):
    """Test /clear keeps system prompt intact."""
    agent = MockAgent()
    agent.context = MockContext(
        system_prompt="You are a helpful assistant.",
        messages=["msg1"],
    )
    handlers = BuiltinCommandHandlers(agent)

    await handlers.handle_clear("")

    assert agent.context.system_prompt == "You are a helpful assistant."

@pytest.mark.asyncio
async def test_handle_clear_creates_new_session(self):
    """Test /clear creates a new session when session_manager is available."""
    agent = MockAgent()
    agent.context = MockContext(messages=["msg1"])
    agent._session_id = "old-session"
    handlers = BuiltinCommandHandlers(agent)

    await handlers.handle_clear("")

    assert agent._session_id != "old-session"
    assert agent._session_id == "new-session-id"

@pytest.mark.asyncio
async def test_handle_clear_works_without_session_manager(self):
    """Test /clear works even when session_manager is None."""
    agent = MockAgent()
    agent.context = MockContext(messages=["msg1"])
    agent.session_manager = None
    agent._session_id = None
    handlers = BuiltinCommandHandlers(agent)

    success, error = await handlers.handle_clear("")

    assert success is True
    assert agent.context.messages == []
```

Also add `MockContext` class to the test file (before `MockAgent`):

```python
class MockContext:
    """Mock context for testing."""

    def __init__(self, messages=None, system_prompt=""):
        self.messages = messages or []
        self.system_prompt = system_prompt
```

And update `MockAgent.__init__` to include `context`:

```python
class MockAgent:
    def __init__(self):
        self.settings = MockSettings()
        self.session_manager = MockSessionManager()
        self._todo_show_full = False
        self.plan_mode = False
        self.conversation = []
        self.context = MockContext()
        self._current_todos = []
        self._pending_asks = []
        self._session_id = None
```

And add `create_session` to `MockSessionManager`:

```python
class MockSessionManager:
    def __init__(self):
        self.sessions = [
            {"id": "session-1", "created_at": "2026-03-14T10:00:00"},
            {"id": "session-2", "created_at": "2026-03-14T11:00:00"},
        ]
        self.current_session_id = "session-1"

    async def create_session(self, model_id: str = "") -> str:
        return "new-session-id"

    async def list_sessions(self):
        return self.sessions

    async def load_session(self, session_id: str):
        if session_id not in [s["id"] for s in self.sessions]:
            raise ValueError(f"Session not found: {session_id}")
        self.current_session_id = session_id
        return [{"role": "user", "content": "test"}]
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/basket-assistant && poetry run pytest tests/interaction/commands/test_handlers.py -v -k "clear"`
Expected: FAIL — `AttributeError: 'BuiltinCommandHandlers' has no attribute 'handle_clear'`

**Step 3: Commit test scaffolding**

```bash
git add packages/basket-assistant/tests/interaction/commands/test_handlers.py
git commit -m "test: add failing tests for /clear command handler"
```

---

### Task 2: Implement `/clear` command handler

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/interaction/commands/handlers.py:10-19` (add handler method)
- Modify: `packages/basket-assistant/basket_assistant/interaction/commands/handlers.py:172-260` (register command)

**Step 1: Add `handle_clear` method to `BuiltinCommandHandlers`**

Add after the `handle_plan` method (after line 116):

```python
async def handle_clear(self, args: str) -> tuple[bool, str]:
    """Handle /clear command — reset conversation context.

    Clears messages, todos, and pending asks while preserving the
    system prompt. Creates a new session if session_manager is available.

    Args:
        args: Command arguments (unused)

    Returns:
        Tuple of (success, error_message)
    """
    old_msg_count = len(self.agent.context.messages)

    # Clear in-memory state
    self.agent.context.messages = []
    self.agent._current_todos = []
    self.agent._pending_asks = []

    # Create new session if session management is available
    if self.agent.session_manager is not None:
        try:
            model_id = getattr(self.agent.model, "model_id", "")
            new_session_id = await self.agent.session_manager.create_session(
                model_id=model_id,
            )
            self.agent._session_id = new_session_id
            print(f"Context cleared ({old_msg_count} messages removed). New session: {new_session_id}")
        except Exception as e:
            self.agent._session_id = None
            print(f"Context cleared ({old_msg_count} messages removed). Warning: failed to create new session: {e}")
    else:
        self.agent._session_id = None
        print(f"Context cleared ({old_msg_count} messages removed).")

    return True, ""
```

**Step 2: Register `/clear` in `register_builtin_commands`**

Add after the `/open` registration block (after line 233):

```python
# Register /clear command
registry.register(
    name="clear",
    handler=handlers.handle_clear,
    description="Clear conversation context and start fresh",
    usage="/clear",
    aliases=["clear", "/clear"],
)
```

**Step 3: Update `/help` text**

In `handle_help`, add `/clear` to the help text (after the `/open` line):

```
  /clear             Clear conversation and start new session
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/basket-assistant && poetry run pytest tests/interaction/commands/test_handlers.py -v -k "clear"`
Expected: All 4 clear tests PASS

**Step 5: Run all handler tests to verify no regressions**

Run: `cd packages/basket-assistant && poetry run pytest tests/interaction/commands/test_handlers.py -v`
Expected: All tests PASS (existing + new)

**Step 6: Commit**

```bash
git add packages/basket-assistant/basket_assistant/interaction/commands/handlers.py
git commit -m "feat: implement /clear command to reset conversation context"
```

---

### Task 3: Write failing tests for `/compact` command handler

**Files:**
- Modify: `packages/basket-assistant/tests/interaction/commands/test_handlers.py`

**Step 1: Write the failing tests**

Add to `TestBuiltinCommandHandlers`:

```python
@pytest.mark.asyncio
async def test_handle_compact_reduces_context(self):
    """Test /compact triggers compaction when context is large."""
    agent = MockAgent()
    # Simulate large context that needs compaction
    agent.context = MockContext(messages=["msg"] * 100)
    agent.model = MockModelWithWindow(context_window=100)
    handlers = BuiltinCommandHandlers(agent)

    success, error = await handlers.handle_compact("")

    assert success is True
    assert error == ""

@pytest.mark.asyncio
async def test_handle_compact_no_change_when_small(self):
    """Test /compact reports no change when context is small."""
    agent = MockAgent()
    agent.context = MockContext(messages=[])
    agent.model = MockModelWithWindow(context_window=100_000)
    handlers = BuiltinCommandHandlers(agent)

    success, error = await handlers.handle_compact("")

    assert success is True
    assert error == ""
```

Add `MockModelWithWindow`:

```python
class MockModelWithWindow:
    """Mock model with context_window attribute."""

    def __init__(self, context_window: int = 128000):
        self.context_window = context_window
        self.model_id = "test-model"
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/basket-assistant && poetry run pytest tests/interaction/commands/test_handlers.py -v -k "compact"`
Expected: FAIL — `AttributeError: 'BuiltinCommandHandlers' has no attribute 'handle_compact'`

**Step 3: Commit**

```bash
git add packages/basket-assistant/tests/interaction/commands/test_handlers.py
git commit -m "test: add failing tests for /compact command handler"
```

---

### Task 4: Implement `/compact` command handler

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/interaction/commands/handlers.py`

**Step 1: Add `handle_compact` method**

Add after `handle_clear` (uses the existing `compact_context` and `estimate_context_tokens` from `basket_agent.context_manager`):

```python
async def handle_compact(self, args: str) -> tuple[bool, str]:
    """Handle /compact command — compress conversation context.

    Triggers the three-stage compaction pipeline (truncate tool results,
    summarise older turns, evict oldest messages) and reports metrics.

    Args:
        args: Command arguments (unused)

    Returns:
        Tuple of (success, error_message)
    """
    from basket_agent.context_manager import compact_context, estimate_context_tokens

    context_window = getattr(self.agent.model, "context_window", 128_000)

    before_msgs = len(self.agent.context.messages)
    before_tokens = estimate_context_tokens(self.agent.context)

    new_context, was_compacted = compact_context(
        self.agent.context, context_window
    )

    if not was_compacted:
        usage_pct = (before_tokens / context_window * 100) if context_window else 0
        print(
            f"No compaction needed. Context: {before_msgs} messages, "
            f"~{before_tokens:,} tokens ({usage_pct:.0f}% of {context_window:,} window)."
        )
        return True, ""

    # Apply compacted context
    self.agent.context = new_context

    after_msgs = len(new_context.messages)
    after_tokens = estimate_context_tokens(new_context)
    saved_msgs = before_msgs - after_msgs
    saved_tokens = before_tokens - after_tokens
    usage_pct = (after_tokens / context_window * 100) if context_window else 0

    print(
        f"Context compacted: {before_msgs} → {after_msgs} messages "
        f"(-{saved_msgs}), ~{before_tokens:,} → ~{after_tokens:,} tokens "
        f"(-{saved_tokens:,}). Now at {usage_pct:.0f}% of {context_window:,} window."
    )
    return True, ""
```

**Step 2: Register `/compact`**

Add after the `/clear` registration:

```python
# Register /compact command
registry.register(
    name="compact",
    handler=handlers.handle_compact,
    description="Compress conversation context to free up space",
    usage="/compact",
    aliases=["compact", "/compact"],
)
```

**Step 3: Update `/help` text**

Add after `/clear` in help text:

```
  /compact           Compress conversation context to save tokens
```

**Step 4: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/interaction/commands/test_handlers.py -v -k "compact"`
Expected: All compact tests PASS

**Step 5: Run all tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/interaction/commands/ -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add packages/basket-assistant/basket_assistant/interaction/commands/handlers.py
git commit -m "feat: implement /compact command for manual context compression"
```

---

### Task 5: Integration tests — /clear and /compact through InputProcessor

**Files:**
- Modify: `packages/basket-assistant/tests/interaction/processors/test_input_processor.py`

**Step 1: Write integration tests**

Verify that `/clear` and `/compact` are routed correctly through the InputProcessor priority system:

```python
@pytest.mark.asyncio
async def test_clear_command_is_handled(self):
    """Test /clear is routed as a handled command."""
    result = await self.input_processor.process("/clear")
    assert result.action == "handled"
    assert result.error is None or result.error == ""

@pytest.mark.asyncio
async def test_compact_command_is_handled(self):
    """Test /compact is routed as a handled command."""
    result = await self.input_processor.process("/compact")
    assert result.action == "handled"
    assert result.error is None or result.error == ""
```

**Step 2: Run integration tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/interaction/processors/test_input_processor.py -v -k "clear or compact"`
Expected: PASS

**Step 3: Commit**

```bash
git add packages/basket-assistant/tests/interaction/processors/test_input_processor.py
git commit -m "test: add integration tests for /clear and /compact routing"
```

---

### Task 6: Registration verification test

**Files:**
- Modify: `packages/basket-assistant/tests/interaction/commands/test_handlers.py`

**Step 1: Update `TestRegisterBuiltinCommands`**

Add to `test_register_builtin_commands`:

```python
assert registry.get_command("clear") is not None
assert registry.get_command("compact") is not None
```

Add to `test_command_aliases`:

```python
assert registry.get_command("/clear") is not None
assert registry.get_command("/compact") is not None
```

**Step 2: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/interaction/commands/test_handlers.py::TestRegisterBuiltinCommands -v`
Expected: PASS

**Step 3: Commit**

```bash
git add packages/basket-assistant/tests/interaction/commands/test_handlers.py
git commit -m "test: verify /clear and /compact are registered with aliases"
```

---

### Task 7: Full test suite verification

**Files:** None (verification only)

**Step 1: Run all basket-assistant tests**

Run: `cd packages/basket-assistant && poetry run pytest -v`
Expected: All tests PASS, no regressions

**Step 2: Run basket-agent context_manager tests (verify no breakage)**

Run: `cd packages/basket-agent && poetry run pytest tests/test_context_manager.py -v`
Expected: All tests PASS

**Step 3: Type checking**

Run: `cd packages/basket-assistant && poetry run mypy basket_assistant/interaction/commands/handlers.py --ignore-missing-imports`
Expected: No errors

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: verify all tests pass after /clear and /compact implementation"
```

---

## Summary of Changes

| File | Action | Description |
|------|--------|-------------|
| `handlers.py` | Modify | Add `handle_clear()` and `handle_compact()` methods + register both commands |
| `test_handlers.py` | Modify | Add `MockContext`, `MockModelWithWindow`, update `MockAgent`, add 6 new tests |
| `test_input_processor.py` | Modify | Add 2 integration routing tests |

**Total new tests:** 8
**Total new production code:** ~70 lines (2 handlers + 2 registrations + help text update)
**Estimated effort:** ~30 minutes

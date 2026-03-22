# Event System Unified Typed Flow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate the wasteful Pydantic→dict→dataclass conversion chain by making the entire event flow typed end-to-end.

**Architecture:** basket-agent yields typed Pydantic events directly (no `.model_dump()`). EventPublisher forwards them without conversion. Adapters consume typed events. The redundant `AssistantEvent` dataclass layer is deleted entirely.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, pytest-asyncio

**Design Doc:** `docs/plans/2026-03-22-event-system-unified-typed-design.md`

---

### Task 1: basket-agent — Remove .model_dump() from agent_loop.py

**Files:**
- Modify: `packages/basket-agent/basket_agent/agent_loop.py` (16 `.model_dump()` calls)

**Step 1: Write failing test — agent_loop yields typed events**

Add to `packages/basket-agent/tests/test_agent_loop.py`:

```python
from basket_agent.types import (
    AgentEvent,
    AgentEventTurnStart,
    AgentEventTurnEnd,
    AgentEventToolCallStart,
    AgentEventToolCallEnd,
    AgentEventComplete,
    AgentEventError,
)


class TestAgentLoopTypedEvents:
    """Verify agent_loop yields typed AgentEvent instances, not dicts."""

    @pytest.mark.asyncio
    async def test_turn_events_are_typed(self, sample_model):
        """run_agent_turn should yield AgentEvent instances, not dicts."""
        from unittest.mock import AsyncMock, patch

        context = Context(
            systemPrompt="You are a test agent.",
            messages=[UserMessage(role="user", content="Say hello", timestamp=0)],
        )
        state = AgentState(model=sample_model, context=context, max_turns=1)

        mock_message = AssistantMessage(
            role="assistant",
            content=[TextContent(type="text", text="Hello!")],
            timestamp=0,
        )

        # Mock the stream to return a simple message
        mock_stream = AsyncMock()
        mock_stream.__aiter__ = lambda self: self
        mock_stream.__anext__ = AsyncMock(side_effect=StopAsyncIteration)
        mock_stream.result = AsyncMock(return_value=mock_message)

        with patch("basket_agent.agent_loop.stream", return_value=mock_stream):
            events = []
            async for event in run_agent_turn(state, stream_llm_events=False):
                events.append(event)

            # All AgentEvent instances should be typed, not dicts
            agent_events = [e for e in events if isinstance(e, AgentEvent)]
            assert len(agent_events) >= 2  # at least TurnStart + TurnEnd

            for event in agent_events:
                assert not isinstance(event, dict), (
                    f"Event should be typed AgentEvent, got dict: {event}"
                )

            # Verify specific types
            turn_starts = [e for e in events if isinstance(e, AgentEventTurnStart)]
            assert len(turn_starts) == 1
            assert turn_starts[0].turn_number == 1

            turn_ends = [e for e in events if isinstance(e, AgentEventTurnEnd)]
            assert len(turn_ends) == 1
            assert turn_ends[0].has_tool_calls is False
```

**Step 2: Run test to verify it fails**

```bash
cd packages/basket-agent && poetry run pytest tests/test_agent_loop.py::TestAgentLoopTypedEvents::test_turn_events_are_typed -v
```

Expected: FAIL — events are dicts (from `.model_dump()`)

**Step 3: Remove .model_dump() calls in agent_loop.py**

In `packages/basket-agent/basket_agent/agent_loop.py`, make these changes:

1. **Line 93, `_execute_single_tool_call`**: Change the events list type:
   ```python
   # Before:
   events: List[Dict[str, Any]] = []
   # After:
   events: List[AgentEvent] = []
   ```

2. **Lines 97-101**: Remove `.model_dump()`:
   ```python
   # Before:
   events.append(
       AgentEventToolCallStart(...).model_dump()
   )
   # After:
   events.append(
       AgentEventToolCallStart(...)
   )
   ```

3. **Apply same pattern to ALL 16 occurrences** at lines: 101, 109, 124, 148, 156, 192, 224, 252, 265, 283, 289, 331, 371, 386, 388, 391.
   Every `XxxEvent(...).model_dump()` → `XxxEvent(...)`

4. **Update return type annotations**:
   ```python
   # _execute_single_tool_call return type (line 74):
   # Change "events" field in the returned dict from List[Dict[str, Any]] to List[AgentEvent]

   # run_agent_turn signature (line 170):
   # Before:
   async def run_agent_turn(...) -> AsyncIterator[AgentEvent | Dict[str, Any]]:
   # After:
   async def run_agent_turn(...) -> AsyncIterator[Any]:
   # (Keep Any for now — LLM stream events are AssistantMessageEvent, not AgentEvent)

   # run_agent_loop signature (line 336):
   # Same change as run_agent_turn
   ```

5. **Remove unused `Dict` import** if no longer needed.

**Step 4: Run test to verify it passes**

```bash
cd packages/basket-agent && poetry run pytest tests/test_agent_loop.py::TestAgentLoopTypedEvents -v
```

Expected: PASS

**Step 5: Run all basket-agent tests to check for regressions**

```bash
cd packages/basket-agent && poetry run pytest -v
```

Expected: ALL PASS. If any test asserts `isinstance(event, dict)`, update those tests too.

**Step 6: Commit**

```bash
git add packages/basket-agent/basket_agent/agent_loop.py packages/basket-agent/tests/test_agent_loop.py
git commit -m "refactor(basket-agent): yield typed events instead of dicts in agent_loop"
```

---

### Task 2: basket-agent — Update Agent._emit_event to accept typed events

**Files:**
- Modify: `packages/basket-agent/basket_agent/agent.py:84-92`

**Step 1: Write failing test — Agent._emit_event receives typed event**

Add to `packages/basket-agent/tests/test_agent.py`:

```python
from basket_agent.types import AgentEvent, AgentEventTurnStart


class TestAgentEventEmission:
    """Tests for typed event emission."""

    @pytest.mark.asyncio
    async def test_emit_event_passes_typed_event_to_handler(self, sample_model):
        """Handler should receive a typed AgentEvent, not a dict."""
        agent = Agent(sample_model)
        received = []

        def handler(event: AgentEvent):
            received.append(event)

        agent.on("agent_turn_start", handler)

        event = AgentEventTurnStart(turn_number=1)
        await agent._emit_event(event)

        assert len(received) == 1
        assert isinstance(received[0], AgentEventTurnStart)
        assert received[0].turn_number == 1
```

**Step 2: Run test to verify it fails**

```bash
cd packages/basket-agent && poetry run pytest tests/test_agent.py::TestAgentEventEmission -v
```

Expected: FAIL — `_emit_event` tries `event.get("type")` on a Pydantic object.

**Step 3: Update Agent._emit_event**

In `packages/basket-agent/basket_agent/agent.py`, change:

```python
# Before (lines 84-92):
async def _emit_event(self, event: Dict[str, Any]) -> None:
    """Emit an event to all subscribed handlers."""
    event_type = event.get("type")
    if event_type in self.event_handlers:
        for handler in self.event_handlers[event_type]:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)

# After:
async def _emit_event(self, event: Any) -> None:
    """Emit a typed event to all subscribed handlers."""
    event_type = event.type if hasattr(event, "type") else event.get("type")
    if event_type and event_type in self.event_handlers:
        for handler in self.event_handlers[event_type]:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
```

Note: We use `hasattr` + fallback to support both typed events (from agent_loop) and LLM stream events (from basket-ai, which also have a `.type` attribute). This keeps backward compatibility.

**Step 4: Run test to verify it passes**

```bash
cd packages/basket-agent && poetry run pytest tests/test_agent.py::TestAgentEventEmission -v
```

Expected: PASS

**Step 5: Run all basket-agent tests**

```bash
cd packages/basket-agent && poetry run pytest -v
```

Expected: ALL PASS

**Step 6: Commit**

```bash
git add packages/basket-agent/basket_agent/agent.py packages/basket-agent/tests/test_agent.py
git commit -m "refactor(basket-agent): Agent._emit_event accepts typed events"
```

---

### Task 3: basket-assistant — Update agent/events.py handlers to use typed events

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/agent/events.py:54-152`

**Step 1: Update setup_event_handlers to use typed parameters**

In `packages/basket-assistant/basket_assistant/agent/events.py`, change the handlers in `setup_event_handlers()`:

```python
# Add imports at top:
from basket_ai.types import EventTextDelta
from basket_agent.types import AgentEventToolCallStart, AgentEventToolCallEnd

# Before (line 57):
def on_text_delta(event):
    delta = event.get("delta", "")

# After:
def on_text_delta(event: EventTextDelta) -> None:
    delta = event.delta

# Before (line 62):
async def on_tool_call_start(event):
    tool_name = event.get("tool_name", "unknown")
    args = event.get("arguments", {}) or {}

# After:
async def on_tool_call_start(event: AgentEventToolCallStart) -> None:
    tool_name = event.tool_name
    args = event.arguments
```

Apply the same pattern to:
- `on_tool_call_start` (lines 62-107): Replace all `event.get(...)` → `event.xxx`
  - `event.get("tool_name", "unknown")` → `event.tool_name`
  - `event.get("arguments", {}) or {}` → `event.arguments`
  - `event.get("tool_call_id")` → `event.tool_call_id`
  - `event['tool_name']` → `event.tool_name`

- `on_tool_call_end` (lines 109-148): Same pattern
  - `event.get("tool_name", "unknown")` → `event.tool_name`
  - `event.get("error")` → `event.error`
  - `event.get("result")` → `event.result`
  - `event.get("tool_call_id")` → `event.tool_call_id`
  - `event['error']` → `event.error`

**Step 2: Update setup_logging_handlers similarly**

In `setup_logging_handlers()` (lines 155-192):

```python
# Add import:
from basket_agent.types import AgentEventTurnStart, AgentEventTurnEnd

# Before (line 162):
def on_turn_start(event: dict) -> None:
    logger.info("LLM turn started, turn_number=%s", event.get("turn_number"))

# After:
def on_turn_start(event: AgentEventTurnStart) -> None:
    logger.info("LLM turn started, turn_number=%s", event.turn_number)

# Before (line 168):
def on_turn_end(event: dict) -> None:
    logger.info("LLM turn ended, turn_number=%s, has_tool_calls=%s",
                event.get("turn_number"), event.get("has_tool_calls", False))

# After:
def on_turn_end(event: AgentEventTurnEnd) -> None:
    logger.info("LLM turn ended, turn_number=%s, has_tool_calls=%s",
                event.turn_number, event.has_tool_calls)
```

Same for `on_tool_call_start_log` and `on_tool_call_end_log`.

**Step 3: Update trajectory handlers**

In `on_trajectory_event` (line 261) and `ensure_trajectory_handlers` (line 268):

```python
# Before (line 261):
def on_trajectory_event(agent: AssistantAgentProtocol, event: dict) -> None:

# After:
def on_trajectory_event(agent: AssistantAgentProtocol, event: Any) -> None:
```

The trajectory recorder's `on_event` may still need dict — pass `event.model_dump()` inside:

```python
def on_trajectory_event(agent: AssistantAgentProtocol, event: Any) -> None:
    recorder = agent._trajectory_recorder
    if recorder is not None:
        # Trajectory recorder expects dict format
        data = event.model_dump() if hasattr(event, "model_dump") else event
        recorder.on_event(data)
```

**Step 4: Run basket-assistant tests**

```bash
cd packages/basket-assistant && poetry run pytest tests/ -v -x
```

Fix any failures caused by type changes.

**Step 5: Commit**

```bash
git add packages/basket-assistant/basket_assistant/agent/events.py
git commit -m "refactor(basket-assistant): update event handlers to use typed events"
```

---

### Task 4: basket-assistant — Simplify EventPublisher (remove 8 handlers → 1)

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/core/events/publisher.py`

**Step 1: Write failing test — publisher forwards typed events directly**

Add to `packages/basket-assistant/tests/core/events/test_publisher.py`:

```python
from basket_agent.types import AgentEventToolCallStart, AgentEventTurnStart


class TestEventPublisherTypedEvents:
    """Test publisher works with typed events (no dict conversion)."""

    def test_publisher_forwards_typed_agent_event(self, mock_agent):
        """Publisher should forward typed AgentEvent to subscribers as-is."""
        publisher = EventPublisher(mock_agent)
        received = []
        publisher.subscribe("agent_tool_call_start", lambda e: received.append(e))

        # Get the handler that publisher registered on the agent
        handler = None
        for call in mock_agent.agent.on.call_args_list:
            if call[0][0] == "agent_tool_call_start":
                handler = call[0][1]
                break

        # Emit a TYPED event (not a dict)
        typed_event = AgentEventToolCallStart(
            tool_name="bash",
            tool_call_id="call_1",
            arguments={"command": "ls"},
        )
        handler(typed_event)

        assert len(received) == 1
        assert isinstance(received[0], AgentEventToolCallStart)
        assert received[0].tool_name == "bash"
```

**Step 2: Run test to verify it fails**

```bash
cd packages/basket-assistant && poetry run pytest tests/core/events/test_publisher.py::TestEventPublisherTypedEvents -v
```

Expected: FAIL — publisher calls `event_from_dict()` which expects a dict.

**Step 3: Rewrite EventPublisher**

Replace `packages/basket-assistant/basket_assistant/core/events/publisher.py`:

```python
"""EventPublisher: Central event distribution hub.

Subscribes to basket-agent events and distributes typed events to adapters.
No conversion needed — events flow through as typed objects.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List

if TYPE_CHECKING:
    from basket_assistant.agent import AssistantAgent

logger = logging.getLogger(__name__)

# All event types the publisher subscribes to on the basket-agent
AGENT_EVENT_TYPES = (
    "text_delta",
    "thinking_delta",
    "agent_tool_call_start",
    "agent_tool_call_end",
    "agent_turn_start",
    "agent_turn_end",
    "agent_complete",
    "agent_error",
)


class EventPublisher:
    """Central event distribution hub for the assistant.

    Subscribes to basket-agent events and forwards them to adapters.
    Events are already typed — no conversion needed.

    Example:
        >>> publisher = EventPublisher(assistant)
        >>> publisher.subscribe("agent_tool_call_start", lambda e: print(e.tool_name))
    """

    def __init__(self, agent: AssistantAgent):
        self._assistant = agent
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {}
        self._setup_agent_subscriptions()

    def _setup_agent_subscriptions(self) -> None:
        """Subscribe to all agent event types with a single generic handler."""
        ba = self._assistant.agent
        for event_type in AGENT_EVENT_TYPES:
            ba.on(event_type, self._on_agent_event)

    def _on_agent_event(self, event: Any) -> None:
        """Forward typed event to subscribers."""
        event_type = event.type if hasattr(event, "type") else None
        if event_type:
            self._publish(event_type, event)

    def subscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        """Subscribe to a specific event type.

        Args:
            event_type: Event type string (e.g., "text_delta", "agent_tool_call_start")
            handler: Callback that receives the typed event
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)
            logger.debug(
                "Subscribed to %s: %s (total: %d)",
                event_type,
                handler.__name__ if hasattr(handler, "__name__") else str(handler)[:50],
                len(self._subscribers[event_type]),
            )

    def unsubscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        """Unsubscribe from a specific event type."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass

    def _publish(self, event_type: str, event: Any) -> None:
        """Publish an event to all subscribers for the given type."""
        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            return

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    "Event handler failed: type=%s handler=%s error=%s",
                    event_type,
                    handler.__name__ if hasattr(handler, "__name__") else "unknown",
                    e,
                    exc_info=True,
                )

    def cleanup(self) -> None:
        """Clean up all subscriptions."""
        self._subscribers.clear()
        logger.debug("EventPublisher cleaned up")
```

**Step 4: Run tests**

```bash
cd packages/basket-assistant && poetry run pytest tests/core/events/test_publisher.py -v
```

Some old tests will now fail because they emit dict events. Fix in Task 8.

**Step 5: Commit**

```bash
git add packages/basket-assistant/basket_assistant/core/events/publisher.py
git commit -m "refactor(basket-assistant): simplify EventPublisher to single generic handler"
```

---

### Task 5: basket-assistant — Update adapter subscriptions for new event names

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/adapters/cli.py:6-10, 83-87`
- Modify: `packages/basket-assistant/basket_assistant/adapters/tui.py:6-13, 41-48`
- Modify: `packages/basket-assistant/basket_assistant/adapters/webui.py:7-14, 43-50`
- Modify: `packages/basket-assistant/basket_assistant/adapters/base.py` (type hint update)

The key change: adapters now subscribe using `agent_` prefixed event names (matching basket-agent) and receive typed events from basket-agent/basket-ai directly.

**Step 1: Update CLIAdapter**

In `packages/basket-assistant/basket_assistant/adapters/cli.py`:

```python
# Before imports (lines 6-10):
from basket_assistant.core.events import (
    TextDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
)

# After:
from typing import Any
from basket_agent.types import AgentEventToolCallStart, AgentEventToolCallEnd

# Before subscriptions (lines 83-87):
def _setup_subscriptions(self) -> None:
    self.publisher.subscribe("text_delta", self._on_text_delta)
    self.publisher.subscribe("tool_call_start", self._on_tool_call_start)
    self.publisher.subscribe("tool_call_end", self._on_tool_call_end)

# After:
def _setup_subscriptions(self) -> None:
    self.publisher.subscribe("text_delta", self._on_text_delta)
    self.publisher.subscribe("agent_tool_call_start", self._on_tool_call_start)
    self.publisher.subscribe("agent_tool_call_end", self._on_tool_call_end)

# Before handler types:
def _on_text_delta(self, event: TextDeltaEvent) -> None:
def _on_tool_call_start(self, event: ToolCallStartEvent) -> None:
def _on_tool_call_end(self, event: ToolCallEndEvent) -> None:

# After:
def _on_text_delta(self, event: Any) -> None:
    """Handle text_delta event (EventTextDelta from basket-ai)."""
    if hasattr(event, "delta") and event.delta:
        print(event.delta, end="", flush=True)

def _on_tool_call_start(self, event: AgentEventToolCallStart) -> None:
    """Handle agent_tool_call_start event."""
    logger.info("Tool call: %s", event.tool_name)
    if self.verbose:
        args_str = _format_tool_args(event.tool_name, event.arguments or {})
        if args_str:
            print(f"\n[Tool: {event.tool_name} {args_str}]", flush=True)
        else:
            print(f"\n[Tool: {event.tool_name}]", flush=True)

def _on_tool_call_end(self, event: AgentEventToolCallEnd) -> None:
    """Handle agent_tool_call_end event."""
    if event.error:
        print(f"\n[Error: {event.error}]", flush=True)
        logger.warning("Tool call failed: %s - %s", event.tool_name, event.error)
```

**Step 2: Update TUIAdapter**

In `packages/basket-assistant/basket_assistant/adapters/tui.py`:

```python
# Before imports (lines 6-13):
from basket_assistant.core.events import (
    AgentCompleteEvent, AgentErrorEvent, TextDeltaEvent,
    ThinkingDeltaEvent, ToolCallEndEvent, ToolCallStartEvent,
)

# After:
from basket_agent.types import (
    AgentEventToolCallStart, AgentEventToolCallEnd,
    AgentEventComplete, AgentEventError,
)

# Before subscriptions (lines 41-48):
self.publisher.subscribe("text_delta", self._on_text_delta)
self.publisher.subscribe("thinking_delta", self._on_thinking_delta)
self.publisher.subscribe("tool_call_start", self._on_tool_call_start)
self.publisher.subscribe("tool_call_end", self._on_tool_call_end)
self.publisher.subscribe("agent_complete", self._on_agent_complete)
self.publisher.subscribe("agent_error", self._on_agent_error)

# After:
self.publisher.subscribe("text_delta", self._on_text_delta)
self.publisher.subscribe("thinking_delta", self._on_thinking_delta)
self.publisher.subscribe("agent_tool_call_start", self._on_tool_call_start)
self.publisher.subscribe("agent_tool_call_end", self._on_tool_call_end)
self.publisher.subscribe("agent_complete", self._on_agent_complete)
self.publisher.subscribe("agent_error", self._on_agent_error)
```

Update handler type hints to use basket-agent types:
- `_on_text_delta(self, event: Any)` — basket-ai `EventTextDelta`
- `_on_thinking_delta(self, event: Any)` — basket-ai `EventThinkingDelta`
- `_on_tool_call_start(self, event: AgentEventToolCallStart)`
- `_on_tool_call_end(self, event: AgentEventToolCallEnd)`
- `_on_agent_complete(self, event: AgentEventComplete)`
- `_on_agent_error(self, event: AgentEventError)`

**Step 3: Update WebUIAdapter**

Same pattern as TUI. In `packages/basket-assistant/basket_assistant/adapters/webui.py`:
- Update imports: basket-agent types instead of basket-assistant event types
- Update subscription names: `"tool_call_start"` → `"agent_tool_call_start"`, etc.
- Update handler type hints

**Step 4: Run adapter tests**

```bash
cd packages/basket-assistant && poetry run pytest tests/adapters/ -v
```

Fix adapter test mocks to emit typed events instead of dicts.

**Step 5: Commit**

```bash
git add packages/basket-assistant/basket_assistant/adapters/
git commit -m "refactor(basket-assistant): adapters consume typed events from basket-agent"
```

---

### Task 6: basket-assistant — Delete AssistantEvent dataclass layer

**Files:**
- Delete: `packages/basket-assistant/basket_assistant/core/events/types.py` (entire file)
- Modify: `packages/basket-assistant/basket_assistant/core/events/__init__.py`

**Step 1: Update __init__.py exports**

Replace `packages/basket-assistant/basket_assistant/core/events/__init__.py`:

```python
"""Event system for basket-assistant.

Architecture:
    AssistantAgent → EventPublisher → Adapters → UI

Events flow through as typed objects from basket-agent and basket-ai.
No intermediate conversion layer.
"""

from .publisher import EventPublisher, AGENT_EVENT_TYPES

__all__ = [
    "EventPublisher",
    "AGENT_EVENT_TYPES",
]
```

**Step 2: Delete types.py**

```bash
rm packages/basket-assistant/basket_assistant/core/events/types.py
```

**Step 3: Search and fix remaining imports**

Search for any file still importing from `core.events.types` or importing the old event classes:

```bash
cd packages/basket-assistant && grep -rn "from basket_assistant.core.events import" --include="*.py" .
cd packages/basket-assistant && grep -rn "from .types import" basket_assistant/core/events/ --include="*.py"
cd packages/basket-assistant && grep -rn "AssistantEvent\|TextDeltaEvent\|ThinkingDeltaEvent\|ToolCallStartEvent\|ToolCallEndEvent\|AgentTurnStartEvent\|AgentTurnEndEvent\|AgentCompleteEvent\|AgentErrorEvent\|event_from_dict" --include="*.py" .
```

Fix every hit — replace with basket-agent/basket-ai type imports.

**Step 4: Run all tests**

```bash
cd packages/basket-assistant && poetry run pytest tests/ -v
```

**Step 5: Commit**

```bash
git add -A packages/basket-assistant/basket_assistant/core/events/
git commit -m "refactor(basket-assistant): delete AssistantEvent dataclass layer"
```

---

### Task 7: Split agent/events.py into focused modules

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/agent/events.py` (split into 4)
- Create: `packages/basket-assistant/basket_assistant/agent/_event_handlers.py`
- Create: `packages/basket-assistant/basket_assistant/agent/_event_logging.py`
- Create: `packages/basket-assistant/basket_assistant/agent/_trajectory.py`
- Create: `packages/basket-assistant/basket_assistant/agent/_assistant_events.py`

**Step 1: Create _event_handlers.py**

Move `setup_event_handlers`, `_tool_call_args_summary`, `_TOOL_ARG_SUMMARY_KEYS` from `events.py` to `_event_handlers.py`:

```python
"""CLI/TUI event handlers for agent events.

Handles text display, tool call logging, ask_user_question management,
and todo status updates.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from ._protocol import AssistantAgentProtocol

from basket_ai.types import EventTextDelta
from basket_agent.types import AgentEventToolCallStart, AgentEventToolCallEnd

logger = logging.getLogger(__name__)

# [Move _TOOL_ARG_SUMMARY_KEYS here from events.py lines 17-29]
# [Move _tool_call_args_summary here from events.py lines 32-51]
# [Move setup_event_handlers here from events.py lines 54-152]
```

**Step 2: Create _event_logging.py**

Move `setup_logging_handlers` from `events.py`:

```python
"""Logging-only event handlers shared by CLI and TUI modes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ._protocol import AssistantAgentProtocol

from basket_agent.types import (
    AgentEventTurnStart, AgentEventTurnEnd,
    AgentEventToolCallStart, AgentEventToolCallEnd,
)

logger = logging.getLogger(__name__)

# [Move _tool_call_args_summary reference or import from _event_handlers]
# [Move setup_logging_handlers here from events.py lines 155-192]
```

**Step 3: Create _trajectory.py**

Move trajectory functions from `events.py`:

```python
"""Trajectory recording for agent events."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:
    from ._protocol import AssistantAgentProtocol

logger = logging.getLogger(__name__)

# [Move get_trajectory_dir from events.py lines 252-258]
# [Move on_trajectory_event from events.py lines 261-265]
# [Move ensure_trajectory_handlers from events.py lines 268-281]
# [Move run_with_trajectory_if_enabled from events.py lines 284-341]
```

**Step 4: Create _assistant_events.py**

Move assistant-level event emission:

```python
"""Assistant-level event emission (before_run, turn_done)."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from ._protocol import AssistantAgentProtocol

logger = logging.getLogger(__name__)

# [Move emit_assistant_event from events.py lines 195-224]
# [Move messages_for_hook_payload from events.py lines 227-249]
```

**Step 5: Update events.py to re-export for backward compatibility**

Replace `packages/basket-assistant/basket_assistant/agent/events.py` with:

```python
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
]
```

**Step 6: Run all tests**

```bash
cd packages/basket-assistant && poetry run pytest tests/ -v
```

**Step 7: Commit**

```bash
git add packages/basket-assistant/basket_assistant/agent/events.py \
       packages/basket-assistant/basket_assistant/agent/_event_handlers.py \
       packages/basket-assistant/basket_assistant/agent/_event_logging.py \
       packages/basket-assistant/basket_assistant/agent/_trajectory.py \
       packages/basket-assistant/basket_assistant/agent/_assistant_events.py
git commit -m "refactor(basket-assistant): split events.py into 4 focused modules"
```

---

### Task 8: Update all tests for typed events

**Files:**
- Modify: `packages/basket-assistant/tests/core/events/test_publisher.py`
- Modify: `packages/basket-assistant/tests/integration/test_event_flow.py`
- Modify: `packages/basket-assistant/tests/adapters/test_cli.py`
- Modify: `packages/basket-assistant/tests/adapters/test_tui.py`
- Modify: `packages/basket-assistant/tests/adapters/test_webui.py`

**Step 1: Update test_publisher.py**

All tests currently emit **dicts** to simulate agent events. Change them to emit **typed events**.

Example for `test_subscribe_and_receive_text_delta` (lines 60-82):

```python
# Before (line 75):
text_delta_handler({"delta": "hello"})

# After:
from basket_ai.types import EventTextDelta
from basket_ai.types import AssistantMessage

text_delta_event = EventTextDelta(
    type="text_delta",
    content_index=0,
    delta="hello",
    partial=AssistantMessage(role="assistant", content=[], timestamp=0),
)
text_delta_handler(text_delta_event)
```

For agent events:

```python
# Before (line 170-176):
tool_call_handler({
    "tool_name": "bash",
    "arguments": {"command": "ls -la"},
    "tool_call_id": "call_123",
})

# After:
from basket_agent.types import AgentEventToolCallStart

tool_call_handler(AgentEventToolCallStart(
    tool_name="bash",
    tool_call_id="call_123",
    arguments={"command": "ls -la"},
))
```

Update assertions too:
```python
# Before:
assert isinstance(event, ToolCallStartEvent)  # was basket-assistant type
# After:
assert isinstance(event, AgentEventToolCallStart)  # now basket-agent type
```

**Important**: The `test_publisher_subscribes_to_agent_events` test (lines 37-58) should still pass — event type names haven't changed.

**Also update**: subscriber event names in tests:
```python
# Before:
publisher.subscribe("tool_call_start", handler)
# After:
publisher.subscribe("agent_tool_call_start", handler)
```

**Step 2: Update test_event_flow.py**

Same pattern — replace all dict event emissions with typed events. Update adapter subscription names.

**Step 3: Update adapter tests**

For each adapter test file (`test_cli.py`, `test_tui.py`, `test_webui.py`):
- Update imports to basket-agent types
- Change dict event data to typed event instances
- Update subscription event name assertions

**Step 4: Run ALL tests**

```bash
cd packages/basket-assistant && poetry run pytest tests/ -v
```

Expected: ALL PASS

**Step 5: Run basket-agent tests too (ensure no regressions)**

```bash
cd packages/basket-agent && poetry run pytest -v
```

Expected: ALL PASS

**Step 6: Commit**

```bash
git add packages/basket-assistant/tests/
git commit -m "test(basket-assistant): update all event tests for typed events"
```

---

### Task 9: Protocol slimming — Extract event/trajectory state

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/agent/_protocol.py`

**Step 1: Remove event/trajectory attributes from Protocol**

In `packages/basket-assistant/basket_assistant/agent/_protocol.py`:

```python
# Remove these lines from AssistantAgentProtocol:
# _assistant_event_handlers: Dict[str, List[Callable]]  (line 50)
# _trajectory_recorder: Optional[Any]  (line 54)
# _trajectory_handlers_registered: bool  (line 55)
```

**Step 2: Update _trajectory.py and _assistant_events.py**

These modules currently access `agent._assistant_event_handlers`, `agent._trajectory_recorder`, etc. They should still work — the Protocol just no longer declares these. The actual `AssistantAgent` class still has them. The Protocol is a structural type, so removing from Protocol means callers don't need to know about internal event state.

**Alternative**: If you want to fully decouple, encapsulate event state in small classes:

```python
# In _assistant_events.py:
class AssistantEventEmitter:
    """Encapsulates assistant-level event handler state."""
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}

    def register(self, event_name: str, handler: Callable) -> None:
        self._handlers.setdefault(event_name, []).append(handler)

    async def emit(self, event_name: str, payload: dict) -> None:
        # [Move logic from emit_assistant_event here]
        ...
```

This is optional for this phase. The minimal change is removing from Protocol.

**Step 3: Run tests**

```bash
cd packages/basket-assistant && poetry run pytest tests/ -v
```

**Step 4: Commit**

```bash
git add packages/basket-assistant/basket_assistant/agent/_protocol.py
git commit -m "refactor(basket-assistant): slim Protocol by removing event/trajectory state"
```

---

### Task 10: Final verification — Full test suite

**Step 1: Run basket-agent full test suite**

```bash
cd packages/basket-agent && poetry run pytest -v --tb=short
```

Expected: ALL PASS

**Step 2: Run basket-assistant full test suite**

```bash
cd packages/basket-assistant && poetry run pytest -v --tb=short
```

Expected: ALL PASS

**Step 3: Run type checker**

```bash
cd packages/basket-agent && poetry run mypy .
cd packages/basket-assistant && poetry run mypy .
```

Fix any type errors.

**Step 4: Run linter**

```bash
cd packages/basket-agent && poetry run ruff check .
cd packages/basket-assistant && poetry run ruff check .
```

Fix any lint issues.

**Step 5: Final commit (if any fixes)**

```bash
git add -A
git commit -m "chore: fix type/lint issues from event system refactor"
```

---

## Summary of Changes

| File | Action | Lines Changed |
|------|--------|---------------|
| `basket-agent/agent_loop.py` | Remove 16 `.model_dump()` | ~30 lines |
| `basket-agent/agent.py` | Update `_emit_event` | ~5 lines |
| `basket-assistant/core/events/types.py` | **DELETE** | -169 lines |
| `basket-assistant/core/events/publisher.py` | Rewrite (simplify) | -216 → ~100 lines |
| `basket-assistant/core/events/__init__.py` | Update exports | -45 → ~15 lines |
| `basket-assistant/agent/events.py` | Split → re-export | -342 → ~20 lines |
| `basket-assistant/agent/_event_handlers.py` | **NEW** | ~100 lines |
| `basket-assistant/agent/_event_logging.py` | **NEW** | ~50 lines |
| `basket-assistant/agent/_trajectory.py` | **NEW** | ~100 lines |
| `basket-assistant/agent/_assistant_events.py` | **NEW** | ~50 lines |
| `basket-assistant/adapters/cli.py` | Update types+names | ~15 lines |
| `basket-assistant/adapters/tui.py` | Update types+names | ~20 lines |
| `basket-assistant/adapters/webui.py` | Update types+names | ~20 lines |
| `basket-assistant/agent/_protocol.py` | Remove 3 attributes | ~3 lines |
| Tests (5+ files) | Update to typed events | ~200 lines |

**Net result:** ~200 lines deleted, type safety end-to-end, single event flow path.

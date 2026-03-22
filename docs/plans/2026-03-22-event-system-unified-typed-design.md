# Event System Refactor: Unified Typed Event Flow

**Date:** 2026-03-22
**Status:** Approved
**Scope:** basket-agent + basket-assistant

## Problem Statement

The current event system has 3 layers with wasteful conversion:

```
Pydantic event → .model_dump() → Dict[str,Any] → event_from_dict() → dataclass → adapter
```

Specific issues:
1. **Type safety lost at source**: `agent_loop.py` creates typed Pydantic events then immediately calls `.model_dump()`, discarding all type information
2. **Redundant conversion layer**: `EventPublisher` has 8 identical handler methods that call `event_from_dict()` to reconstruct typed events from dicts
3. **Two parallel event systems**: `Agent.on()` (dict handlers) and `EventPublisher.subscribe()` (typed handlers) operate independently
4. **Inconsistent naming**: `agent_tool_call_start` vs `tool_call_start` with `EVENT_TYPE_MAP` double mapping
5. **events.py god file**: 342 lines mixing event handling, trajectory, logging, and hook payloads
6. **Protocol bloat**: `AssistantAgentProtocol` has 17 attributes including event/trajectory state

## Design

### Section 1: basket-agent — Yield Typed Events

**Change**: Remove all `.model_dump()` calls in `agent_loop.py`. Yield Pydantic event objects directly.

**Before:**
```python
yield AgentEventTurnStart(turn_number=state.current_turn).model_dump()
```

**After:**
```python
yield AgentEventTurnStart(turn_number=state.current_turn)
```

**Type signatures:**
- `run_agent_turn()`: `AsyncIterator[AgentEvent | Dict[str, Any]]` → `AsyncIterator[AgentEvent | AssistantMessageEvent]`
- `run_agent_loop()`: Same change
- `_execute_single_tool_call` events list: `List[Dict[str, Any]]` → `List[AgentEvent]`

**Agent._emit_event:**
```python
# Before
async def _emit_event(self, event: Dict[str, Any]) -> None:
    event_type = event.get("type")

# After
async def _emit_event(self, event: AgentEvent) -> None:
    event_type = event.type
```

Note: LLM stream events (`EventTextDelta`, `EventThinkingDelta` from basket-ai) are already typed Pydantic objects. They flow through unchanged.

### Section 2: Delete AssistantEvent Dataclass Layer

**Delete** `basket-assistant/core/events/types.py` entirely:
- `AssistantEvent` base class
- `TextDeltaEvent`, `ThinkingDeltaEvent`, `ToolCallStartEvent`, etc.
- `EVENT_TYPE_MAP` mapping dict
- `event_from_dict()` conversion function

Adapters will directly consume `AgentEvent` (from basket-agent) and `AssistantMessageEvent` (from basket-ai).

### Section 3: Simplify EventPublisher

**Before:** 8 `_on_xxx` handler methods doing identical dict→typed conversion.

**After:** Single generic forwarder.

```python
class EventPublisher:
    _subscribers: Dict[str, List[Callable[[AgentEvent], None]]]

    def _setup_agent_subscriptions(self) -> None:
        for event_type in AGENT_EVENT_TYPES:
            self._assistant.agent.on(event_type, self._on_agent_event)

    def _on_agent_event(self, event: AgentEvent) -> None:
        self._publish(event)

    def _publish(self, event: AgentEvent) -> None:
        for handler in self._subscribers.get(event.type, []):
            try:
                handler(event)
            except Exception as e:
                logger.error("Event handler %s failed: %s", event.type, e, exc_info=True)
```

**Constant for subscription:**
```python
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
```

### Section 4: Split events.py (342 lines → 4 files)

```
agent/
├── _event_handlers.py     # ~100 lines — CLI/TUI event handlers
│   └── setup_event_handlers(agent)
│   └── _tool_call_args_summary(...)
│   └── _TOOL_ARG_SUMMARY_KEYS
│
├── _event_logging.py      # ~50 lines — Logging-only handlers
│   └── setup_logging_handlers(agent)
│
├── _trajectory.py         # ~100 lines — Trajectory recording
│   └── on_trajectory_event(agent, event)
│   └── ensure_trajectory_handlers(agent)
│   └── run_with_trajectory_if_enabled(agent, ...)
│   └── get_trajectory_dir(agent)
│
├── _assistant_events.py   # ~50 lines — Assistant-level event emission
│   └── emit_assistant_event(agent, event_name, payload)
│   └── messages_for_hook_payload(agent, messages)
```

### Section 5: Typed Handlers

**Before:**
```python
def on_text_delta(event):           # no type
    delta = event.get("delta", "")  # dict access

async def on_tool_call_start(event):
    tool_name = event.get("tool_name", "unknown")
    args = event.get("arguments", {}) or {}
```

**After:**
```python
from basket_ai.types import EventTextDelta
from basket_agent.types import AgentEventToolCallStart

def on_text_delta(event: EventTextDelta) -> None:
    delta = event.delta  # typed attribute

async def on_tool_call_start(event: AgentEventToolCallStart) -> None:
    tool_name = event.tool_name    # typed
    args = event.arguments         # Dict[str, Any], no None guard needed
```

### Section 6: Protocol Slimming

Move event/trajectory state out of `AssistantAgentProtocol`:

**Remove from Protocol:**
- `_assistant_event_handlers` → encapsulate in `_assistant_events.py` module state or a small `AssistantEventEmitter` class
- `_trajectory_recorder` → encapsulate in `_trajectory.py` module state or a `TrajectoryManager` class
- `_trajectory_handlers_registered` → same

**Protocol reduced from 17 → ~12 attributes.**

### Section 7: Naming Convention

Standardize on `agent_` prefix for all basket-agent events:
- `agent_tool_call_start` (already used)
- `agent_tool_call_end` (already used)
- `agent_turn_start`, `agent_turn_end`
- `agent_complete`, `agent_error`

LLM stream events keep their original names:
- `text_delta`, `thinking_delta` (from basket-ai, no `agent_` prefix)

This matches the current basket-agent naming. The `EVENT_TYPE_MAP` double mapping (`tool_call_start` → `ToolCallStartEvent` AND `agent_tool_call_start` → `ToolCallStartEvent`) is deleted.

## Files Affected

### basket-agent (modify)
- `agent_loop.py` — Remove `.model_dump()`, update return types
- `agent.py` — Change `_emit_event` signature from dict to typed
- `types.py` — No changes needed (already typed)

### basket-assistant (modify)
- `core/events/types.py` — **DELETE** (AssistantEvent classes)
- `core/events/publisher.py` — Simplify to single handler
- `core/events/__init__.py` — Update exports
- `agent/events.py` — Split into 4 files (see Section 4)
- `agent/_protocol.py` — Remove event/trajectory attributes
- `adapters/base.py` — Update type hints
- `adapters/cli.py` — Use typed events
- `adapters/tui.py` — Use typed events
- `adapters/webui.py` — Use typed events

### Tests (update)
- All event-related test files need mock updates (dict → typed objects)

## Migration Strategy

Phase order (each phase independently testable):

1. **basket-agent: Remove .model_dump()** — yield typed events, update Agent._emit_event
2. **basket-assistant: Update handlers** — change dict access to typed access in events.py
3. **Delete AssistantEvent** — remove types.py, event_from_dict, EVENT_TYPE_MAP
4. **Simplify EventPublisher** — replace 8 handlers with 1
5. **Split events.py** — extract into 4 focused files
6. **Slim Protocol** — extract event/trajectory state
7. **Update adapters** — typed event consumption
8. **Update tests** — mock typed events instead of dicts

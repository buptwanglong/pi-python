# Event System Refactor Design

**Date**: 2026-03-14
**Status**: Approved
**Author**: Claude (via brainstorming skill)

## Overview

Refactor basket-assistant event system to improve extensibility, maintainability, and ease of adding new UI modes (especially WebUI). Current system has three independent event systems with unclear boundaries, making it difficult to add new interfaces.

## Goals

**Primary Goals** (in priority order):
1. **Extensibility**: Adding new UI (e.g., WebUI) requires < 200 lines of code
2. **Clarity**: New team members understand event flow in < 30 minutes
3. **Testability**: Comprehensive test coverage for all UI adapters

**Success Metrics**:
- WebUI Adapter implementation: ~150 lines (Adapter + integration)
- Architecture has clear three-layer separation
- 85%+ test coverage for adapters, 90%+ for publisher

## Current Problems

### Three Independent Event Systems

1. **basket-ai**: LLM provider events (text_delta, thinking_delta)
2. **basket-agent**: Agent lifecycle events (agent_tool_call_start/end, agent_complete)
3. **basket-assistant**: Assistant-specific events (before_run, turn_done)

### UI Integration Inconsistency

- **CLI**: `setup_event_handlers()` directly prints to stdout
- **TUI**: `AgentEventBridge` converts agent events → TUI EventBus
- **Gateway**: `_ensure_event_sink_handlers()` sends to WebSocket

Each UI mode implements its own event listening logic with:
- ❌ Unclear responsibilities across layers
- ❌ Duplicate code (formatting, error handling)
- ❌ Tight coupling between agent and UI
- ❌ Difficult to debug event flow

## Proposed Solution: EventPublisher + Adapter Pattern

### Architecture

```
┌─────────────────────────────────────────┐
│     AssistantAgent (Business Logic)     │
│  - No knowledge of any UI               │
│  - Only runs agent and tools            │
└──────────────┬──────────────────────────┘
               │ Dependency Injection
         ┌─────▼──────┐
         │EventPublisher│
         │(Standardization Layer)           │
         │- Subscribes to basket-agent events│
         │- Publishes standardized AssistantEvent│
         └─────┬────────┘
               │ Observer Pattern
        ┌──────┼──────┬──────┐
    ┌───▼───┐ ┌─▼────┐ ┌─▼─────┐
    │CLI    │ │TUI   │ │WebUI  │
    │Adapter│ │Adapter│ │Adapter│
    └───┬───┘ └──┬───┘ └───┬───┘
        │        │          │
     Print   EventBus   WebSocket
```

**Key Principles**:
- AssistantAgent is completely unaware of UI existence (dependency inversion)
- EventPublisher is the only component that interacts with basket-agent
- Each Adapter is independent, testable, and replaceable

### Directory Structure

```
basket_assistant/
  core/
    events/
      __init__.py          # Public API exports
      types.py             # Event type definitions (150 lines)
      publisher.py         # EventPublisher (200 lines)
  adapters/
    __init__.py            # Public API exports
    base.py               # EventAdapter base class (30 lines)
    cli.py                # CLIAdapter (80 lines)
    tui.py                # TUIAdapter (100 lines)
    webui.py              # WebUIAdapter (80 lines)

tests/
  core/events/
    test_publisher.py     # Unit tests (200 lines)
  adapters/
    test_cli.py          # Unit tests (100 lines)
    test_tui.py          # Unit tests (100 lines)
    test_webui.py        # Unit tests (100 lines)
  integration/
    test_event_flow.py   # Integration tests (150 lines)
```

## Component Design

### 1. Standardized Event Types

All events inherit from `AssistantEvent` base class:

```python
@dataclass
class AssistantEvent:
    """Base class for all events"""
    type: str

@dataclass
class TextDeltaEvent(AssistantEvent):
    """LLM text streaming output"""
    type: str = "text_delta"
    delta: str = ""

@dataclass
class ThinkingDeltaEvent(AssistantEvent):
    """LLM thinking process streaming"""
    type: str = "thinking_delta"
    delta: str = ""

@dataclass
class ToolCallStartEvent(AssistantEvent):
    """Tool call started"""
    type: str = "tool_call_start"
    tool_name: str = ""
    arguments: Dict[str, Any] = None
    tool_call_id: str = ""

@dataclass
class ToolCallEndEvent(AssistantEvent):
    """Tool call completed"""
    type: str = "tool_call_end"
    tool_name: str = ""
    result: Any = None
    error: Optional[str] = None
    tool_call_id: str = ""

@dataclass
class AgentCompleteEvent(AssistantEvent):
    """Agent execution completed"""
    type: str = "agent_complete"

@dataclass
class AgentErrorEvent(AssistantEvent):
    """Agent execution error"""
    type: str = "agent_error"
    error: str = ""
```

### 2. EventPublisher

**Responsibilities**:
- Subscribe to basket-agent events
- Convert raw dict events to typed AssistantEvent instances
- Publish standardized events to subscribers
- Handle subscriber errors gracefully (don't let one adapter crash others)

**Key Methods**:
```python
class EventPublisher:
    def __init__(self, agent: Any)
    def subscribe(self, event_type: str, handler: Callable)
    def unsubscribe(self, event_type: str, handler: Callable)
    def _publish(self, event: AssistantEvent)  # Internal
```

**Error Handling**:
- Catch and log exceptions in subscriber handlers
- Continue notifying other subscribers if one fails
- Don't let event handling errors crash the agent

### 3. EventAdapter Base Class

**Responsibilities**:
- Define common interface for all adapters
- Manage subscription lifecycle
- Provide cleanup mechanism

```python
class EventAdapter(ABC):
    def __init__(self, publisher: EventPublisher)

    @abstractmethod
    def _setup_subscriptions(self):
        """Subclass implements: subscribe to needed event types"""
        pass

    def cleanup(self):
        """Clean up resources (unsubscribe)"""
        pass
```

### 4. Adapter Implementations

#### CLIAdapter (~80 lines)
- Subscribes to: text_delta, tool_call_start, tool_call_end
- Prints to stdout
- Respects verbose flag

#### TUIAdapter (~100 lines)
- Subscribes to: all event types
- Converts AssistantEvent → TUI EventBus events
- Replaces current `AgentEventBridge`

#### WebUIAdapter (~80 lines)
- Subscribes to: all event types
- Sends JSON over WebSocket
- Uses asyncio.create_task for non-blocking sends

## Data Flow

### Event Flow Diagram

```
User Input
   ↓
AssistantAgent.run()
   ↓
basket-agent execution
   ↓ (triggers events)
agent.on("text_delta")
agent.on("tool_call_start")
   ↓
EventPublisher._on_text_delta()
EventPublisher._on_tool_call_start()
   ↓ (standardize to AssistantEvent)
TextDeltaEvent(delta="hello")
ToolCallStartEvent(tool_name="bash")
   ↓ (publish to subscribers)
publisher._publish(event)
   ↓ (distribute to all adapters)
├─→ CLIAdapter._on_text_delta() → print()
├─→ TUIAdapter._on_text_delta() → event_bus.publish()
└─→ WebUIAdapter._on_text_delta() → websocket.send()
```

**Performance**:
- Time complexity: O(n) where n = number of adapters (typically 1-3)
- Latency: < 0.1ms (synchronous calls, no serialization overhead)

### Usage Examples

**CLI Mode**:
```python
async def run_cli_mode(agent):
    publisher = EventPublisher(agent.agent)
    cli_adapter = CLIAdapter(publisher, verbose=agent.settings.agent.verbose)

    await agent.run()

    cli_adapter.cleanup()
```

**TUI Mode**:
```python
async def run_tui_mode(agent, app):
    publisher = EventPublisher(agent.agent)
    tui_adapter = TUIAdapter(publisher, app.event_bus)

    await agent.run()

    tui_adapter.cleanup()
```

**WebUI Mode (NEW)**:
```python
async def handle_websocket(websocket, agent):
    publisher = EventPublisher(agent.agent)
    webui_adapter = WebUIAdapter(publisher, websocket.send)

    try:
        async for message in websocket:
            await agent.run(message)
    finally:
        webui_adapter.cleanup()
```

## Migration Strategy

### Phase 1: Add New Architecture (No Breaking Changes)

- Create `core/events/` and `adapters/` directories
- Implement EventPublisher and all adapters
- CLI/TUI/Gateway continue using existing approach
- New code (WebUI) uses new architecture
- **Duration**: 1-2 weeks

### Phase 2: Gradual Migration

- Migrate CLI to CLIAdapter
- Migrate TUI to TUIAdapter
- Migrate Gateway to WebUIAdapter
- Run both old and new systems in parallel during transition
- **Duration**: 1-2 weeks

### Phase 3: Cleanup

- Delete old event handling code in `agent/events.py`
- Delete `AgentEventBridge` in basket-tui
- Remove deprecated imports
- **Duration**: 1 week

## Error Handling

### EventPublisher Layer

```python
def _publish(self, event: AssistantEvent):
    """Publish event, catch handler exceptions to avoid affecting other subscribers"""
    for handler in self._subscribers.get(event.type, []):
        try:
            handler(event)
        except Exception as e:
            logger.error(
                "Event handler failed: type=%s handler=%s error=%s",
                event.type, handler.__name__, e,
                exc_info=True
            )
            # Don't raise, continue notifying other subscribers
```

### Adapter Layer

```python
def _on_text_delta(self, event: TextDeltaEvent):
    try:
        asyncio.create_task(self.send({
            "type": "text_delta",
            "delta": event.delta
        }))
    except Exception as e:
        logger.error("WebSocket send failed: %s", e)
        # Unsubscribe when WebSocket disconnects
        self.cleanup()
```

**Principles**:
- ❌ Don't let single adapter failure affect others
- ❌ Don't let event handling errors crash agent
- ✅ Log detailed errors for debugging

## Testing Strategy

### Unit Tests

**EventPublisher Tests** (`test_publisher.py`):
- Correct conversion of agent events to AssistantEvent
- Proper event distribution to multiple subscribers
- Error handling when subscriber throws exception
- Subscribe/unsubscribe lifecycle
- **Target Coverage**: 90%+

**Adapter Tests** (`test_cli.py`, `test_tui.py`, `test_webui.py`):
- Correct handling of each event type
- Output format verification (print/EventBus/WebSocket)
- Error handling (e.g., WebSocket disconnect)
- Cleanup/unsubscribe behavior
- **Target Coverage**: 85%+

### Integration Tests

**End-to-End Flow** (`test_event_flow.py`):
- Complete flow from agent execution → UI output
- Multiple adapters running simultaneously
- Event ordering and timing
- Real agent execution with mocked LLM
- **Scenarios**: CLI mode, TUI mode, WebUI mode

### Test Code Estimate

- EventPublisher tests: 200 lines
- Adapter tests: 100 lines each (300 total)
- Integration tests: 150 lines
- **Total**: ~650 lines of test code

## Performance Considerations

### Synchronous vs Asynchronous

**Synchronous publish** (for CLI/TUI):
```python
def _publish(self, event: AssistantEvent):
    for handler in self._subscribers.get(event.type, []):
        handler(event)
```

**Async publish support** (for WebSocket):
```python
async def _publish_async(self, event: AssistantEvent):
    tasks = []
    for handler in self._subscribers.get(event.type, []):
        if asyncio.iscoroutinefunction(handler):
            tasks.append(handler(event))
        else:
            handler(event)
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
```

### Optimizations

- **Lazy loading**: Only create adapters when needed
- **Event batching**: Optional batch mode for high-frequency events (text_delta)
- **Subscription filtering**: Adapters only subscribe to events they need

## Future Extensions

### Event Filtering

```python
publisher.subscribe(
    "tool_call_start",
    handler,
    filter=lambda e: e.tool_name == "bash"  # Only bash tool events
)
```

### Event Transformation

```python
publisher.subscribe(
    "text_delta",
    handler,
    transform=lambda e: TextDeltaEvent(delta=e.delta.upper())  # Uppercase
)
```

### Event Recording/Replay

```python
recorder = EventRecorder(publisher)
recorder.start()
# ... agent execution ...
recorder.stop()
recorder.save("session.jsonl")

# Replay
replayer = EventReplayer("session.jsonl")
replayer.replay(webui_adapter)  # Replay in WebUI
```

### Multi-Agent Support

```python
# Each agent has its own publisher
publisher_1 = EventPublisher(agent_1)
publisher_2 = EventPublisher(agent_2)

# Same adapter listens to multiple publishers
adapter = WebUIAdapter([publisher_1, publisher_2], websocket.send)
```

## Implementation Checklist

**Phase 1: New Architecture** (Week 1-2)
- [ ] Create `core/events/types.py` with event type definitions
- [ ] Create `core/events/publisher.py` with EventPublisher
- [ ] Create `adapters/base.py` with EventAdapter base class
- [ ] Create `adapters/cli.py` with CLIAdapter
- [ ] Create `adapters/tui.py` with TUIAdapter
- [ ] Create `adapters/webui.py` with WebUIAdapter
- [ ] Write unit tests for EventPublisher (90%+ coverage)
- [ ] Write unit tests for each adapter (85%+ coverage)
- [ ] Write integration tests for end-to-end flow

**Phase 2: Migration** (Week 3-4)
- [ ] Update CLI mode to use CLIAdapter
- [ ] Update TUI mode to use TUIAdapter
- [ ] Update Gateway to use WebUIAdapter
- [ ] Verify all existing functionality works
- [ ] Run parallel testing (old vs new system)

**Phase 3: Cleanup** (Week 5)
- [ ] Delete `basket_assistant/agent/events.py` (old event handlers)
- [ ] Delete `basket_tui/managers/agent_bridge.py` (replaced by TUIAdapter)
- [ ] Remove deprecated imports
- [ ] Update documentation
- [ ] Code review and final testing

## Risks and Mitigations

### Risk: Breaking Existing UI Modes During Migration

**Mitigation**:
- Phase 1 adds new code without touching existing code
- Phase 2 runs old and new systems in parallel
- Comprehensive integration tests verify behavior parity

### Risk: Performance Regression

**Mitigation**:
- Synchronous publish for low-latency UI (CLI/TUI)
- Benchmark event latency before/after migration
- Optimize if latency > 0.1ms

### Risk: Complex Event Ordering Issues

**Mitigation**:
- Events published in same order as received from agent
- Integration tests verify event ordering
- Document event flow clearly

## Success Criteria

✅ **WebUI Implementation < 200 lines**: WebUIAdapter (80) + integration (70) = 150 lines
✅ **Understandable in 30 minutes**: Three-layer architecture with clear boundaries
✅ **Test Coverage**: 650+ lines of test code, 85%+ adapter coverage, 90%+ publisher coverage
✅ **No Breaking Changes**: Existing CLI/TUI/Gateway continue working during migration
✅ **Performance**: Event latency < 0.1ms (same as current implementation)

## Conclusion

This design refactors the event system to be extensible, maintainable, and easy to understand. The EventPublisher + Adapter pattern provides clear separation of concerns, making it trivial to add new UI modes while keeping the agent logic completely decoupled from UI concerns.

The three-phase migration ensures a smooth transition without breaking existing functionality, and comprehensive testing guarantees reliability throughout the process.

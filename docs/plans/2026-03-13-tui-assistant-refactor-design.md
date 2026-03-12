# Basket TUI & Assistant Refactoring Design

**Date:** 2026-03-13
**Author:** Claude (brainstorming skill)
**Status:** Approved

---

## Executive Summary

This design document outlines a comprehensive refactoring of `basket-tui` and `basket-assistant` to address critical architectural issues identified in the code review:

- **P0 (Critical)**: Mixin hell (8-layer inheritance), state management chaos, immutability violations
- **P1 (High)**: Tight coupling, incomplete error handling, event handler complexity
- **P2 (Medium)**: Type safety issues, Textual framework underutilization, long functions

**Approach:** Big-bang rewrite using component-based architecture with:
- Composition over inheritance
- State machine pattern
- Event bus with typed events
- Textual reactive properties
- TDD methodology

---

## Design Decisions

### Key Constraints

| Decision Point | Choice | Rationale |
|----------------|--------|-----------|
| **Backward Compatibility** | Option B: Breaking changes allowed | Enables cleanest architecture, no legacy constraints |
| **Component Granularity** | Option B: Medium (6-8 managers) | Balance between single responsibility and pragmatism |
| **State Management** | Option B: State machine + context | Enforced transition rules, type-safe phases |
| **Event Handling** | Option B: Event bus + typed events | Decoupling, testability, middleware support |
| **Textual Optimization** | Option B: Use reactive properties | Declarative, automatic refresh optimization |
| **Migration Strategy** | Option A: Big-bang rewrite | Fastest path to target architecture |
| **Testing Strategy** | Option B: TDD approach | Test-driven design, continuous verification |

---

## Architecture Overview

### Component-Based Architecture

```
basket_tui/
├── core/                    # Core abstractions
│   ├── state_machine.py     # AppStateMachine, Phase enum
│   ├── conversation.py      # Message, ConversationContext (immutable)
│   ├── streaming.py         # StreamingState
│   ├── events.py            # Typed event definitions
│   └── event_bus.py         # EventBus implementation
│
├── components/              # Reactive Textual Widgets
│   ├── message_list.py      # MessageList (reactive messages)
│   ├── streaming_display.py # StreamingDisplay (reactive buffer)
│   ├── tool_display.py      # ToolDisplay (reactive tool state)
│   └── input_box.py         # MultiLineInput (future)
│
├── managers/                # Business logic managers
│   ├── layout_manager.py    # UI layout and composition
│   ├── message_renderer.py  # Message display logic
│   ├── streaming_controller.py # Streaming output control
│   ├── input_handler.py     # User input + slash commands
│   ├── session_controller.py # Session switching
│   └── agent_bridge.py      # Agent event bridging
│
└── app.py                   # PiCodingAgentApp (orchestrator)
```

**Dependency Flow:**
```
App → Managers → [EventBus, StateMachine, Components]
     ↓
Components (reactive) ← Events published via EventBus
```

---

## Detailed Design

### 1. Core State Management

#### 1.1 State Machine

```python
class Phase(Enum):
    IDLE = "idle"
    WAITING_MODEL = "waiting_model"
    THINKING = "thinking"
    STREAMING = "streaming"
    TOOL_RUNNING = "tool_running"
    ERROR = "error"

class AppStateMachine:
    def __init__(self):
        self._phase = Phase.IDLE

    def transition_to(self, new_phase: Phase) -> None:
        """Validates and transitions to new phase"""
        if new_phase not in VALID_TRANSITIONS.get(self._phase, set()):
            raise InvalidStateTransition(...)
        self._phase = new_phase
```

**Valid Transitions:**
- `IDLE` → `WAITING_MODEL`
- `WAITING_MODEL` → `THINKING | STREAMING | TOOL_RUNNING | ERROR | IDLE`
- `THINKING` → `STREAMING | TOOL_RUNNING | ERROR | IDLE`
- `STREAMING` → `TOOL_RUNNING | IDLE | ERROR`
- `TOOL_RUNNING` → `STREAMING | IDLE | ERROR`
- `ERROR` → `IDLE`

**Benefits:**
- ✅ Compile-time type safety (enum)
- ✅ Runtime validation of transitions
- ✅ Clear state lifecycle

#### 1.2 Immutable Conversation Context

```python
@dataclass(frozen=True)
class Message:
    role: str
    content: str
    timestamp: float
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None

@dataclass(frozen=True)
class ConversationContext:
    messages: tuple[Message, ...] = field(default_factory=tuple)

    def add_message(self, message: Message) -> 'ConversationContext':
        """Returns new context with added message"""
        return ConversationContext(messages=self.messages + (message,))
```

**Benefits:**
- ✅ No accidental mutations
- ✅ Easy to snapshot/restore
- ✅ Thread-safe by design

#### 1.3 Streaming State (Mutable)

```python
@dataclass
class StreamingState:
    buffer: str = ""
    is_active: bool = False
    length_rendered: int = 0

    def append(self, text: str) -> None:
        """Append text to buffer"""
        self.buffer += text
```

**Rationale for mutability:** High-frequency updates (~80ms intervals) make immutability impractical for streaming buffer.

---

### 2. Event System

#### 2.1 Typed Events

```python
@dataclass
class Event:
    timestamp: float = time.time()

# Agent events
@dataclass
class TextDeltaEvent(Event):
    delta: str

@dataclass
class ThinkingDeltaEvent(Event):
    delta: str

@dataclass
class ToolCallStartEvent(Event):
    tool_name: str
    arguments: dict

@dataclass
class ToolCallEndEvent(Event):
    tool_name: str
    result: Any
    error: Optional[str] = None

# UI events
@dataclass
class UserInputEvent(Event):
    text: str

@dataclass
class PhaseChangedEvent(Event):
    old_phase: Phase
    new_phase: Phase
```

**Benefits:**
- ✅ Type-safe event payloads
- ✅ Auto-completion in IDEs
- ✅ Clear event contracts

#### 2.2 Event Bus

```python
class EventBus:
    def __init__(self):
        self._handlers: Dict[Type[Event], List[Callable]] = {}

    def subscribe(self, event_type: Type[E], handler: Callable[[E], None]) -> None:
        """Subscribe to event type"""
        ...

    def publish(self, event: Event) -> None:
        """Publish event to all subscribers"""
        ...
```

**Features:**
- ✅ Decouples publishers from subscribers
- ✅ Supports multiple handlers per event
- ✅ Exception isolation (one handler failure doesn't affect others)

#### 2.3 Agent Event Bridge

```python
class AgentEventBridge:
    def connect_agent(self, agent: Agent) -> None:
        """Connect Agent and map events to TUI events"""
        agent.on("text_delta", self._on_text_delta)
        agent.on("thinking_delta", self._on_thinking_delta)
        agent.on("agent_tool_call_start", self._on_tool_call_start)
        agent.on("agent_tool_call_end", self._on_tool_call_end)

    def _on_text_delta(self, event: dict) -> None:
        self._event_bus.publish(TextDeltaEvent(delta=event.get("delta", "")))
```

**Benefits:**
- ✅ Isolates Agent API from TUI internals
- ✅ Single point of integration
- ✅ Easy to mock for testing

---

### 3. Reactive Widgets

#### 3.1 MessageList Widget

```python
class MessageList(Widget):
    messages: reactive[List[Message]] = reactive(list, init=False)

    def watch_messages(self, old: List[Message], new: List[Message]) -> None:
        """Auto-called when messages change"""
        self.refresh()

    def add_message(self, message: Message) -> None:
        """Trigger reactive update"""
        self.messages = self.messages + [message]  # New list triggers update
```

**Key Insight:** Reassigning the list (not mutating it) triggers Textual's reactive system.

#### 3.2 StreamingDisplay Widget

```python
class StreamingDisplay(Widget):
    buffer: reactive[str] = reactive("", init=False)
    is_active: reactive[bool] = reactive(False, init=False)

    def watch_buffer(self, old: str, new: str) -> None:
        """Auto-refresh on buffer change"""
        if self.is_active:
            self.refresh()

    def watch_is_active(self, old: bool, new: bool) -> None:
        """Show/hide widget on activation"""
        self.display = new
```

**Benefits:**
- ✅ Declarative updates (no manual Timer management)
- ✅ Automatic batching by Textual
- ✅ Built-in performance optimization

#### 3.3 ToolDisplay Widget

```python
class ToolDisplay(Static):
    tool_name: reactive[str] = reactive("", init=False)
    is_running: reactive[bool] = reactive(False, init=False)
    tool_result: reactive[Optional[str]] = reactive(None, init=False)
    has_error: reactive[bool] = reactive(False, init=False)

    def watch_tool_result(self, old: Optional[str], new: Optional[str]) -> None:
        if new is not None:
            self.is_running = False
            self.refresh()
```

**Features:**
- ✅ Self-contained state (no external state leakage)
- ✅ Automatic rendering on state change
- ✅ Clear visual feedback (⏳ running, ✅ success, ❌ error)

---

### 4. Manager Layer

#### 4.1 MessageRenderer

**Responsibilities:**
- Maintain immutable ConversationContext
- Add user/system/assistant messages
- Subscribe to Agent events (TextDeltaEvent, AgentCompleteEvent)
- Update MessageList and StreamingDisplay widgets

**Key Methods:**
```python
def add_user_message(self, text: str) -> None
def add_system_message(self, text: str) -> None
def clear_conversation(self) -> None
def _on_text_delta(self, event: TextDeltaEvent) -> None
def _on_agent_complete(self, event: AgentCompleteEvent) -> None
```

#### 4.2 StreamingController

**Responsibilities:**
- Manage StreamingState lifecycle
- Control streaming activation/deactivation
- Subscribe to TextDeltaEvent

**Key Methods:**
```python
def activate(self) -> None
def deactivate(self) -> None
def _on_text_delta(self, event: TextDeltaEvent) -> None
```

#### 4.3 InputHandler

**Responsibilities:**
- Process user input
- Handle slash commands (/clear, /help, /sessions, /new)
- Publish UserInputEvent
- Call external callback (for Agent integration)

**Slash Commands:**
```python
/clear      # Clear conversation
/sessions   # Show session picker
/new        # Create new session
/help       # Show help
```

#### 4.4 SessionController

**Responsibilities:**
- Session creation and switching
- Load/persist session history
- Publish SessionSwitchEvent

**Key Methods:**
```python
async def create_new_session(self) -> None
async def switch_to_session(self, session_id: str) -> None
async def show_session_picker(self) -> None
```

#### 4.5 LayoutManager

**Responsibilities:**
- Compose UI layout (Header, ScrollableContainer, Footer)
- Update status bar (phase, model, session)

**Layout:**
```
Header
ScrollableContainer
  ├── MessageList
  ├── StreamingDisplay
  └── ToolDisplay
StatusBar (Horizontal)
  ├── Phase
  ├── Model
  └── Session
Footer
```

---

### 5. Main Application

#### 5.1 PiCodingAgentApp

**Architecture:**
```python
class PiCodingAgentApp(App):
    def __init__(self, agent=None, coding_agent=None, max_cols=None):
        # Core components
        self.event_bus = EventBus()
        self.state_machine = AppStateMachine()

        # Managers (composition, not inheritance)
        self.layout_manager = LayoutManager(self)
        self.message_renderer = MessageRenderer(self)
        self.streaming_controller = StreamingController(self)
        self.input_handler = InputHandler(self)
        self.session_controller = SessionController(self, coding_agent)
        self.agent_bridge = AgentEventBridge(self)

        # Connect Agent
        if agent:
            self.agent_bridge.connect_agent(agent)
```

**Key Principles:**
- ✅ **Single Responsibility**: Each manager handles one domain
- ✅ **Dependency Injection**: Managers receive dependencies via constructor
- ✅ **Event-Driven**: Managers communicate via EventBus, not direct calls
- ✅ **Testability**: Each manager can be unit-tested independently

#### 5.2 Integration with basket-assistant

**New Integration Layer:**
```python
# basket_assistant/modes/tui_v2.py

async def run_tui_mode(coding_agent, max_cols=None) -> None:
    # Create TUI app
    app = PiCodingAgentApp(
        agent=coding_agent.agent,
        coding_agent=coding_agent,
        max_cols=max_cols
    )

    # Handle user input
    async def handle_user_input(text: str) -> None:
        coding_agent.context.messages.append(UserMessage(role="user", content=text))
        app.transition_phase(Phase.WAITING_MODEL)

        try:
            await coding_agent._run_with_trajectory_if_enabled(stream_llm_events=True)
        except Exception as e:
            logger.exception("Agent run failed")
            app.message_renderer.add_system_message(f"Error: {e}")
        finally:
            app.transition_phase(Phase.IDLE)

    # Subscribe to user input events
    app.event_bus.subscribe(UserInputEvent, lambda e: asyncio.create_task(handle_user_input(e.text)))
    app.input_handler.set_callback(handle_user_input)

    # Load history and run
    # ... (load history messages)
    await app.run_async()
```

**Changes to basket-assistant:**
- Replace `modes/tui.py` (429 lines) with `modes/tui_v2.py` (~100 lines)
- Remove `_connect_agent_handlers` function (event bridge handles this)
- Simplify error handling (state restored automatically via immutable context)

---

## Migration Strategy

### Big-Bang Rewrite Approach

**Phase 1: Core + Tests (Week 1)**
1. Implement `core/` modules:
   - `state_machine.py` with tests
   - `conversation.py` with tests
   - `streaming.py` with tests
   - `events.py` (definitions only)
   - `event_bus.py` with tests

**Phase 2: Components + Tests (Week 1)**
2. Implement reactive widgets:
   - `components/message_list.py` with tests
   - `components/streaming_display.py` with tests
   - `components/tool_display.py` with tests

**Phase 3: Managers + Tests (Week 2)**
3. Implement managers:
   - `managers/layout_manager.py`
   - `managers/message_renderer.py` with tests
   - `managers/streaming_controller.py` with tests
   - `managers/input_handler.py` with tests
   - `managers/agent_bridge.py` with tests
   - `managers/session_controller.py` with tests

**Phase 4: Integration (Week 2)**
4. Main app assembly:
   - `app.py` (compose all managers)
   - `modes/tui_v2.py` (basket-assistant integration)
   - Integration tests
   - Manual testing with real Agent

**Phase 5: Cutover (Week 3)**
5. Replace old code:
   - Delete all 8 Mixin files
   - Delete `modes/tui.py`
   - Rename `tui_v2.py` → `tui.py`
   - Update all imports
   - Update documentation

---

## Testing Strategy

### TDD Workflow

**For each component:**
1. Write test first (RED)
2. Implement minimal code to pass (GREEN)
3. Refactor (REFACTOR)
4. Verify test still passes

### Test Coverage Goals

| Component | Coverage Target | Test Types |
|-----------|----------------|------------|
| `core/state_machine.py` | 100% | Unit: valid/invalid transitions |
| `core/event_bus.py` | 100% | Unit: subscribe, publish, exception handling |
| `core/conversation.py` | 100% | Unit: immutability, add_message |
| `components/*` | 90%+ | Unit: reactive property changes |
| `managers/*` | 85%+ | Unit + Integration: event subscriptions |
| `app.py` | 70%+ | Integration: end-to-end flows |

### Example Test: State Machine

```python
# tests/core/test_state_machine.py

import pytest
from basket_tui.core.state_machine import AppStateMachine, Phase, InvalidStateTransition

class TestAppStateMachine:
    def test_initial_state_is_idle(self):
        sm = AppStateMachine()
        assert sm.current_phase == Phase.IDLE

    def test_valid_transition_idle_to_waiting(self):
        sm = AppStateMachine()
        sm.transition_to(Phase.WAITING_MODEL)
        assert sm.current_phase == Phase.WAITING_MODEL

    def test_invalid_transition_idle_to_streaming_raises_error(self):
        sm = AppStateMachine()
        with pytest.raises(InvalidStateTransition):
            sm.transition_to(Phase.STREAMING)

    def test_can_transition_to_returns_true_for_valid(self):
        sm = AppStateMachine()
        assert sm.can_transition_to(Phase.WAITING_MODEL) is True

    def test_can_transition_to_returns_false_for_invalid(self):
        sm = AppStateMachine()
        assert sm.can_transition_to(Phase.STREAMING) is False
```

---

## Error Handling

### Comprehensive Error Strategy

**Principle:** Fail fast, log thoroughly, recover gracefully.

#### 1. State Machine Errors

```python
try:
    app.state_machine.transition_to(Phase.STREAMING)
except InvalidStateTransition as e:
    logger.error(f"Invalid state transition: {e}")
    app.message_renderer.add_system_message("Internal state error, resetting...")
    app.state_machine.reset()  # Force reset to IDLE
```

#### 2. Agent Errors

```python
async def handle_user_input(text: str):
    try:
        await coding_agent._run_with_trajectory_if_enabled(stream_llm_events=True)
    except asyncio.CancelledError:
        logger.info("Agent cancelled by user")
        app.message_renderer.add_system_message("Stopped by user")
    except Exception as e:
        logger.exception(f"Agent run failed: {e}")
        app.message_renderer.add_system_message("An error occurred. Context preserved.")
    finally:
        app.transition_phase(Phase.IDLE)
```

**Key Points:**
- ✅ No context mutation on error (immutable ConversationContext)
- ✅ User-friendly error messages (no stack traces in UI)
- ✅ Always log exceptions with full traceback
- ✅ Always transition back to IDLE in finally block

#### 3. Event Handler Errors

```python
# In EventBus.publish()
for handler in handlers:
    try:
        handler(event)
    except Exception as e:
        logger.exception(f"Error in handler for {event_type.__name__}: {e}")
        # Continue processing other handlers
```

**Rationale:** One handler failure shouldn't cascade to other subscribers.

---

## Type Safety Improvements

### Protocol-Based Tool Results

**Problem:** Current code uses `result: any` and runtime `isinstance()` checks.

**Solution:** Define protocols for tool results.

```python
# basket_assistant/tools/protocols.py

from typing import Protocol

class ToolResult(Protocol):
    """Base protocol for tool results"""
    def format_display(self) -> str:
        """Format for display in TUI"""
        ...

class BashResult:
    stdout: str
    stderr: str
    exit_code: int
    timeout: bool

    def format_display(self) -> str:
        parts = []
        if self.timeout:
            parts.append("Command timed out")
        parts.append(f"exit {self.exit_code}")
        if self.stdout:
            parts.append(f"\n{self.stdout[:1000]}")
        return "\n".join(parts)

class ReadResult:
    file_path: str
    lines: int
    content: str

    def format_display(self) -> str:
        preview = "\n".join(self.content.split("\n")[:5])
        return f"Read {self.lines} lines from {self.file_path}\n{preview}"
```

**Usage in ToolDisplay:**
```python
def show_result(self, result: ToolResult) -> None:
    self.tool_result = result.format_display()
```

**Benefits:**
- ✅ Type-checked at compile time (mypy)
- ✅ Single method for formatting
- ✅ Easy to add new tool types

---

## Performance Optimizations

### Textual Reactive Properties

**Before (manual Timer management):**
```python
def append_text(self, text: str):
    self.streaming_buffer += text
    if self._timer is None:
        self._timer = self.set_timer(0.08, self._refresh)
```

**After (reactive properties):**
```python
class StreamingDisplay(Widget):
    buffer: reactive[str] = reactive("")

    def watch_buffer(self, old: str, new: str):
        self.refresh()  # Textual batches these automatically
```

**Benefits:**
- ✅ Textual handles debouncing internally
- ✅ No manual Timer lifecycle management
- ✅ Fewer bugs (no timer leaks)

### Widget Lifecycle

**Optimization:** Hide inactive widgets instead of destroying/recreating.

```python
def watch_is_active(self, old: bool, new: bool):
    self.display = new  # CSS display: none (no render cost)
```

---

## Documentation Updates

### Files to Update

1. **`basket-tui/README.md`**
   - Remove Mixin architecture description
   - Add component-based architecture section
   - Update usage examples

2. **`basket-assistant/README.md`**
   - Update TUI mode description
   - Document new event system

3. **`CLAUDE.md`**
   - Update architecture section
   - Remove Mixin references
   - Add state machine and event bus sections

4. **New: `basket-tui/docs/ARCHITECTURE.md`**
   - Detailed component descriptions
   - Event flow diagrams
   - Extension guide

---

## Success Criteria

### Functional Requirements

- ✅ All existing TUI features work (streaming, tool display, sessions)
- ✅ No regressions in user-facing behavior
- ✅ Slash commands function correctly
- ✅ Session persistence works

### Non-Functional Requirements

- ✅ **Code Quality:**
  - All files under 300 lines (most under 150)
  - No Mixin classes
  - No mutable default arguments
  - No magic numbers

- ✅ **Test Coverage:**
  - Overall: 80%+
  - Core modules: 95%+
  - Managers: 85%+

- ✅ **Performance:**
  - Streaming latency ≤ 100ms
  - UI responsiveness maintained under high load

- ✅ **Type Safety:**
  - `mypy --strict` passes with no errors
  - All events and states strongly typed

---

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Big-bang approach fails to integrate | High | Medium | TDD ensures each component works; integration tests catch issues early |
| Textual reactive properties have edge cases | Medium | Low | Extensive testing of reactive behavior; fallback to Timer if needed |
| Performance regression in streaming | Medium | Low | Benchmark streaming latency; optimize reactive updates if needed |
| Breaking changes disrupt users | Low | High (expected) | Document migration in release notes; provide clear error messages |

---

## Timeline

**Estimated Duration:** 2-3 weeks (single developer)

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| Core + Tests | 3 days | State machine, event bus, conversation context with 100% coverage |
| Components + Tests | 2 days | Reactive widgets with 90%+ coverage |
| Managers + Tests | 4 days | All 6 managers with 85%+ coverage |
| Integration | 3 days | Main app, basket-assistant integration, integration tests |
| Cutover + Polish | 2 days | Delete old code, update docs, final testing |

---

## Appendix: File Size Comparison

### Before (Current)

```
app.py                        136 lines (Mixin composition)
app_layout.py                 257 lines
app_scroll_focus.py           222 lines
app_output_messages.py        222 lines
app_session_model.py          103 lines
app_agent.py                   50 lines
app_slash.py                  199 lines
app_input.py                   55 lines
app_actions.py                136 lines
state.py                      198 lines
modes/tui.py                  429 lines
---------------------------------------------
TOTAL (TUI + modes)          2007 lines
```

### After (Target)

```
core/
  state_machine.py             ~80 lines
  conversation.py              ~60 lines
  streaming.py                 ~40 lines
  events.py                    ~80 lines
  event_bus.py                 ~60 lines

components/
  message_list.py              ~80 lines
  streaming_display.py         ~100 lines
  tool_display.py              ~120 lines

managers/
  layout_manager.py            ~100 lines
  message_renderer.py          ~140 lines
  streaming_controller.py      ~80 lines
  input_handler.py             ~120 lines
  session_controller.py        ~100 lines
  agent_bridge.py              ~100 lines

app.py                         ~150 lines
modes/tui_v2.py                ~100 lines
---------------------------------------------
TOTAL                         ~1510 lines
```

**Reduction:** ~500 lines (25% decrease) with clearer structure.

---

## Conclusion

This refactoring addresses all identified issues (P0, P1, P2) through a clean component-based architecture. The use of composition, state machines, event buses, and reactive properties provides a maintainable, testable, and performant foundation for future development.

**Key Wins:**
1. ✅ Eliminated Mixin hell → Composition with 6 focused managers
2. ✅ Fixed state chaos → State machine with enforced transitions
3. ✅ Decoupled components → Event bus with typed events
4. ✅ Optimized Textual usage → Reactive properties replace manual Timers
5. ✅ Improved type safety → Protocols for tool results, dataclass events
6. ✅ TDD approach → 80%+ coverage, continuous validation

**Next Steps:** Invoke `writing-plans` skill to create detailed implementation plan.

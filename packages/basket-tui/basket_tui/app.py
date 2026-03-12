"""
Pi Coding Agent TUI Application

Component-based architecture with event bus communication.
"""

import asyncio
from typing import Optional
from textual.app import App, ComposeResult
from textual.binding import Binding

from .core.state_machine import AppStateMachine, Phase
from .core.event_bus import EventBus
from .core.events import PhaseChangedEvent
from .managers import (
    LayoutManager,
    MessageRenderer,
    StreamingController,
    InputHandler,
    SessionController,
    AgentEventBridge,
)


class PiCodingAgentApp(App):
    """
    Pi Coding Agent TUI Application

    Uses composition pattern with managers instead of Mixin inheritance.
    Communication via EventBus for decoupled components.
    """

    TITLE = "Pi Coding Agent"
    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear", "Clear"),
        Binding("ctrl+p", "sessions", "Sessions"),
        Binding("ctrl+d", "toggle_dark", "Dark Mode"),
        Binding("ctrl+g", "stop_agent", "Stop"),
    ]

    def __init__(
        self,
        agent=None,
        coding_agent=None,
        max_cols: Optional[int] = None,
        **kwargs,
    ):
        """
        Initialize TUI app

        Args:
            agent: basket_agent.Agent instance
            coding_agent: basket_assistant.AssistantAgent instance
            max_cols: Maximum column width
        """
        super().__init__(**kwargs)

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

        # Configuration
        self._max_cols = max_cols
        self._agent = agent
        self._coding_agent = coding_agent

        # Subscribe to state changes
        self.event_bus.subscribe(PhaseChangedEvent, self._on_phase_changed)

    def compose(self) -> ComposeResult:
        """Compose UI components"""
        yield from self.layout_manager.compose()

    def on_mount(self) -> None:
        """Initialize app on mount"""
        # Show welcome message
        self.message_renderer.add_system_message(
            "Welcome to Pi Coding Agent! Type /help for commands."
        )

        # Initialize status bar
        model_name = (
            getattr(self._agent, "model", {}).get("model_id", "Unknown")
            if self._agent
            else "Unknown"
        )
        self.layout_manager.update_status_bar(
            phase=self.state_machine.current_phase.value, model=model_name
        )

    async def action_clear(self) -> None:
        """Clear conversation"""
        self.message_renderer.clear_conversation()

    async def action_sessions(self) -> None:
        """Show session picker"""
        await self.session_controller.show_session_picker()

    async def action_stop_agent(self) -> None:
        """Stop agent execution"""
        if self._agent and hasattr(self._agent, "cancel"):
            self._agent.cancel()
        self.message_renderer.add_system_message("Agent stopped")

    def transition_phase(self, new_phase: Phase) -> None:
        """
        Transition to new phase

        Args:
            new_phase: Target phase
        """
        old_phase = self.state_machine.current_phase

        try:
            self.state_machine.transition_to(new_phase)

            # Publish phase change event
            self.event_bus.publish(
                PhaseChangedEvent(old_phase=old_phase, new_phase=new_phase)
            )
        except Exception as e:
            self.message_renderer.add_system_message(
                f"Phase transition error: {e}"
            )

    def _on_phase_changed(self, event: PhaseChangedEvent) -> None:
        """Update UI on phase change"""
        self.layout_manager.update_status_bar(phase=event.new_phase.value)


if __name__ == "__main__":
    app = PiCodingAgentApp()
    app.run()

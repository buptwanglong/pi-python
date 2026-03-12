"""
State Machine for TUI Application

Manages application phase transitions with validation.
"""

from enum import Enum
from typing import Set, Dict


class Phase(Enum):
    """Application phase enumeration"""

    IDLE = "idle"
    WAITING_MODEL = "waiting_model"
    THINKING = "thinking"
    STREAMING = "streaming"
    TOOL_RUNNING = "tool_running"
    ERROR = "error"


# Define valid state transitions
VALID_TRANSITIONS: Dict[Phase, Set[Phase]] = {
    Phase.IDLE: {Phase.WAITING_MODEL},
    Phase.WAITING_MODEL: {
        Phase.THINKING,
        Phase.STREAMING,
        Phase.TOOL_RUNNING,
        Phase.ERROR,
        Phase.IDLE,
    },
    Phase.THINKING: {
        Phase.STREAMING,
        Phase.TOOL_RUNNING,
        Phase.ERROR,
        Phase.IDLE,
    },
    Phase.STREAMING: {
        Phase.TOOL_RUNNING,
        Phase.IDLE,
        Phase.ERROR,
    },
    Phase.TOOL_RUNNING: {
        Phase.STREAMING,
        Phase.IDLE,
        Phase.ERROR,
    },
    Phase.ERROR: {Phase.IDLE},
}


class InvalidStateTransition(Exception):
    """Raised when attempting an invalid state transition"""

    pass


class AppStateMachine:
    """
    Application state machine

    Manages conversation phase with validated transitions.
    """

    def __init__(self):
        self._phase = Phase.IDLE

    @property
    def current_phase(self) -> Phase:
        """Get current phase"""
        return self._phase

    def transition_to(self, new_phase: Phase) -> None:
        """
        Transition to new phase

        Args:
            new_phase: Target phase

        Raises:
            InvalidStateTransition: If transition is not allowed
        """
        if new_phase not in VALID_TRANSITIONS.get(self._phase, set()):
            raise InvalidStateTransition(
                f"Cannot transition from {self._phase.value} to {new_phase.value}"
            )
        self._phase = new_phase

    def can_transition_to(self, new_phase: Phase) -> bool:
        """
        Check if transition to target phase is valid

        Args:
            new_phase: Target phase

        Returns:
            True if transition is valid
        """
        return new_phase in VALID_TRANSITIONS.get(self._phase, set())

    def reset(self) -> None:
        """Reset to initial IDLE phase"""
        self._phase = Phase.IDLE

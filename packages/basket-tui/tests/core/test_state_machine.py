"""
Tests for AppStateMachine

Following TDD methodology: write tests first, then implement.
"""

import pytest
from basket_tui.core.state_machine import (
    AppStateMachine,
    Phase,
    InvalidStateTransition,
)


class TestAppStateMachine:
    """Test suite for AppStateMachine"""

    def test_initial_state_is_idle(self):
        """State machine should start in IDLE phase"""
        sm = AppStateMachine()
        assert sm.current_phase == Phase.IDLE

    def test_valid_transition_idle_to_waiting(self):
        """Should allow transition from IDLE to WAITING_MODEL"""
        sm = AppStateMachine()
        sm.transition_to(Phase.WAITING_MODEL)
        assert sm.current_phase == Phase.WAITING_MODEL

    def test_invalid_transition_idle_to_streaming_raises_error(self):
        """Should raise InvalidStateTransition for illegal transition"""
        sm = AppStateMachine()
        with pytest.raises(InvalidStateTransition) as exc_info:
            sm.transition_to(Phase.STREAMING)
        assert "idle" in str(exc_info.value).lower()
        assert "streaming" in str(exc_info.value).lower()

    def test_can_transition_to_returns_true_for_valid(self):
        """Should return True for valid transitions"""
        sm = AppStateMachine()
        assert sm.can_transition_to(Phase.WAITING_MODEL) is True

    def test_can_transition_to_returns_false_for_invalid(self):
        """Should return False for invalid transitions"""
        sm = AppStateMachine()
        assert sm.can_transition_to(Phase.STREAMING) is False

    def test_reset_to_idle(self):
        """Should reset to IDLE phase"""
        sm = AppStateMachine()
        sm.transition_to(Phase.WAITING_MODEL)
        sm.reset()
        assert sm.current_phase == Phase.IDLE

    def test_valid_transition_waiting_to_thinking(self):
        """Should allow WAITING_MODEL -> THINKING"""
        sm = AppStateMachine()
        sm.transition_to(Phase.WAITING_MODEL)
        sm.transition_to(Phase.THINKING)
        assert sm.current_phase == Phase.THINKING

    def test_valid_transition_thinking_to_streaming(self):
        """Should allow THINKING -> STREAMING"""
        sm = AppStateMachine()
        sm.transition_to(Phase.WAITING_MODEL)
        sm.transition_to(Phase.THINKING)
        sm.transition_to(Phase.STREAMING)
        assert sm.current_phase == Phase.STREAMING

    def test_valid_transition_streaming_to_tool_running(self):
        """Should allow STREAMING -> TOOL_RUNNING"""
        sm = AppStateMachine()
        sm.transition_to(Phase.WAITING_MODEL)
        sm.transition_to(Phase.STREAMING)
        sm.transition_to(Phase.TOOL_RUNNING)
        assert sm.current_phase == Phase.TOOL_RUNNING

    def test_valid_transition_tool_running_to_idle(self):
        """Should allow TOOL_RUNNING -> IDLE"""
        sm = AppStateMachine()
        sm.transition_to(Phase.WAITING_MODEL)
        sm.transition_to(Phase.TOOL_RUNNING)
        sm.transition_to(Phase.IDLE)
        assert sm.current_phase == Phase.IDLE

    def test_valid_transition_to_error_from_any_phase(self):
        """Should allow transition to ERROR from most phases"""
        # From WAITING_MODEL
        sm = AppStateMachine()
        sm.transition_to(Phase.WAITING_MODEL)
        sm.transition_to(Phase.ERROR)
        assert sm.current_phase == Phase.ERROR

        # From THINKING
        sm = AppStateMachine()
        sm.transition_to(Phase.WAITING_MODEL)
        sm.transition_to(Phase.THINKING)
        sm.transition_to(Phase.ERROR)
        assert sm.current_phase == Phase.ERROR

    def test_error_can_only_transition_to_idle(self):
        """ERROR phase should only allow transition to IDLE"""
        sm = AppStateMachine()
        sm.transition_to(Phase.WAITING_MODEL)
        sm.transition_to(Phase.ERROR)

        # Can go to IDLE
        sm.transition_to(Phase.IDLE)
        assert sm.current_phase == Phase.IDLE

    def test_invalid_transition_error_to_streaming(self):
        """Should not allow ERROR -> STREAMING"""
        sm = AppStateMachine()
        sm.transition_to(Phase.WAITING_MODEL)
        sm.transition_to(Phase.ERROR)

        with pytest.raises(InvalidStateTransition):
            sm.transition_to(Phase.STREAMING)

    def test_phase_enum_values(self):
        """Phase enum should have correct values"""
        assert Phase.IDLE.value == "idle"
        assert Phase.WAITING_MODEL.value == "waiting_model"
        assert Phase.THINKING.value == "thinking"
        assert Phase.STREAMING.value == "streaming"
        assert Phase.TOOL_RUNNING.value == "tool_running"
        assert Phase.ERROR.value == "error"

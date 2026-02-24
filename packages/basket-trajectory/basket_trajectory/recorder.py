"""
Trajectory recorder: consumes agent events and final state to build TaskTrajectory.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .schema import TaskTrajectory, ToolCallRecord, TurnRecord

if TYPE_CHECKING:
    from basket_agent.types import AgentState

logger = logging.getLogger(__name__)

# Maximum length for result_summary in tool calls
RESULT_SUMMARY_MAX_LEN = 2000


def _truncate_result(result: Any) -> str:
    """Convert result to string and truncate for storage."""
    try:
        if hasattr(result, "model_dump"):
            s = json.dumps(result.model_dump())
        elif isinstance(result, str):
            s = result
        else:
            s = json.dumps(result)
    except Exception:
        s = str(result)
    if len(s) > RESULT_SUMMARY_MAX_LEN:
        return s[:RESULT_SUMMARY_MAX_LEN] + "..."
    return s


class TrajectoryRecorder:
    """
    Records agent run events and builds a TaskTrajectory on finalize.

    Use: start_task(user_input), subscribe on_event to agent events,
    then finalize(state) and get_trajectory() / write via storage.
    """

    def __init__(self, task_id: Optional[str] = None):
        self.task_id = task_id or f"task_{int(time.time() * 1000)}"
        self._started_at: float = 0.0
        self._ended_at: float = 0.0
        self._user_input: str = ""
        self._success = False
        self._error_message: Optional[str] = None
        self._final_message_text: Optional[str] = None
        self._total_turns = 0
        # tool_calls keyed by turn_number (1-based)
        self._turn_tool_calls: Dict[int, List[ToolCallRecord]] = {}
        self._current_turn_with_tool_calls: Optional[int] = None
        self._last_turn_with_tool_calls: Optional[int] = None  # fallback when _current is None
        self._trajectory: Optional[TaskTrajectory] = None

    def start_task(self, user_input: str) -> None:
        """Mark start of a task and set user input."""
        self._started_at = time.time()
        self._ended_at = 0.0
        self._user_input = user_input
        self._success = False
        self._error_message = None
        self._final_message_text = None
        self._total_turns = 0
        self._turn_tool_calls.clear()
        self._current_turn_with_tool_calls = None
        self._last_turn_with_tool_calls = None
        self._trajectory = None

    def on_event(self, event: Dict[str, Any]) -> None:
        """Process one agent event (sync)."""
        event_type = event.get("type")
        if event_type == "agent_turn_start":
            pass  # turn number available in event for context
        elif event_type == "agent_turn_end":
            if event.get("has_tool_calls"):
                t = event.get("turn_number")
                if t is not None:
                    self._current_turn_with_tool_calls = t
                    self._last_turn_with_tool_calls = t
                    self._turn_tool_calls.setdefault(t, [])
        elif event_type == "agent_tool_call_start":
            pass
        elif event_type == "agent_tool_call_end":
            turn_key = self._current_turn_with_tool_calls or self._last_turn_with_tool_calls
            if turn_key is None:
                return
            record = ToolCallRecord(
                tool_name=event.get("tool_name", ""),
                tool_call_id=event.get("tool_call_id", ""),
                arguments=event.get("arguments") or {},
                result_summary=_truncate_result(event.get("result")) if event.get("result") is not None else None,
                error=event.get("error"),
            )
            self._turn_tool_calls.setdefault(turn_key, []).append(record)
        elif event_type == "agent_complete":
            self._success = True
            self._total_turns = event.get("total_turns", 0)
            final_msg = event.get("final_message")
            if final_msg and isinstance(final_msg, dict):
                content = final_msg.get("content") or []
                texts = [
                    b.get("text", "")
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                ]
                self._final_message_text = "\n".join(texts) if texts else None
            elif hasattr(final_msg, "content"):
                texts = [
                    getattr(b, "text", "")
                    for b in (final_msg.content or [])
                    if getattr(b, "type", None) == "text"
                ]
                self._final_message_text = "\n".join(texts) if texts else None
        elif event_type == "agent_error":
            self._success = False
            self._error_message = event.get("error", "")

    def finalize(self, state: Optional["AgentState"] = None) -> None:
        """
        Build TaskTrajectory from buffered events and optional state.

        If state is None (e.g. run failed before returning), only
        event-derived fields are set; turns may be empty.
        """
        self._ended_at = time.time()
        model_provider = ""
        model_id = ""
        system_prompt: Optional[str] = None
        tool_names: List[str] = []
        turns: List[TurnRecord] = []
        total_usage: Dict[str, Any] = {
            "input": 0,
            "output": 0,
            "total_tokens": 0,
            "cost_total": 0.0,
        }

        if state is not None:
            try:
                model_provider = getattr(state.model, "provider", "") or ""
                model_id = getattr(state.model, "id", "") or ""
            except Exception:
                pass
            try:
                system_prompt = state.context.system_prompt if state.context else None
                if state.context and state.context.tools:
                    tool_names = [t.name for t in state.context.tools]
            except Exception:
                pass
            # Build turns from context.messages: each AssistantMessage = one turn
            try:
                messages = state.context.messages or []
                turn_index = 0
                for i, msg in enumerate(messages):
                    if getattr(msg, "role", None) == "assistant":
                        turn_index += 1
                        asst_dict: Dict[str, Any] = {}
                        if hasattr(msg, "model_dump"):
                            asst_dict = msg.model_dump(mode="json")
                        elif isinstance(msg, dict):
                            asst_dict = msg
                        tool_calls = self._turn_tool_calls.get(turn_index, [])
                        # Input for this turn = all messages before this assistant
                        input_messages: List[Dict[str, Any]] = []
                        for m in messages[:i]:
                            if hasattr(m, "model_dump"):
                                input_messages.append(m.model_dump(mode="json"))
                            elif isinstance(m, dict):
                                input_messages.append(m)
                        turns.append(
                            TurnRecord(
                                turn_index=turn_index,
                                input_messages=input_messages,
                                assistant_message=asst_dict,
                                tool_calls=tool_calls,
                            )
                        )
                        # Aggregate usage from this assistant message
                        if hasattr(msg, "usage") and msg.usage is not None:
                            u = msg.usage
                            total_usage["input"] = total_usage.get("input", 0) + getattr(u, "input", 0)
                            total_usage["output"] = total_usage.get("output", 0) + getattr(u, "output", 0)
                            total_usage["total_tokens"] = total_usage.get("total_tokens", 0) + getattr(u, "total_tokens", 0)
                            if getattr(u, "cost", None) is not None:
                                total_usage["cost_total"] = total_usage.get("cost_total", 0) + getattr(u.cost, "total", 0)
            except Exception as e:
                logger.debug("Trajectory finalize from state: %s", e)

        if not self._total_turns and turns:
            self._total_turns = len(turns)

        self._trajectory = TaskTrajectory(
            task_id=self.task_id,
            started_at=self._started_at,
            ended_at=self._ended_at,
            model_provider=model_provider,
            model_id=model_id,
            success=self._success,
            error_message=self._error_message,
            user_input=self._user_input,
            system_prompt=system_prompt,
            tool_names=tool_names,
            turns=turns,
            final_message_text=self._final_message_text,
            total_turns=self._total_turns,
            total_usage=total_usage,
        )

    def get_trajectory(self) -> TaskTrajectory:
        """Return the built TaskTrajectory (call after finalize)."""
        if self._trajectory is None:
            self.finalize(None)
        assert self._trajectory is not None
        return self._trajectory

"""Trajectory recording helpers for agent runs."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ._protocol import AssistantAgentProtocol

logger = logging.getLogger(__name__)


def get_trajectory_dir(agent: AssistantAgentProtocol) -> Optional[str]:
    """Trajectory directory from env or settings; None if disabled."""
    out = (
        os.environ.get("BASKET_TRAJECTORY_DIR")
        or (agent.settings.trajectory_dir or "").strip()
    )
    return out or None


def on_trajectory_event(agent: AssistantAgentProtocol, event: Any) -> None:
    """Forward agent event to current trajectory recorder (if any)."""
    recorder = agent._trajectory_recorder
    if recorder is not None:
        # Trajectory recorder expects dict format
        data = event.model_dump() if hasattr(event, "model_dump") else event
        recorder.on_event(data)


def ensure_trajectory_handlers(agent: AssistantAgentProtocol) -> None:
    """Register trajectory event handlers once (no-op when trajectory disabled)."""
    if agent._trajectory_handlers_registered:
        return
    for event_type in (
        "agent_turn_start",
        "agent_turn_end",
        "agent_tool_call_start",
        "agent_tool_call_end",
        "agent_complete",
        "agent_error",
    ):
        agent.agent.on(event_type, lambda e, ag=agent: on_trajectory_event(ag, e))
    agent._trajectory_handlers_registered = True


async def run_with_trajectory_if_enabled(
    agent: AssistantAgentProtocol,
    stream_llm_events: bool = True,
    invoked_skill_id: Optional[str] = None,
):
    """Run agent; if trajectory_dir is set, record trajectory and write to disk."""
    from . import prompts
    from ._assistant_events import emit_assistant_event

    old_system = agent.context.system_prompt
    agent.context.system_prompt = prompts.get_system_prompt_for_run(
        agent, invoked_skill_id
    )
    if invoked_skill_id:
        logger.info("Invoked skill for this turn: skill_id=%s", invoked_skill_id)
    try:
        await emit_assistant_event(
            agent,
            "before_run",
            {"session_id": agent._session_id, "context": agent.context},
        )
        trajectory_dir = get_trajectory_dir(agent)
        if not trajectory_dir:
            return await agent.agent.run(stream_llm_events=stream_llm_events)

        from basket_trajectory import TrajectoryRecorder, write_trajectory

        ensure_trajectory_handlers(agent)
        recorder = TrajectoryRecorder()
        agent._trajectory_recorder = recorder

        user_input = ""
        for msg in reversed(agent.context.messages):
            if getattr(msg, "role", None) == "user":
                content = getattr(msg, "content", "")
                user_input = content if isinstance(content, str) else str(content)
                break
        recorder.start_task(user_input)

        state = None
        try:
            state = await agent.agent.run(stream_llm_events=stream_llm_events)
        except Exception:
            raise
        finally:
            agent._trajectory_recorder = None
            try:
                recorder.finalize(state)
                path = Path(trajectory_dir).expanduser()
                path.mkdir(parents=True, exist_ok=True)
                write_trajectory(
                    recorder.get_trajectory(), path / f"task_{recorder.task_id}.json"
                )
            except Exception as e:
                logger.warning("Failed to write trajectory: %s", e)

        return state
    finally:
        agent.context.system_prompt = old_system

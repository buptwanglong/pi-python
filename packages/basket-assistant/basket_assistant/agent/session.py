"""Session switching, history/todos/pending_asks load and persist, resume pending ask."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from basket_ai.types import TextContent

if TYPE_CHECKING:
    from ._protocol import AssistantAgentProtocol

logger = logging.getLogger(__name__)


async def set_session_id(
    agent: AssistantAgentProtocol, session_id: Optional[str], load_history: bool = True
) -> None:
    """
    Set the current session id and load its todo list and pending_asks from disk.
    When session_id is non-empty and load_history is True, load messages into context.messages.
    When session_id is None, clear _session_id, _current_todos, _pending_asks, and context.messages.
    """
    agent._session_id = session_id
    if session_id:
        agent._current_todos = await agent.session_manager.load_todos(session_id)
        agent._pending_asks = await agent.session_manager.load_pending_asks(session_id)
        if load_history:
            agent.context.messages = await agent.session_manager.load_messages(
                session_id
            )
            logger.info(
                "Session context initialized: session_id=%s, loaded_messages=%d, todos=%d, pending_asks=%d",
                session_id,
                len(agent.context.messages),
                len(agent._current_todos),
                len(agent._pending_asks),
            )
        else:
            logger.info(
                "Session set (no history load): session_id=%s, context.messages=%d",
                session_id,
                len(agent.context.messages),
            )
        hook_runner = agent.hook_runner
        if hook_runner is not None:
            await hook_runner.run(
                "session.created",
                {
                    "session_id": session_id,
                    "directory": str(Path.cwd()),
                    "workspace_roots": [str(Path.cwd())],
                },
                cwd=Path.cwd(),
            )
    else:
        agent._current_todos = []
        agent._pending_asks = []
        agent.context.messages = []
        logger.info("Session cleared: context.messages=0")


async def try_resume_pending_ask(
    agent: AssistantAgentProtocol,
    user_content: str,
    tool_call_id: Optional[str] = None,
    *,
    stream_llm_events: bool = True,
    invoked_skill_id: Optional[str] = None,
) -> bool:
    """
    If there is a pending_ask, treat user_content as the answer: replace the
    corresponding ToolResultMessage content, remove that pending, and run agent.
    Returns True if a pending was consumed and run started; False otherwise.
    """
    if not agent._pending_asks:
        return False
    if tool_call_id:
        entry = next(
            (p for p in agent._pending_asks if p.get("tool_call_id") == tool_call_id),
            None,
        )
    else:
        entry = agent._pending_asks[0]
    if not entry:
        return False
    target_id = entry["tool_call_id"]
    for msg in agent.context.messages:
        if getattr(msg, "role", None) == "toolResult" and getattr(
            msg, "tool_call_id", None
        ) == target_id:
            msg.content = [TextContent(type="text", text=user_content)]
            break
    else:
        return False
    agent._pending_asks = [
        p for p in agent._pending_asks if p.get("tool_call_id") != target_id
    ]
    if agent._session_id:
        await agent.session_manager.save_pending_asks(
            agent._session_id, agent._pending_asks
        )
    await agent._run_with_trajectory_if_enabled(
        stream_llm_events=stream_llm_events,
        invoked_skill_id=invoked_skill_id,
    )
    return True

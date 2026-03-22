"""CLI/TUI display event handlers for agent tool calls and text streaming."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

from basket_ai.types import EventTextDelta
from basket_agent.types import (
    AgentEventToolCallStart,
    AgentEventToolCallEnd,
)

if TYPE_CHECKING:
    from ._protocol import AssistantAgentProtocol

logger = logging.getLogger(__name__)

# Tool name -> list of argument keys to show in INFO log (first key wins for short summary)
_TOOL_ARG_SUMMARY_KEYS: Dict[str, List[str]] = {
    "bash": ["command"],
    "read": ["file_path"],
    "write": ["file_path"],
    "edit": ["file_path", "old_string", "new_string"],
    "grep": ["pattern", "path"],
    "web_search": ["query"],
    "web_fetch": ["url"],
    "todo_write": [],  # summary is "N items"
    "ask_user_question": ["question"],
    "task": ["subagent_type", "prompt"],
    "skill": ["skill_id", "message"],
}


def _tool_call_args_summary(tool_name: str, args: Dict[str, Any], max_len: int = 200) -> str:
    """Build a short one-line summary of tool arguments for logging."""
    if not args:
        return ""
    keys = _TOOL_ARG_SUMMARY_KEYS.get(tool_name)
    if keys:
        parts = []
        for k in keys:
            if k in args:
                v = args[k]
                if isinstance(v, str) and len(v) > 80:
                    v = v[:77] + "..."
                parts.append(f"{k}={v!r}")
        if parts:
            s = " ".join(parts)
            return s[:max_len] + "..." if len(s) > max_len else s
    # Fallback: first two keys
    first = list(args.items())[:2]
    s = " ".join(f"{k}={v!r}" for k, v in first)
    return (s[:max_len] + "...") if len(s) > max_len else s


def setup_event_handlers(agent: AssistantAgentProtocol) -> None:
    """Setup event handlers for agent events."""

    def on_text_delta(event: EventTextDelta):
        delta = event.delta
        if delta:
            print(delta, end="", flush=True)

    async def on_tool_call_start(event: AgentEventToolCallStart):
        tool_name = event.tool_name
        args = event.arguments or {}
        summary = _tool_call_args_summary(tool_name, args)
        if summary:
            logger.info("Tool call start: %s %s", tool_name, summary)
        else:
            logger.info("Tool call start: %s", tool_name)
        if args:
            args_str = str(args)
            logger.debug(
                "Tool call args: %s",
                args_str[:500] + "..." if len(args_str) > 500 else args_str,
            )
        if agent.settings.agent.verbose:
            print(f"\n[Tool: {event.tool_name}]", flush=True)
            logger.info("[Tool: %s]", tool_name)
        if tool_name == "ask_user_question":
            tool_call_id = event.tool_call_id
            if tool_call_id:
                question = (args or {}).get("question", "")
                options = (
                    (args or {}).get("options")
                    if isinstance((args or {}).get("options"), list)
                    else []
                )
                entry = {
                    "tool_call_id": tool_call_id,
                    "question": question,
                    "options": options or [],
                }
                agent._pending_asks.append(entry)
                if agent._session_id:
                    await agent.session_manager.save_pending_asks(
                        agent._session_id, agent._pending_asks
                    )
                q = entry.get("question", "") or "Question"
                if len(q) > 60:
                    q = q[:57] + "..."
                n = len(agent._pending_asks)
                msg = (
                    f"\n[Ask: {q}] Reply in your next message"
                    + (f" ({n} pending)" if n > 1 else "")
                )
                print(msg, flush=True)
                logger.info("[Ask: %s] Reply in your next message%s", q, f" ({n} pending)" if n > 1 else "")

    async def on_tool_call_end(event: AgentEventToolCallEnd):
        tool_name = event.tool_name
        err = event.error
        logger.info("Tool call end: %s error=%s", tool_name, bool(err))
        if not err and event.result is not None:
            result_str = str(event.result)
            logger.debug(
                "Tool call result: %s",
                result_str[:500] + "..." if len(result_str) > 500 else result_str,
            )
        if err:
            print(f"[Error: {event.error}]", flush=True)
            logger.warning("[Error: %s]", event.error)
            if tool_name == "ask_user_question":
                tid = event.tool_call_id
                if tid:
                    agent._pending_asks = [
                        p for p in agent._pending_asks if p.get("tool_call_id") != tid
                    ]
                    if agent._session_id:
                        await agent.session_manager.save_pending_asks(
                            agent._session_id, agent._pending_asks
                        )
        elif tool_name == "todo_write" and agent._current_todos:
            in_progress = [
                t for t in agent._current_todos if t.get("status") == "in_progress"
            ]
            if in_progress and agent.settings.agent.verbose:
                line = (
                    f"\n[Todo: {len(agent._current_todos)} items; in progress: {(in_progress[0].get('content') or '')[:50]!r}]"
                )
                print(line, flush=True)
                logger.debug(
                    "[Todo: %d items; in progress: %s]",
                    len(agent._current_todos),
                    (in_progress[0].get("content") or "")[:50],
                )
            elif agent.settings.agent.verbose:
                print(f"\n[Todo: {len(agent._current_todos)} items]", flush=True)
                logger.debug("[Todo: %d items]", len(agent._current_todos))

    agent.agent.on("text_delta", on_text_delta)
    agent.agent.on("agent_tool_call_start", on_tool_call_start)
    agent.agent.on("agent_tool_call_end", on_tool_call_end)

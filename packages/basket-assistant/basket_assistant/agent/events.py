"""Agent event handlers, before_run/turn_done emission, trajectory recording."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def setup_event_handlers(agent: Any) -> None:
    """Setup event handlers for agent events."""

    def on_text_delta(event):
        delta = event.get("delta", "")
        if delta:
            print(delta, end="", flush=True)

    async def on_tool_call_start(event):
        tool_name = event.get("tool_name", "unknown")
        args = event.get("arguments", {}) or {}
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
            print(f"\n[Tool: {event['tool_name']}]", flush=True)
            logger.info("[Tool: %s]", tool_name)
        if tool_name == "ask_user_question":
            tool_call_id = event.get("tool_call_id") or ""
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

    async def on_tool_call_end(event):
        tool_name = event.get("tool_name", "unknown")
        err = event.get("error")
        logger.info("Tool call end: %s error=%s", tool_name, bool(err))
        if not err and event.get("result") is not None:
            result_str = str(event.get("result", ""))
            logger.debug(
                "Tool call result: %s",
                result_str[:500] + "..." if len(result_str) > 500 else result_str,
            )
        if err:
            print(f"[Error: {event['error']}]", flush=True)
            logger.warning("[Error: %s]", event.get("error", ""))
            if tool_name == "ask_user_question":
                tid = event.get("tool_call_id")
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


def setup_logging_handlers(agent: Any) -> None:
    """
    Register handlers that only write INFO logs for LLM turns and tool calls.
    Shared by CLI and TUI; same events drive both logging and display responses.
    """
    basket_agent = agent.agent if hasattr(agent, "agent") else agent

    def on_turn_start(event: dict) -> None:
        logger.info(
            "LLM turn started, turn_number=%s",
            event.get("turn_number"),
        )

    def on_turn_end(event: dict) -> None:
        logger.info(
            "LLM turn ended, turn_number=%s, has_tool_calls=%s",
            event.get("turn_number"),
            event.get("has_tool_calls", False),
        )

    def on_tool_call_start_log(event: dict) -> None:
        tool_name = event.get("tool_name", "unknown")
        args = event.get("arguments", {}) or {}
        summary = _tool_call_args_summary(tool_name, args)
        if summary:
            logger.info("Tool call start: %s %s", tool_name, summary)
        else:
            logger.info("Tool call start: %s", tool_name)

    def on_tool_call_end_log(event: dict) -> None:
        tool_name = event.get("tool_name", "unknown")
        err = event.get("error")
        logger.info("Tool call end: %s error=%s", tool_name, bool(err))

    basket_agent.on("agent_turn_start", on_turn_start)
    basket_agent.on("agent_turn_end", on_turn_end)
    basket_agent.on("agent_tool_call_start", on_tool_call_start_log)
    basket_agent.on("agent_tool_call_end", on_tool_call_end_log)


async def emit_assistant_event(agent: Any, event_name: str, payload: dict) -> None:
    """Emit an assistant-level event (e.g. before_run, turn_done) to registered handlers."""
    handlers = agent._assistant_event_handlers.get(event_name, [])
    if event_name in ("before_run", "turn_done"):
        logger.info(
            "memory: emit %s handlers=%d payload_keys=%s",
            event_name,
            len(handlers),
            list(payload.keys()) if isinstance(payload, dict) else "?",
        )
    for i, handler in enumerate(handlers):
        try:
            if event_name in ("before_run", "turn_done"):
                logger.info(
                    "memory: invoking %s handler %d/%d (%s)",
                    event_name,
                    i + 1,
                    len(handlers),
                    getattr(handler, "__qualname__", repr(handler)[:60]),
                )
            if asyncio.iscoroutinefunction(handler):
                await handler(payload)
            else:
                handler(payload)
            if event_name in ("before_run", "turn_done"):
                logger.info("memory: %s handler %d/%d done", event_name, i + 1, len(handlers))
        except Exception as e:
            logger.warning(
                "Assistant event handler %s failed: %s", event_name, e, exc_info=True
            )


def messages_for_hook_payload(agent: Any, messages: List) -> List[Dict[str, str]]:
    """Convert message objects to JSON-serializable [{"role", "content"}, ...] for hooks."""
    out = []
    for msg in messages:
        role = getattr(msg, "role", None)
        if role not in ("user", "assistant", "toolResult"):
            continue
        content = getattr(msg, "content", None)
        if isinstance(content, str):
            out.append({"role": role, "content": content})
        elif isinstance(content, list):
            parts = []
            for block in content:
                if hasattr(block, "text") and block.text:
                    parts.append(block.text)
                elif isinstance(block, dict) and block.get("text"):
                    parts.append(block["text"])
            out.append({"role": role, "content": " ".join(parts)})
        else:
            out.append(
                {"role": role, "content": str(content) if content is not None else ""}
            )
    return out


def get_trajectory_dir(agent: Any) -> Optional[str]:
    """Trajectory directory from env or settings; None if disabled."""
    out = (
        os.environ.get("BASKET_TRAJECTORY_DIR")
        or (agent.settings.trajectory_dir or "").strip()
    )
    return out or None


def on_trajectory_event(agent: Any, event: dict) -> None:
    """Forward agent event to current trajectory recorder (if any)."""
    recorder = getattr(agent, "_trajectory_recorder", None)
    if recorder is not None:
        recorder.on_event(event)


def ensure_trajectory_handlers(agent: Any) -> None:
    """Register trajectory event handlers once (no-op when trajectory disabled)."""
    if getattr(agent, "_trajectory_handlers_registered", False):
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
    agent: Any,
    stream_llm_events: bool = True,
    invoked_skill_id: Optional[str] = None,
):
    """Run agent; if trajectory_dir is set, record trajectory and write to disk."""
    from . import prompts

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

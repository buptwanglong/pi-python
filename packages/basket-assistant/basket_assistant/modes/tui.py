"""
TUI Mode for Pi Coding Agent

Runs the coding agent with an interactive TUI interface.
"""

import asyncio
import copy
import logging
import time
from typing import Optional

from basket_agent import Agent
from basket_tui import PiCodingAgentApp
from basket_tui.app import ProcessPendingInputs

logger = logging.getLogger(__name__)


def _format_tool_result(tool_name: str, result: any) -> str:
    """
    Format tool result for display in TUI (Claude Code minimal style).

    Args:
        tool_name: Name of the tool that was executed
        result: Result object from the tool

    Returns:
        Formatted string representation of the result
    """
    if result is None:
        return "Tool executed successfully (no output)"

    # Handle dict results (Pydantic models are converted to dicts)
    if isinstance(result, dict):
        if tool_name == "bash":
            stdout = result.get("stdout", "").strip()
            stderr = result.get("stderr", "").strip()
            exit_code = result.get("exit_code", 0)
            timeout = result.get("timeout", False)

            parts = []
            if timeout:
                parts.append("Command timed out")

            # Simple status line
            if exit_code == 0:
                parts.append(f"exit {exit_code}")
            else:
                parts.append(f"exit {exit_code} (error)")

            # Output with reasonable truncation
            if stdout:
                if len(stdout) > 1000:
                    parts.append(f"\n{stdout[:1000]}\n... ({len(stdout)} chars total, truncated)")
                else:
                    parts.append(f"\n{stdout}")

            if stderr:
                parts.append(f"\nErrors:\n{stderr[:500]}")

            return "\n".join(parts)

        elif tool_name == "read":
            lines = result.get("lines", 0)
            file_path = result.get("file_path", "")
            content = result.get("content", "")

            # Show first few lines as preview
            content_lines = content.split("\n")
            preview_lines = content_lines[:5]
            preview = "\n".join(preview_lines)

            parts = [f"Read {lines} lines from {file_path}"]
            if len(content_lines) > 5:
                parts.append(f"\nFirst 5 lines:\n{preview}\n... ({lines} total lines)")
            else:
                parts.append(f"\n{preview}")

            return "\n".join(parts)

        elif tool_name == "write":
            file_path = result.get("file_path", "")
            success = result.get("success", False)

            if success:
                return f"Wrote file: {file_path}"
            else:
                error = result.get("error", "Unknown error")
                return f"Write failed: {error}"

        elif tool_name == "edit":
            success = result.get("success", False)
            replacements = result.get("replacements_made", 0)
            file_path = result.get("file_path", "")

            if success:
                return f"Made {replacements} replacement(s) in {file_path}"
            else:
                error = result.get("error", "Unknown error")
                return f"Edit failed: {error}"

        elif tool_name == "grep":
            total_matches = result.get("total_matches", 0)
            truncated = result.get("truncated", False)
            matches = result.get("matches", [])

            parts = [f"Found {total_matches} match(es)"]

            if matches:
                sample_count = min(5, len(matches))
                parts.append(f"\nShowing {sample_count} of {total_matches}:")
                for match in matches[:sample_count]:
                    file_path = match.get("file_path", "")
                    line_number = match.get("line_number", 0)
                    parts.append(f"  {file_path}:{line_number}")

                if total_matches > sample_count:
                    parts.append(f"... and {total_matches - sample_count} more")

            return "\n".join(parts)

    # Fallback for other result types
    result_str = str(result)
    if len(result_str) > 500:
        return result_str[:500] + f"\n... ({len(result_str)} chars total, truncated)"
    return result_str


def _connect_agent_handlers(app, agent: Agent, current_response: dict, coding_agent=None) -> None:
    """
    Connect agent event handlers to app display methods (same-thread direct calls).

    Used by run_tui_mode. Event handlers call app methods directly because
    agent runs in the same asyncio loop as the TUI; call_from_thread must not
    be used from the app thread. coding_agent is used to refresh the todo panel on todo_write.
    """
    def on_text_delta(event):
        delta = event.get("delta", "")
        current_response["text"] += delta
        app.append_text(delta)

    def on_thinking_delta(event):
        delta = event.get("delta", "")
        current_response["thinking"] += delta
        if not current_response["in_thinking"]:
            current_response["in_thinking"] = True
            app.append_message("system", "Thinking...")  # No emoji
        app.append_thinking(delta)

    def on_tool_call_start(event):
        tool_name = event.get("tool_name", "unknown")
        arguments = event.get("arguments", {})
        app.show_tool_call(tool_name, arguments)

    def on_tool_call_end(event):
        error = event.get("error")
        tool_name = event.get("tool_name", "unknown")
        if error:
            app.show_tool_result(str(error), success=False)
        else:
            result = event.get("result")
            formatted_result = _format_tool_result(tool_name, result)
            app.show_tool_result(formatted_result, success=True)
        if tool_name == "todo_write" and coding_agent is not None:
            todos = getattr(coding_agent, "_current_todos", [])
            app.update_todo_panel(todos)

    def on_agent_complete(event):
        # Run finished: finalize current assistant block so the next user message gets a new block
        app.finalize_assistant_block()
        current_response["text"] = ""
        current_response["thinking"] = ""
        current_response["in_thinking"] = False
        # Process any user inputs queued while agent was streaming (correct display order)
        app.post_message(ProcessPendingInputs())

    def on_agent_error(event):
        error = event.get("error", "Unknown error")
        app.append_message("system", f"Error: {error}")

    agent.on("text_delta", on_text_delta)
    agent.on("thinking_delta", on_thinking_delta)
    agent.on("agent_tool_call_start", on_tool_call_start)
    agent.on("agent_tool_call_end", on_tool_call_end)
    agent.on("agent_complete", on_agent_complete)
    agent.on("agent_error", on_agent_error)


async def run_tui_mode(coding_agent) -> None:
    """
    Run the coding agent in TUI mode.

    Args:
        coding_agent: The CodingAgent instance (provides .agent, .context, _run_with_trajectory_if_enabled)

    This function:
    1. Creates a TUI app instance
    2. Connects agent events to TUI display methods
    3. Sets up input handling to forward messages to the agent
    4. Runs the TUI application
    """
    agent = coding_agent.agent
    app = PiCodingAgentApp(agent=agent, coding_agent=coding_agent)
    current_response = {"text": "", "thinking": "", "in_thinking": False}
    _connect_agent_handlers(app, agent, current_response, coding_agent=coding_agent)

    async def handle_user_input(user_input: str):
        """
        Handle user input by forwarding to the agent.
        If there are pending ask_user_question(s), treat input as answer (FIFO) and resume.

        Args:
            user_input: The user's message
        """
        from basket_ai.types import UserMessage

        # Pending ask_user_question: treat this input as the answer (FIFO)
        pending = getattr(coding_agent, "_pending_asks", None) or []
        if len(pending) > 0:
            await app.ensure_assistant_block()
            task = asyncio.create_task(
                coding_agent.try_resume_pending_ask(user_input, stream_llm_events=True)
            )
            app.set_agent_task(task)
            try:
                resumed = await task
                if resumed:
                    return
            except asyncio.CancelledError:
                logger.debug("Resume task cancelled")
                app.append_message("system", "Stopped by user.")
                return
            except Exception as e:
                logger.exception("Resume pending ask failed")
                coding_agent.context.messages = coding_agent.context.messages  # no-op, keep context
                app.append_message("system", f"Error: {e}")
                return
            finally:
                app.set_agent_task(None)
            # If not resumed, fall through to normal append + run

        # Add user message to context
        coding_agent.context.messages.append(
            UserMessage(
                role="user",
                content=user_input,
                timestamp=int(time.time() * 1000),
            )
        )

        # Snapshot context for error recovery (restore on exception)
        messages_snapshot = copy.deepcopy(coding_agent.context.messages)

        # Create assistant block so streaming updates go to one block (must be before run)
        await app.ensure_assistant_block()

        logger.debug("Sending user message, starting agent run")
        # Run agent in a cancellable task (with optional trajectory recording)
        task = asyncio.create_task(coding_agent._run_with_trajectory_if_enabled(stream_llm_events=True))
        app.set_agent_task(task)
        try:
            await task
        except asyncio.CancelledError:
            logger.debug("Agent task cancelled by user")
            app.append_message("system", "Stopped by user.")
        except Exception as e:
            logger.exception("Agent run failed in TUI")
            coding_agent.context.messages = messages_snapshot
            app.append_message("system", f"Error: {e}")
            app.append_message("system", "Context restored to previous state.")
        finally:
            app.set_agent_task(None)

    # Set input handler
    app.set_input_handler(handle_user_input)

    # Run the app
    await app.run_async()


__all__ = ["run_tui_mode"]

"""Interactive REPL, run_once, todo block format, help/settings print."""

import copy
import logging
import time
from pathlib import Path
from typing import Optional

from basket_ai.types import UserMessage

logger = logging.getLogger(__name__)


async def run_interactive(agent) -> None:
    """
    Run the agent in interactive mode.
    Continuously prompts for user input and runs the agent.
    """
    if agent._session_id is None:
        session_id = await agent.session_manager.create_session(agent.model.id)
        await agent.set_session_id(session_id)

    print("Basket - Interactive Mode")
    print("Type 'exit' or 'quit' to quit, 'help' for help")
    print("-" * 50)

    while True:
        try:
            if agent._current_todos:
                block = format_todo_block(agent)
                if block:
                    print(block, flush=True)
            user_input = input("\n> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            if user_input.lower() == "help":
                print_help(agent)
                continue

            if user_input.lower() == "settings":
                print_settings(agent)
                continue

            if user_input.lower() == "/todos":
                agent._todo_show_full = not agent._todo_show_full
                print(
                    f"Todo list: {'full' if agent._todo_show_full else 'compact'}",
                    flush=True,
                )
                continue

            if user_input.strip().lower() in ("/plan", "/plan on", "/plan off"):
                on = user_input.strip().lower() != "/plan off"
                agent.set_plan_mode(on)
                print(f"Plan mode {'on' if on else 'off'}", flush=True)
                continue

            if user_input.strip().lower() == "/sessions":
                sessions = await agent.session_manager.list_sessions()
                if not sessions:
                    print("No sessions yet.")
                else:
                    for m in sessions:
                        print(
                            f"  {m.session_id}  created={m.created_at}  model={m.model_id}  messages={m.total_messages}"
                        )
                continue

            if user_input.strip().lower().startswith("/open "):
                session_id = user_input.split(maxsplit=1)[1].strip()
                if not session_id:
                    print("Usage: /open <session_id>")
                    continue
                sessions = await agent.session_manager.list_sessions()
                if not any(s.session_id == session_id for s in sessions):
                    print(f"Session not found: {session_id}")
                    continue
                await agent.set_session_id(session_id, load_history=True)
                n = len(agent.context.messages)
                print(
                    f"Switched to session {session_id}, loaded {n} messages.",
                    flush=True,
                )
                continue

            if agent._pending_asks:
                print()
                try:
                    resumed = await agent.try_resume_pending_ask(
                        user_input, stream_llm_events=True
                    )
                    if resumed:
                        print()
                        continue
                except Exception as resume_err:
                    logger.exception("Resume pending ask failed")
                    print(f"\n❌ Error: {resume_err}", flush=True)
                    continue

            invoked_skill_id = None
            message_content = user_input

            if user_input.strip().lower().startswith("/skill "):
                parts = user_input.split(maxsplit=2)
                if len(parts) < 2:
                    print("Usage: /skill <id> [your message]")
                    continue
                invoked_skill_id = parts[1].strip()
                message_content = parts[2].strip() if len(parts) > 2 else ""
                if not message_content:
                    message_content = "Please help according to the active skill instructions."

            elif user_input.startswith("/"):
                command_parts = user_input.split(maxsplit=1)
                command = command_parts[0]
                args = command_parts[1] if len(command_parts) > 1 else ""

                if agent.extension_loader.extension_api.execute_command(command, args):
                    continue
                else:
                    print(f"Unknown command: {command}")
                    available = agent.extension_loader.extension_api.get_commands()
                    if available:
                        print(f"Available commands: {', '.join(available)}")
                    continue

            n_before = len(agent.context.messages)

            agent.context.messages.append(
                UserMessage(
                    role="user",
                    content=message_content,
                    timestamp=int(time.time() * 1000),
                )
            )

            messages_snapshot = copy.deepcopy(agent.context.messages)

            print()
            try:
                await agent._run_with_trajectory_if_enabled(
                    stream_llm_events=True, invoked_skill_id=invoked_skill_id
                )
                if agent._session_id:
                    new_messages = agent.context.messages[n_before:]
                    if new_messages:
                        await agent.session_manager.append_messages(
                            agent._session_id, new_messages
                        )
                        await agent.emit_assistant_event(
                            "turn_done",
                            {
                                "session_id": agent._session_id,
                                "new_messages": new_messages,
                            },
                        )
                        hook_runner = getattr(
                            agent.extension_loader, "hook_runner", None
                        )
                        if hook_runner is not None:
                            await hook_runner.run(
                                "message.turn_done",
                                {
                                    "session_id": agent._session_id,
                                    "new_messages": agent._messages_for_hook_payload(
                                        new_messages
                                    ),
                                },
                                cwd=Path.cwd(),
                            )
            except Exception as agent_error:
                logger.exception("Agent run failed")
                agent.context.messages = messages_snapshot
                raise agent_error
            print()

        except KeyboardInterrupt:
            print("\n\nInterrupted. Type 'exit' to quit.")
            continue
        except Exception as e:
            logger.exception("Interactive loop error")
            print(f"\n❌ Error: {e}")
            if agent.settings.agent.verbose:
                import traceback

                traceback.print_exc()
            print("Context has been restored to previous state.")


async def run_once(
    agent, message: str, invoked_skill_id: Optional[str] = None
) -> str:
    """
    Run the agent once with a message.
    Returns agent response text.
    """
    agent.context.messages.append(
        UserMessage(
            role="user", content=message, timestamp=int(time.time() * 1000)
        )
    )

    state = await agent._run_with_trajectory_if_enabled(
        stream_llm_events=False, invoked_skill_id=invoked_skill_id
    )

    last_message = state.context.messages[-1]
    if hasattr(last_message, "content"):
        text_blocks = [
            block.text
            for block in last_message.content
            if hasattr(block, "text")
        ]
        return "\n".join(text_blocks)

    return ""


def format_todo_block(agent) -> str:
    """Format _current_todos for CLI display above prompt."""
    if not agent._current_todos:
        return ""
    total = len(agent._current_todos)
    done = sum(1 for t in agent._current_todos if t.get("status") == "completed")
    in_progress = [
        t for t in agent._current_todos if t.get("status") == "in_progress"
    ]
    if agent._todo_show_full:
        icons = {
            "completed": "✓",
            "pending": "○",
            "in_progress": "→",
            "cancelled": "✗",
        }
        lines = []
        for t in agent._current_todos:
            icon = icons.get(t.get("status", "pending"), "○")
            content = (t.get("content") or "").strip()
            lines.append(f"  {icon} {content}")
        return "\n".join(lines)
    if in_progress:
        content = (in_progress[0].get("content") or "").strip()
        return f"[Todo {done}/{total}] → {content}"
    return f"[Todo {total} items]"


def print_help(agent) -> None:
    """Print help information."""
    print(
        """
Available commands:
  help      - Show this help message
  settings  - Show current settings
  /todos    - Toggle full/compact todo list above prompt
  /plan     - Toggle plan mode (read-only analysis and planning); /plan on, /plan off
  /sessions - List all sessions (id, created_at, model, message count)
  /open <session_id> - Switch to a session and load its history
  exit/quit - Exit the program
  /skill <id> - Load full instructions for a skill for this turn (e.g. /skill refactor)

Available tools:
  read      - Read files
  write     - Write files
  edit      - Edit files with exact string replacement
  bash      - Execute shell commands
  grep      - Search for patterns in files

Example prompts:
  "Read the README.md file"
  "Create a new file hello.py with a hello world function"
  "Search for 'TODO' in all Python files"
  "Run the tests using pytest"
"""
    )


def print_settings(agent) -> None:
    """Print current settings."""
    print(
        f"""
Current settings:
  Model: {agent.settings.model.provider} / {agent.settings.model.model_id}
  Temperature: {agent.settings.model.temperature}
  Max tokens: {agent.settings.model.max_tokens}
  Max turns: {agent.settings.agent.max_turns}
  Verbose: {agent.settings.agent.verbose}
  Sessions dir: {agent.settings.sessions_dir}
"""
    )

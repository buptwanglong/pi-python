"""CLI interaction mode."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from basket_assistant.core.events.publisher import EventPublisher
from basket_assistant.adapters.cli import CLIAdapter

from .base import InteractionMode

logger = logging.getLogger(__name__)


class CLIMode(InteractionMode):
    """CLI interaction mode with REPL and todo list display.

    This mode provides a simple command-line interface with:
    - Input prompt ("> ")
    - Todo list display (if agent has todos)
    - Verbose flag support for detailed tool output

    Example:
        >>> mode = CLIMode(agent, verbose=True)
        >>> await mode.initialize()
        >>> await mode.run()
    """

    def __init__(self, agent: Any, verbose: bool = False) -> None:
        """Initialize CLI mode.

        Args:
            agent: AssistantAgent instance
            verbose: Whether to print verbose tool call information
        """
        super().__init__(agent)
        self.verbose = verbose

    def setup_publisher_adapter(self) -> Tuple[Any, Any]:
        """Set up publisher and CLI adapter.

        Returns:
            Tuple of (EventPublisher, CLIAdapter)
        """
        publisher = EventPublisher(self.agent)
        adapter = CLIAdapter(publisher, verbose=self.verbose)
        return publisher, adapter

    def _format_todo_block(self, todos: List[Dict[str, Any]]) -> str:
        """Format todo list for display.

        Args:
            todos: List of todo items (dicts with 'id', 'title', 'done')

        Returns:
            Formatted todo block string, empty if no todos
        """
        if not todos:
            return ""

        lines = []
        for todo in todos:
            checkbox = "[✓]" if todo.get("done", False) else "[ ]"
            todo_id = todo.get("id", "?")
            title = todo.get("title", "Untitled")
            lines.append(f"{checkbox} {todo_id}. {title}")

        return "\n".join(lines)

    async def run(self) -> None:
        """Run the CLI REPL loop.

        This method:
        1. Displays todo list if present
        2. Reads user input with "> " prompt
        3. Processes input and runs agent
        4. Continues until user exits or Ctrl-C

        Handles:
        - KeyboardInterrupt (Ctrl-C) - exits gracefully
        - EOFError (Ctrl-D) - exits gracefully
        """
        logger.info("Starting CLI mode")

        try:
            while True:
                # Display todo list if present
                if hasattr(self.agent, "todo_list") and self.agent.todo_list:
                    todo_block = self._format_todo_block(self.agent.todo_list)
                    if todo_block:
                        print(f"\nTodo:\n{todo_block}\n")

                # Get user input
                try:
                    user_input = input("> ")
                except EOFError:
                    # Ctrl-D pressed
                    print()
                    break

                # Process and run agent
                should_continue = await self.process_and_run_agent(user_input)
                if not should_continue:
                    break

        except KeyboardInterrupt:
            # Ctrl-C pressed
            print("\n^C")
            logger.info("User interrupted CLI mode")

        logger.info("CLI mode ended")


# Standalone functions for backward compatibility with old agent/__init__.py


async def run_interactive(agent: Any) -> None:
    """Run interactive mode (standalone wrapper for backward compatibility).

    Args:
        agent: AssistantAgent instance
    """
    mode = CLIMode(agent, verbose=agent.settings.agent.verbose)
    await mode.initialize()
    await mode.run()


async def run_once(
    agent: Any, message: str, invoked_skill_id: Optional[str] = None
) -> str:
    """Run agent once with a message (for tests/scripts).

    Args:
        agent: AssistantAgent instance
        message: User message
        invoked_skill_id: Optional skill ID to invoke

    Returns:
        Agent response text
    """
    from basket_ai.types import UserMessage
    import time

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


def format_todo_block(agent: Any) -> str:
    """Format todo block for display (standalone wrapper).

    Args:
        agent: AssistantAgent instance

    Returns:
        Formatted todo block string
    """
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


def print_help(agent: Any) -> None:
    """Print help information (standalone wrapper).

    Args:
        agent: AssistantAgent instance
    """
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


def print_settings(agent: Any) -> None:
    """Print current settings (standalone wrapper).

    Args:
        agent: AssistantAgent instance
    """
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


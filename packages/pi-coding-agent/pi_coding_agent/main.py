"""
Main entry point for the pi-coding-agent CLI.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

from pi_agent import Agent
from pi_ai.api import get_model
from pi_ai.types import Context, UserMessage

from .core import SettingsManager, SessionManager
from .tools import BUILT_IN_TOOLS
from .extensions import ExtensionLoader


class CodingAgent:
    """
    Main coding agent class.

    Manages the agent lifecycle, tools, and user interaction.
    """

    def __init__(self, settings_manager: Optional[SettingsManager] = None, load_extensions: bool = True):
        """
        Initialize the coding agent.

        Args:
            settings_manager: Optional settings manager (uses default if None)
            load_extensions: Whether to load extensions at startup
        """
        self.settings_manager = settings_manager or SettingsManager()
        self.settings = self.settings_manager.load()

        # Create session manager
        sessions_dir = Path(self.settings.sessions_dir).expanduser()
        self.session_manager = SessionManager(sessions_dir)

        # Initialize model
        self.model = get_model(
            self.settings.model.provider,
            self.settings.model.model_id,
        )

        # Create context
        self.context = Context(
            systemPrompt=self._get_system_prompt(),
            messages=[],
        )

        # Create agent
        self.agent = Agent(self.model, self.context)
        self.agent.max_turns = self.settings.agent.max_turns

        # Register tools
        self._register_tools()

        # Setup event handlers
        self._setup_event_handlers()

        # Load extensions
        self.extension_loader = ExtensionLoader(self)
        if load_extensions:
            num_loaded = self.extension_loader.load_default_extensions()
            if num_loaded > 0:
                print(f"📦 Loaded {num_loaded} extension(s)")

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent."""
        return """You are a helpful coding assistant. You have access to tools to read, write, and edit files, execute shell commands, and search for code.

When using tools:
- Use 'read' to read file contents
- Use 'write' to create or overwrite files
- Use 'edit' to make precise changes to existing files
- Use 'bash' to run shell commands (git, npm, pytest, etc.)
- Use 'grep' to search for patterns in files

Always explain what you're doing before using tools.
"""

    def _register_tools(self) -> None:
        """Register all built-in tools with the agent."""
        for tool in BUILT_IN_TOOLS:
            self.agent.register_tool(
                name=tool["name"],
                description=tool["description"],
                parameters=tool["parameters"],
                execute_fn=tool["execute_fn"],
            )

    def _setup_event_handlers(self) -> None:
        """Setup event handlers for agent events."""

        def on_text_delta(event):
            """Handle text delta events."""
            if self.settings.agent.verbose:
                print(event["delta"], end="", flush=True)

        def on_tool_call_start(event):
            """Handle tool call start events."""
            if self.settings.agent.verbose:
                print(f"\n[Tool: {event['tool_name']}]", flush=True)

        def on_tool_call_end(event):
            """Handle tool call end events."""
            if event.get("error"):
                print(f"[Error: {event['error']}]", flush=True)

        self.agent.on("text_delta", on_text_delta)
        self.agent.on("agent_tool_call_start", on_tool_call_start)
        self.agent.on("agent_tool_call_end", on_tool_call_end)

    async def run_interactive(self) -> None:
        """
        Run the agent in interactive mode.

        Continuously prompts for user input and runs the agent.
        """
        print("Pi Coding Agent - Interactive Mode")
        print("Type 'exit' or 'quit' to quit, 'help' for help")
        print("-" * 50)

        while True:
            try:
                # Get user input
                user_input = input("\n> ").strip()

                if not user_input:
                    continue

                # Handle special commands
                if user_input.lower() in ["exit", "quit"]:
                    print("Goodbye!")
                    break

                if user_input.lower() == "help":
                    self._print_help()
                    continue

                if user_input.lower() == "settings":
                    self._print_settings()
                    continue

                # Handle slash commands (from extensions)
                if user_input.startswith("/"):
                    command_parts = user_input.split(maxsplit=1)
                    command = command_parts[0]
                    args = command_parts[1] if len(command_parts) > 1 else ""

                    if self.extension_loader.extension_api.execute_command(command, args):
                        continue
                    else:
                        print(f"Unknown command: {command}")
                        available = self.extension_loader.extension_api.get_commands()
                        if available:
                            print(f"Available commands: {', '.join(available)}")
                        continue

                # Add user message to context
                self.context.messages.append(
                    UserMessage(
                        role="user",
                        content=user_input,
                        timestamp=0,
                    )
                )

                # Run agent
                print()  # Newline before agent output
                await self.agent.run(stream_llm_events=True)
                print()  # Newline after agent output

            except KeyboardInterrupt:
                print("\n\nInterrupted. Type 'exit' to quit.")
                continue
            except Exception as e:
                print(f"\nError: {e}")
                if self.settings.agent.verbose:
                    import traceback
                    traceback.print_exc()

    async def run_once(self, message: str) -> str:
        """
        Run the agent once with a message.

        Args:
            message: User message

        Returns:
            Agent response text
        """
        # Add user message
        self.context.messages.append(
            UserMessage(role="user", content=message, timestamp=0)
        )

        # Run agent
        state = await self.agent.run(stream_llm_events=False)

        # Get last assistant message
        last_message = state.context.messages[-1]
        if hasattr(last_message, "content"):
            text_blocks = [
                block.text
                for block in last_message.content
                if hasattr(block, "text")
            ]
            return "\n".join(text_blocks)

        return ""

    def _print_help(self) -> None:
        """Print help information."""
        print("""
Available commands:
  help      - Show this help message
  settings  - Show current settings
  exit/quit - Exit the program

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
""")

    def _print_settings(self) -> None:
        """Print current settings."""
        print(f"""
Current settings:
  Model: {self.settings.model.provider} / {self.settings.model.model_id}
  Temperature: {self.settings.model.temperature}
  Max tokens: {self.settings.model.max_tokens}
  Max turns: {self.settings.agent.max_turns}
  Verbose: {self.settings.agent.verbose}
  Sessions dir: {self.settings.sessions_dir}
""")


async def main_async(args: Optional[list] = None) -> int:
    """
    Async main function.

    Args:
        args: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code
    """
    if args is None:
        args = sys.argv[1:]

    # Parse simple arguments
    use_tui = "--tui" in args
    if use_tui:
        args = [a for a in args if a != "--tui"]

    if "--help" in args or "-h" in args:
        print("""
Pi Coding Agent - AI-powered coding assistant

Usage:
  pi                     - Start interactive mode
  pi --tui               - Start TUI mode (terminal UI)
  pi "message"          - Run once with a message
  pi --help             - Show this help
  pi --version          - Show version

Interactive mode commands:
  help      - Show help
  settings  - Show settings
  exit/quit - Exit

Environment variables:
  OPENAI_API_KEY      - OpenAI API key
  ANTHROPIC_API_KEY   - Anthropic API key
  GOOGLE_API_KEY      - Google API key
""")
        return 0

    if "--version" in args or "-v" in args:
        print("Pi Coding Agent v0.1.0")
        return 0

    # Create agent
    try:
        agent = CodingAgent()
    except Exception as e:
        print(f"Error initializing agent: {e}")
        return 1

    # Run mode
    if len(args) == 0:
        # Choose mode based on flag
        if use_tui:
            # TUI mode
            try:
                from .modes.tui import run_tui_mode
                await run_tui_mode(agent.agent)
            except ImportError as e:
                print(f"Error: TUI mode requires 'pi-tui' package: {e}")
                print("Install with: poetry add pi-tui")
                return 1
        else:
            # Interactive mode (basic CLI)
            await agent.run_interactive()
    else:
        # One-shot mode
        message = " ".join(args)
        response = await agent.run_once(message)
        print(response)

    return 0


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code
    """
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())

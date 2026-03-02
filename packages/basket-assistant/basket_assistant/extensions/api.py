"""
Extension API for Pi Coding Agent

Provides a clean API for extensions to register tools, commands, and event handlers.
Tools registered via register_tool are wrapped with hook execution (tool.execute.before / after).
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type
from pydantic import BaseModel

from .hook_runner import HookRunner


def _wrap_tool_execute_with_hooks(
    tool_name: str,
    execute_fn: Callable,
    hook_runner: HookRunner,
    get_cwd: Callable[[], Path],
) -> Callable:
    """Wrap an execute_fn to run tool.execute.before and tool.execute.after hooks (subprocess)."""

    async def wrapped(**kwargs: Any) -> Any:
        input_before = {
            "tool_name": tool_name,
            "tool_call_id": "",
            "arguments": dict(kwargs),
            "cwd": str(get_cwd()),
        }
        output_before: Dict[str, Any] = {"modified_arguments": None}
        result_before = await hook_runner.run(
            "tool.execute.before",
            input_before,
            output=output_before,
            cwd=get_cwd(),
        )
        if result_before.get("permission") == "deny":
            reason = result_before.get("reason") or "Blocked by hook."
            return f"Error: {reason}"
        args = output_before.get("modified_arguments") or kwargs
        if not isinstance(args, dict):
            args = kwargs
        exc_raised: Optional[BaseException] = None
        try:
            result = await execute_fn(**args)
            error_msg = None
        except Exception as e:
            result = None
            error_msg = str(e)
            exc_raised = e
        input_after = {
            "tool_name": tool_name,
            "tool_call_id": "",
            "arguments": args,
            "result": result,
            "error": error_msg,
            "cwd": str(get_cwd()),
        }
        await hook_runner.run(
            "tool.execute.after",
            input_after,
            cwd=get_cwd(),
        )
        if exc_raised is not None:
            raise exc_raised
        return result

    return wrapped


class ExtensionAPI:
    """
    API for extensions to interact with the coding agent.

    Extensions can:
    - Register custom tools
    - Register slash commands
    - Subscribe to agent events
    - Access agent context and settings
    """

    def __init__(self, agent, hook_runner: Optional[HookRunner] = None):
        """
        Initialize the extension API.

        Args:
            agent: The CodingAgent instance
            hook_runner: Optional HookRunner for wrapping tool execution with before/after hooks
        """
        self._agent = agent
        self._hook_runner = hook_runner
        self._commands: Dict[str, Callable] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: Type[BaseModel],
    ):
        """
        Decorator to register a custom tool.

        Args:
            name: Tool name
            description: Tool description
            parameters: Pydantic model for tool parameters

        Example:
            @pi.register_tool(
                name="my_tool",
                description="Does something useful",
                parameters=MyToolParams
            )
            async def my_tool(param: str) -> str:
                return f"Result: {param}"
        """

        def decorator(func: Callable):
            execute_fn = func
            if self._hook_runner is not None:
                execute_fn = _wrap_tool_execute_with_hooks(
                    name,
                    func,
                    self._hook_runner,
                    get_cwd=lambda: Path.cwd(),
                )
            self._agent.agent.register_tool(
                name=name,
                description=description,
                parameters=parameters,
                execute_fn=execute_fn,
            )
            return func

        return decorator

    def register_command(self, command: str):
        """
        Decorator to register a slash command.

        Args:
            command: Command name (e.g., "/custom")

        Example:
            @pi.register_command("/hello")
            def hello_command(args: str):
                print(f"Hello, {args}!")
        """

        def decorator(func: Callable):
            # Store command handler
            self._commands[command] = func
            return func

        return decorator

    def on(self, event_name: str):
        """
        Decorator to register an event handler.

        Args:
            event_name: Event name (e.g., "tool_call", "text_delta")

        Example:
            @pi.on("tool_call")
            async def on_tool_call(event, ctx):
                print(f"Tool called: {event['tool_name']}")
        """

        def decorator(func: Callable):
            # Store event handler
            if event_name not in self._event_handlers:
                self._event_handlers[event_name] = []
            self._event_handlers[event_name].append(func)

            # Assistant-level events: register on CodingAgent, not basket_agent
            if event_name in ("before_run", "turn_done"):
                if event_name not in self._agent._assistant_event_handlers:
                    self._agent._assistant_event_handlers[event_name] = []
                self._agent._assistant_event_handlers[event_name].append(func)
            else:
                self._agent.agent.on(event_name, func)

            return func

        return decorator

    def get_context(self):
        """
        Get the current agent context.

        Returns:
            The agent's Context object
        """
        return self._agent.agent.context

    def get_settings(self):
        """
        Get the agent settings.

        Returns:
            The agent's Settings object
        """
        return self._agent.settings

    def get_session_manager(self):
        """
        Get the session manager.

        Returns:
            The SessionManager instance
        """
        return self._agent.session_manager

    def execute_command(self, command: str, args: str = "") -> bool:
        """
        Execute a registered command.

        Args:
            command: Command name (e.g., "/custom")
            args: Command arguments

        Returns:
            True if command was found and executed, False otherwise
        """
        handler = self._commands.get(command)
        if handler:
            handler(args)
            return True
        return False

    def get_commands(self) -> List[str]:
        """
        Get list of registered commands.

        Returns:
            List of command names
        """
        return list(self._commands.keys())


__all__ = ["ExtensionAPI"]

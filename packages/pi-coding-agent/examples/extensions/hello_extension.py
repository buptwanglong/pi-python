"""
Example Extension: Hello World

Demonstrates how to create a custom extension for Pi Coding Agent.
"""

from pydantic import BaseModel, Field


class HelloParams(BaseModel):
    """Parameters for the hello tool."""

    name: str = Field(..., description="Name to greet")
    enthusiastic: bool = Field(False, description="Use enthusiastic greeting")


def setup(pi):
    """
    Extension setup function.

    This function is called when the extension is loaded.

    Args:
        pi: ExtensionAPI instance
    """

    # Register a custom tool
    @pi.register_tool(
        name="hello",
        description="Say hello to someone",
        parameters=HelloParams,
    )
    async def hello_tool(name: str, enthusiastic: bool = False) -> str:
        """Say hello to someone."""
        if enthusiastic:
            return f"HELLO, {name.upper()}!!! 🎉"
        return f"Hello, {name}! 👋"

    # Register a slash command
    @pi.register_command("/greet")
    def greet_command(args: str):
        """Greet someone via command."""
        name = args.strip() or "World"
        print(f"👋 Hello, {name}!")

    # Register an event handler
    @pi.on("agent_tool_call_start")
    async def on_tool_call(event, ctx=None):
        """Log when tools are called."""
        tool_name = event.get("tool_name")
        print(f"🔧 Extension: Tool '{tool_name}' is being called")

    print("✅ Hello World extension loaded!")

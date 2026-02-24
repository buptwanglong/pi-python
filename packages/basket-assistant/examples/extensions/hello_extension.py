"""
Example Extension: Hello World

Demonstrates how to create a custom extension for Pi Coding Agent.
"""

from pydantic import BaseModel, Field


class HelloParams(BaseModel):
    """Parameters for the hello tool."""

    name: str = Field(..., description="Name to greet")
    enthusiastic: bool = Field(False, description="Use enthusiastic greeting")


def setup(basket):
    """
    Extension setup function.

    This function is called when the extension is loaded.

    Args:
        basket: ExtensionAPI instance
    """

    # Register a custom tool
    @basket.register_tool(
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
    @basket.register_command("/greet")
    def greet_command(args: str):
        """Greet someone via command."""
        name = args.strip() or "World"
        print(f"👋 Hello, {name}!")

    # Register an event handler
    @basket.on("agent_tool_call_start")
    async def on_tool_call(event, ctx=None):
        """Log when tools are called."""
        tool_name = event.get("tool_name")
        print(f"🔧 Extension: Tool '{tool_name}' is being called")

    print("✅ Hello World extension loaded!")

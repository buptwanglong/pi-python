"""Blackboard read/write tools for subagents.

These tools expose the shared blackboard to agents, allowing them
to share findings and state across agent boundaries.
"""

from typing import Callable

from pydantic import BaseModel, Field

from basket_agent.blackboard import Blackboard


class BlackboardReadParams(BaseModel):
    """Parameters for the blackboard_read tool."""

    key: str = Field(..., description="The key to read from the shared blackboard")


class BlackboardWriteParams(BaseModel):
    """Parameters for the blackboard_write tool."""

    key: str = Field(..., description="The key to write to the shared blackboard")
    value: str = Field(..., description="The value to store (as string)")


def create_blackboard_read_tool(get_blackboard: Callable[[], Blackboard]) -> dict:
    """
    Create a blackboard_read tool.

    Args:
        get_blackboard: A callable returning the current Blackboard instance.

    Returns:
        A tool dict with name, description, parameters, and execute_fn.
    """

    async def execute(key: str) -> str:
        bb = get_blackboard()
        value = bb.read(key)
        if value is None:
            available = bb.keys()
            return f"Key '{key}' not found in blackboard. Available keys: {available}"
        return str(value)

    return {
        "name": "blackboard_read",
        "description": (
            "Read a value from the shared blackboard. "
            "Use this to access findings from other agents."
        ),
        "parameters": BlackboardReadParams,
        "execute_fn": execute,
    }


def create_blackboard_write_tool(
    get_blackboard: Callable[[], Blackboard],
    set_blackboard: Callable[[Blackboard], None],
    agent_name: str,
) -> dict:
    """
    Create a blackboard_write tool.

    Args:
        get_blackboard: A callable returning the current Blackboard instance.
        set_blackboard: A callable that replaces the current Blackboard.
        agent_name: The name of the agent using this tool (used as author).

    Returns:
        A tool dict with name, description, parameters, and execute_fn.
    """

    async def execute(key: str, value: str) -> str:
        bb = get_blackboard()
        new_bb = bb.write(key, value, author=agent_name)
        set_blackboard(new_bb)
        return f"Written key '{key}' to blackboard"

    return {
        "name": "blackboard_write",
        "description": (
            "Write a value to the shared blackboard. "
            "Use this to share findings with other agents."
        ),
        "parameters": BlackboardWriteParams,
        "execute_fn": execute,
    }


__all__ = [
    "BlackboardReadParams",
    "BlackboardWriteParams",
    "create_blackboard_read_tool",
    "create_blackboard_write_tool",
]

"""Tests for the task tool (create_task_tool, execute_task)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from basket_assistant.tools import create_task_tool, TaskParams


@pytest.fixture
def agent_ref_no_agents():
    """Agent ref with no subagents configured."""
    ref = MagicMock()
    ref._get_subagent_configs.return_value = {}
    return ref


@pytest.fixture
def agent_ref_with_agents():
    """Agent ref with two subagents."""
    from basket_assistant.core import SubAgentConfig
    ref = MagicMock()
    ref._get_subagent_configs.return_value = {
        "general": SubAgentConfig(
            description="General-purpose research",
            prompt="You are a research assistant.",
        ),
        "explore": SubAgentConfig(
            description="Fast codebase exploration",
            prompt="You explore codebases. Be concise.",
            tools={"read": True, "grep": True},
        ),
    }
    return ref


@pytest.mark.asyncio
async def test_task_tool_no_agents_description(agent_ref_no_agents):
    """When no subagents, description says no subagents configured."""
    tool = create_task_tool(agent_ref_no_agents)
    assert tool["name"] == "task"
    assert "No subagents configured" in tool["description"]
    assert tool["parameters"] is TaskParams


@pytest.mark.asyncio
async def test_task_tool_description_includes_subagent_list(agent_ref_with_agents):
    """When subagents exist, description lists them with names and descriptions."""
    tool = create_task_tool(agent_ref_with_agents)
    desc = tool["description"]
    assert "general" in desc
    assert "General-purpose research" in desc
    assert "explore" in desc
    assert "Fast codebase exploration" in desc
    assert "subagent_type" in desc or "Available subagents" in desc


@pytest.mark.asyncio
async def test_task_tool_execute_returns_task_result_wrapper(agent_ref_with_agents):
    """execute_fn calls run_subagent and returns task_id + <task_result> wrapper."""
    agent_ref_with_agents.run_subagent = AsyncMock(return_value="Done. Found 3 files.")
    tool = create_task_tool(agent_ref_with_agents)
    result = await tool["execute_fn"](
        description="list files",
        prompt="List files in current directory",
        subagent_type="explore",
    )
    assert "task_id: none" in result
    assert "<task_result>" in result
    assert "</task_result>" in result
    assert "Done. Found 3 files." in result
    agent_ref_with_agents.run_subagent.assert_called_once_with("explore", "List files in current directory")


@pytest.mark.asyncio
async def test_task_tool_execute_unknown_subagent_returns_error_in_result(agent_ref_with_agents):
    """When run_subagent returns error (e.g. unknown name), result still wraps it in task_result."""
    agent_ref_with_agents.run_subagent = AsyncMock(
        return_value='SubAgent "unknown" not found. Available: general, explore'
    )
    tool = create_task_tool(agent_ref_with_agents)
    result = await tool["execute_fn"](
        description="x",
        prompt="Do something",
        subagent_type="unknown",
    )
    assert "<task_result>" in result
    assert "not found" in result
    assert "general" in result or "explore" in result

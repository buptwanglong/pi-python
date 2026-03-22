"""Tests for the task tool (create_task_tool, execute_task)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from basket_assistant.agent.context import AgentContext
from basket_assistant.tools import create_task_tool, TaskParams


def _make_test_ctx(subagent_configs=None, session_id="test"):
    """Build an AgentContext with mock callbacks for testing."""
    configs = subagent_configs or {}
    recent_tasks: list[dict] = []

    ctx = AgentContext(
        session_id=session_id,
        plan_mode=False,
        run_subagent=AsyncMock(return_value="Done"),
        get_subagent_configs=MagicMock(return_value=configs),
        get_subagent_display_description=MagicMock(return_value="A subagent"),
        save_todos=AsyncMock(),
        save_pending_asks=AsyncMock(),
        append_recent_task=MagicMock(side_effect=lambda r: recent_tasks.append(r)),
        update_recent_task=MagicMock(),
        settings=MagicMock(),
        get_skills_dirs=MagicMock(return_value=[]),
        get_plugin_skill_dirs=MagicMock(return_value=[]),
        draft_skill_from_session=AsyncMock(),
        save_pending_skill_draft=AsyncMock(),
    )
    return ctx, recent_tasks


@pytest.fixture
def ctx_no_agents():
    """AgentContext with no subagents configured."""
    ctx, _ = _make_test_ctx()
    return ctx


@pytest.fixture
def ctx_with_agents():
    """AgentContext with two subagents."""
    from basket_assistant.core import SubAgentConfig

    configs = {
        "general": SubAgentConfig(tools=None),
        "explore": SubAgentConfig(tools={"read": True, "grep": True}),
    }
    ctx, recent_tasks = _make_test_ctx(subagent_configs=configs)
    # Override display description to return meaningful labels
    ctx = AgentContext(
        session_id=ctx.session_id,
        plan_mode=ctx.plan_mode,
        run_subagent=ctx.run_subagent,
        get_subagent_configs=ctx.get_subagent_configs,
        get_subagent_display_description=MagicMock(
            side_effect=lambda name, cfg: (
                "General-purpose research" if name == "general" else "Fast codebase exploration"
            )
        ),
        save_todos=ctx.save_todos,
        save_pending_asks=ctx.save_pending_asks,
        append_recent_task=MagicMock(side_effect=lambda r: recent_tasks.append(r)),
        update_recent_task=MagicMock(),
        settings=ctx.settings,
        get_skills_dirs=ctx.get_skills_dirs,
        get_plugin_skill_dirs=ctx.get_plugin_skill_dirs,
        draft_skill_from_session=ctx.draft_skill_from_session,
        save_pending_skill_draft=ctx.save_pending_skill_draft,
    )
    return ctx, recent_tasks


@pytest.mark.asyncio
async def test_task_tool_no_agents_description(ctx_no_agents):
    """When no subagents, description says no subagents configured."""
    tool = create_task_tool(ctx_no_agents)
    assert tool["name"] == "task"
    assert "No subagents configured" in tool["description"]
    assert tool["parameters"] is TaskParams


@pytest.mark.asyncio
async def test_task_tool_description_includes_subagent_list(ctx_with_agents):
    """When subagents exist, description lists them with names and descriptions."""
    ctx, _ = ctx_with_agents
    tool = create_task_tool(ctx)
    desc = tool["description"]
    assert "general" in desc
    assert "General-purpose research" in desc
    assert "explore" in desc
    assert "Fast codebase exploration" in desc
    assert "subagent_type" in desc or "Available subagents" in desc


@pytest.mark.asyncio
async def test_task_tool_execute_returns_task_result_wrapper(ctx_with_agents):
    """execute_fn calls run_subagent and returns task_id + <task_result> wrapper."""
    ctx, recent_tasks = ctx_with_agents
    # Override run_subagent for this test
    ctx = AgentContext(
        session_id=ctx.session_id,
        plan_mode=ctx.plan_mode,
        run_subagent=AsyncMock(return_value="Done. Found 3 files."),
        get_subagent_configs=ctx.get_subagent_configs,
        get_subagent_display_description=ctx.get_subagent_display_description,
        save_todos=ctx.save_todos,
        save_pending_asks=ctx.save_pending_asks,
        append_recent_task=MagicMock(side_effect=lambda r: recent_tasks.append(r)),
        update_recent_task=MagicMock(),
        settings=ctx.settings,
        get_skills_dirs=ctx.get_skills_dirs,
        get_plugin_skill_dirs=ctx.get_plugin_skill_dirs,
        draft_skill_from_session=ctx.draft_skill_from_session,
        save_pending_skill_draft=ctx.save_pending_skill_draft,
    )
    tool = create_task_tool(ctx)
    result = await tool["execute_fn"](
        description="list files",
        prompt="List files in current directory",
        subagent_type="explore",
    )
    assert "task_id:" in result
    assert "<task_result>" in result
    assert "</task_result>" in result
    assert "Done. Found 3 files." in result
    ctx.run_subagent.assert_called_once_with("explore", "List files in current directory")


@pytest.mark.asyncio
async def test_task_tool_execute_unknown_subagent_returns_error_in_result(ctx_with_agents):
    """When run_subagent returns error (e.g. unknown name), result still wraps it in task_result."""
    ctx, recent_tasks = ctx_with_agents
    ctx = AgentContext(
        session_id=ctx.session_id,
        plan_mode=ctx.plan_mode,
        run_subagent=AsyncMock(
            return_value='SubAgent "unknown" not found. Available: general, explore'
        ),
        get_subagent_configs=ctx.get_subagent_configs,
        get_subagent_display_description=ctx.get_subagent_display_description,
        save_todos=ctx.save_todos,
        save_pending_asks=ctx.save_pending_asks,
        append_recent_task=MagicMock(side_effect=lambda r: recent_tasks.append(r)),
        update_recent_task=MagicMock(),
        settings=ctx.settings,
        get_skills_dirs=ctx.get_skills_dirs,
        get_plugin_skill_dirs=ctx.get_plugin_skill_dirs,
        draft_skill_from_session=ctx.draft_skill_from_session,
        save_pending_skill_draft=ctx.save_pending_skill_draft,
    )
    tool = create_task_tool(ctx)
    result = await tool["execute_fn"](
        description="x",
        prompt="Do something",
        subagent_type="unknown",
    )
    assert "<task_result>" in result
    assert "not found" in result
    assert "general" in result or "explore" in result


@pytest.mark.asyncio
async def test_task_tool_execute_appends_recent_task(ctx_with_agents):
    """execute_fn appends a task record via ctx.append_recent_task."""
    ctx, recent_tasks = ctx_with_agents
    ctx = AgentContext(
        session_id=ctx.session_id,
        plan_mode=ctx.plan_mode,
        run_subagent=AsyncMock(return_value="Result"),
        get_subagent_configs=ctx.get_subagent_configs,
        get_subagent_display_description=ctx.get_subagent_display_description,
        save_todos=ctx.save_todos,
        save_pending_asks=ctx.save_pending_asks,
        append_recent_task=MagicMock(side_effect=lambda r: recent_tasks.append(r)),
        update_recent_task=MagicMock(),
        settings=ctx.settings,
        get_skills_dirs=ctx.get_skills_dirs,
        get_plugin_skill_dirs=ctx.get_plugin_skill_dirs,
        draft_skill_from_session=ctx.draft_skill_from_session,
        save_pending_skill_draft=ctx.save_pending_skill_draft,
    )
    tool = create_task_tool(ctx)
    await tool["execute_fn"](
        description="test task",
        prompt="Do something",
        subagent_type="explore",
    )
    assert len(recent_tasks) == 1
    assert recent_tasks[0]["description"] == "test task"
    assert recent_tasks[0]["status"] == "running"
    # update_recent_task should have been called with completed status
    ctx.update_recent_task.assert_called_once()
    call_args = ctx.update_recent_task.call_args
    assert call_args[0][0] == -1
    assert call_args[0][1]["status"] == "completed"

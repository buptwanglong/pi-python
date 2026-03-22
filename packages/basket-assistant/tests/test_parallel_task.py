"""Tests for the parallel_task tool (create_parallel_task_tool)."""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from basket_assistant.agent.context import AgentContext
from basket_assistant.tools.task import (
    ParallelTaskParams,
    TaskSpec,
    create_parallel_task_tool,
)


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


def _make_ctx_with_agents():
    """Build AgentContext with two subagent configs."""
    from basket_assistant.core import SubAgentConfig

    configs = {
        "general": SubAgentConfig(tools=None),
        "explore": SubAgentConfig(tools={"read": True, "grep": True}),
    }
    return _make_test_ctx(subagent_configs=configs)


@pytest.fixture
def ctx_no_agents():
    """AgentContext with no subagents configured."""
    ctx, _ = _make_test_ctx()
    return ctx


@pytest.fixture
def ctx_with_agents():
    """AgentContext with two subagents."""
    ctx, recent_tasks = _make_ctx_with_agents()
    return ctx


class TestCreateParallelTaskTool:
    """Tests for create_parallel_task_tool factory function."""

    def test_tool_name_and_params(self, ctx_with_agents):
        """Tool has correct name and parameter schema."""
        tool = create_parallel_task_tool(ctx_with_agents)
        assert tool["name"] == "parallel_task"
        assert tool["parameters"] is ParallelTaskParams

    def test_description_lists_agents(self, ctx_with_agents):
        """Description includes available subagent names."""
        tool = create_parallel_task_tool(ctx_with_agents)
        desc = tool["description"]
        assert "explore" in desc
        assert "general" in desc
        assert "parallel" in desc.lower()

    def test_description_no_agents(self, ctx_no_agents):
        """When no agents, description says so."""
        tool = create_parallel_task_tool(ctx_no_agents)
        desc = tool["description"]
        assert "No subagents configured" in desc


class TestExecuteParallelTasks:
    """Tests for the parallel_task execute_fn."""

    @pytest.mark.asyncio
    async def test_single_task_works(self, ctx_with_agents):
        """A single task in the list works correctly."""
        ctx = AgentContext(
            session_id=ctx_with_agents.session_id,
            plan_mode=ctx_with_agents.plan_mode,
            run_subagent=AsyncMock(return_value="Found 5 files."),
            get_subagent_configs=ctx_with_agents.get_subagent_configs,
            get_subagent_display_description=ctx_with_agents.get_subagent_display_description,
            save_todos=ctx_with_agents.save_todos,
            save_pending_asks=ctx_with_agents.save_pending_asks,
            append_recent_task=ctx_with_agents.append_recent_task,
            update_recent_task=ctx_with_agents.update_recent_task,
            settings=ctx_with_agents.settings,
            get_skills_dirs=ctx_with_agents.get_skills_dirs,
            get_plugin_skill_dirs=ctx_with_agents.get_plugin_skill_dirs,
            draft_skill_from_session=ctx_with_agents.draft_skill_from_session,
            save_pending_skill_draft=ctx_with_agents.save_pending_skill_draft,
        )
        tool = create_parallel_task_tool(ctx)

        result = await tool["execute_fn"](
            tasks=[
                {
                    "description": "find files",
                    "prompt": "List all Python files",
                    "subagent_type": "explore",
                }
            ]
        )

        assert "1 tasks" in result
        assert "Found 5 files." in result
        assert "<task_result>" in result
        assert "completed" in result
        ctx.run_subagent.assert_called_once_with(
            "explore", "List all Python files"
        )

    @pytest.mark.asyncio
    async def test_multiple_tasks_run_in_parallel(self, ctx_with_agents):
        """Multiple tasks are dispatched concurrently."""
        call_order = []

        async def mock_subagent(name: str, prompt: str) -> str:
            call_order.append(f"start-{name}")
            await asyncio.sleep(0.05)
            call_order.append(f"end-{name}")
            return f"Result from {name}: {prompt}"

        ctx = AgentContext(
            session_id=ctx_with_agents.session_id,
            plan_mode=ctx_with_agents.plan_mode,
            run_subagent=mock_subagent,
            get_subagent_configs=ctx_with_agents.get_subagent_configs,
            get_subagent_display_description=ctx_with_agents.get_subagent_display_description,
            save_todos=ctx_with_agents.save_todos,
            save_pending_asks=ctx_with_agents.save_pending_asks,
            append_recent_task=ctx_with_agents.append_recent_task,
            update_recent_task=ctx_with_agents.update_recent_task,
            settings=ctx_with_agents.settings,
            get_skills_dirs=ctx_with_agents.get_skills_dirs,
            get_plugin_skill_dirs=ctx_with_agents.get_plugin_skill_dirs,
            draft_skill_from_session=ctx_with_agents.draft_skill_from_session,
            save_pending_skill_draft=ctx_with_agents.save_pending_skill_draft,
        )
        tool = create_parallel_task_tool(ctx)

        result = await tool["execute_fn"](
            tasks=[
                {
                    "description": "task A",
                    "prompt": "Do A",
                    "subagent_type": "general",
                },
                {
                    "description": "task B",
                    "prompt": "Do B",
                    "subagent_type": "explore",
                },
            ]
        )

        assert "2 tasks" in result
        assert "Result from general" in result
        assert "Result from explore" in result
        # Both should have started before either ended (parallel)
        assert "start-general" in call_order
        assert "start-explore" in call_order

    @pytest.mark.asyncio
    async def test_one_failure_doesnt_block_others(self, ctx_with_agents):
        """One failing subagent doesn't prevent other results."""

        async def mock_subagent(name: str, prompt: str) -> str:
            if name == "general":
                raise RuntimeError("Agent crashed!")
            return "Success"

        ctx = AgentContext(
            session_id=ctx_with_agents.session_id,
            plan_mode=ctx_with_agents.plan_mode,
            run_subagent=mock_subagent,
            get_subagent_configs=ctx_with_agents.get_subagent_configs,
            get_subagent_display_description=ctx_with_agents.get_subagent_display_description,
            save_todos=ctx_with_agents.save_todos,
            save_pending_asks=ctx_with_agents.save_pending_asks,
            append_recent_task=ctx_with_agents.append_recent_task,
            update_recent_task=ctx_with_agents.update_recent_task,
            settings=ctx_with_agents.settings,
            get_skills_dirs=ctx_with_agents.get_skills_dirs,
            get_plugin_skill_dirs=ctx_with_agents.get_plugin_skill_dirs,
            draft_skill_from_session=ctx_with_agents.draft_skill_from_session,
            save_pending_skill_draft=ctx_with_agents.save_pending_skill_draft,
        )
        tool = create_parallel_task_tool(ctx)

        result = await tool["execute_fn"](
            tasks=[
                {
                    "description": "fail task",
                    "prompt": "Do X",
                    "subagent_type": "general",
                },
                {
                    "description": "ok task",
                    "prompt": "Do Y",
                    "subagent_type": "explore",
                },
            ]
        )

        assert "failed" in result
        assert "Agent crashed!" in result
        assert "Success" in result

    @pytest.mark.asyncio
    async def test_result_order_matches_input(self, ctx_with_agents):
        """Results are returned in the same order as input tasks."""

        async def mock_subagent(name: str, prompt: str) -> str:
            # Second task finishes first
            delay = 0.1 if name == "general" else 0.01
            await asyncio.sleep(delay)
            return f"Result-{name}"

        ctx = AgentContext(
            session_id=ctx_with_agents.session_id,
            plan_mode=ctx_with_agents.plan_mode,
            run_subagent=mock_subagent,
            get_subagent_configs=ctx_with_agents.get_subagent_configs,
            get_subagent_display_description=ctx_with_agents.get_subagent_display_description,
            save_todos=ctx_with_agents.save_todos,
            save_pending_asks=ctx_with_agents.save_pending_asks,
            append_recent_task=ctx_with_agents.append_recent_task,
            update_recent_task=ctx_with_agents.update_recent_task,
            settings=ctx_with_agents.settings,
            get_skills_dirs=ctx_with_agents.get_skills_dirs,
            get_plugin_skill_dirs=ctx_with_agents.get_plugin_skill_dirs,
            draft_skill_from_session=ctx_with_agents.draft_skill_from_session,
            save_pending_skill_draft=ctx_with_agents.save_pending_skill_draft,
        )
        tool = create_parallel_task_tool(ctx)

        result = await tool["execute_fn"](
            tasks=[
                {
                    "description": "slow",
                    "prompt": "A",
                    "subagent_type": "general",
                },
                {
                    "description": "fast",
                    "prompt": "B",
                    "subagent_type": "explore",
                },
            ]
        )

        # Task 1 should appear before Task 2 in output
        idx_1 = result.index("Task 1")
        idx_2 = result.index("Task 2")
        assert idx_1 < idx_2

    @pytest.mark.asyncio
    async def test_task_spec_model_validation(self):
        """TaskSpec validates required fields."""
        spec = TaskSpec(
            description="test", prompt="do something", subagent_type="agent1"
        )
        assert spec.description == "test"
        assert spec.prompt == "do something"
        assert spec.subagent_type == "agent1"

    @pytest.mark.asyncio
    async def test_parallel_task_params_validation(self):
        """ParallelTaskParams validates the tasks list."""
        params = ParallelTaskParams(
            tasks=[
                TaskSpec(
                    description="t1",
                    prompt="p1",
                    subagent_type="a1",
                ),
                TaskSpec(
                    description="t2",
                    prompt="p2",
                    subagent_type="a2",
                ),
            ]
        )
        assert len(params.tasks) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

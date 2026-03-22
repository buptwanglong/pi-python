"""Tests for AgentContext — the public contract between tools and Agent."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from basket_assistant.agent.context import AgentContext


def test_agent_context_is_frozen():
    """AgentContext should be immutable (frozen dataclass)."""
    ctx = AgentContext(
        session_id="test-session",
        plan_mode=False,
        run_subagent=AsyncMock(),
        get_subagent_configs=MagicMock(return_value={}),
        get_subagent_display_description=MagicMock(return_value="desc"),
        save_todos=AsyncMock(),
        save_pending_asks=AsyncMock(),
        append_recent_task=MagicMock(),
        update_recent_task=MagicMock(),
        settings=MagicMock(),
    )
    with pytest.raises(AttributeError):
        ctx.session_id = "changed"


def test_agent_context_fields_accessible():
    """All declared fields should be accessible."""
    mock_settings = MagicMock()
    ctx = AgentContext(
        session_id="s1",
        plan_mode=True,
        run_subagent=AsyncMock(),
        get_subagent_configs=MagicMock(return_value={"explore": {}}),
        get_subagent_display_description=MagicMock(return_value="Explorer"),
        save_todos=AsyncMock(),
        save_pending_asks=AsyncMock(),
        append_recent_task=MagicMock(),
        update_recent_task=MagicMock(),
        settings=mock_settings,
    )
    assert ctx.session_id == "s1"
    assert ctx.plan_mode is True
    assert ctx.get_subagent_configs() == {"explore": {}}
    assert ctx.settings is mock_settings


def test_agent_context_none_session_id():
    """session_id can be None (no active session)."""
    ctx = AgentContext(
        session_id=None,
        plan_mode=False,
        run_subagent=AsyncMock(),
        get_subagent_configs=MagicMock(return_value={}),
        get_subagent_display_description=MagicMock(return_value=""),
        save_todos=AsyncMock(),
        save_pending_asks=AsyncMock(),
        append_recent_task=MagicMock(),
        update_recent_task=MagicMock(),
        settings=MagicMock(),
    )
    assert ctx.session_id is None

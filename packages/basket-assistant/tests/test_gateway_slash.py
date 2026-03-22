"""Gateway short-circuits slash commands via AssistantAgent.try_process_gateway_slash."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from basket_gateway.gateway import AgentGateway


@pytest.mark.asyncio
async def test_gateway_slash_returns_without_appending_user_message() -> None:
    """Handled slash does not append UserMessage or call LLM."""
    agent = MagicMock()
    agent.session_manager = MagicMock()
    agent.session_manager.ensure_session = AsyncMock()
    agent.set_session_id = AsyncMock()
    agent.context = MagicMock()
    agent.context.messages = []

    async def try_slash(user_content: str, *, event_sink=None):
        return ("Plugin output", False)

    agent.try_process_gateway_slash = try_slash

    def factory(_agent_name=None):
        return agent

    gw = AgentGateway(factory)
    received: list[dict] = []

    async def sink(m: dict) -> None:
        received.append(m)

    text = await gw.run("default", "/plugin list", event_sink=sink, agent_name=None)

    assert text == "Plugin output"
    assert agent.context.messages == []
    assert any(m.get("type") == "slash_result" for m in received)

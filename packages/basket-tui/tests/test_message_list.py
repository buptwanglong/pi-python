"""
Tests for MessageList and ToolCard.
Covers update_from_state with all role types (user, assistant, system, error, tool)
to catch MountError and similar regressions.
"""

import pytest
from basket_tui import PiCodingAgentApp
from basket_tui.components.message_list import MessageList, ToolCard
from basket_tui.constants import MESSAGE_LIST_ID
from basket_tui.state import AppState


@pytest.mark.asyncio
async def test_message_list_update_from_state_with_user_message():
    """MessageList.update_from_state runs without error when state has user message (catches MountError)."""
    app = PiCodingAgentApp()
    async with app.run_test():
        message_list = app.query_one(f"#{MESSAGE_LIST_ID}", MessageList)
        state = AppState(
            output_blocks=["welcome", "hi", "hello"],
            output_blocks_with_role=[
                ("system", "welcome"),
                ("user", "hi"),
                ("assistant", "hello"),
            ],
        )
        message_list.update_from_state(state)
        # 3 blocks -> 3 top-level children (system Static, user Horizontal, assistant Static)
        assert len(message_list.children) == 3


@pytest.mark.asyncio
async def test_message_list_update_from_state_all_roles():
    """MessageList.update_from_state runs without error for system, user, assistant, error, tool."""
    app = PiCodingAgentApp()
    async with app.run_test():
        message_list = app.query_one(f"#{MESSAGE_LIST_ID}", MessageList)
        state = AppState(
            output_blocks_with_role=[
                ("system", "System message"),
                ("user", "User input"),
                ("assistant", "Assistant reply"),
                ("error", "Error: something failed"),
                ("tool", "read_file result"),
            ],
            tool_expanded={3: False},
        )
        message_list.update_from_state(state)
        assert len(message_list.children) == 5


@pytest.mark.asyncio
async def test_message_list_update_from_state_empty():
    """MessageList.update_from_state with empty state leaves no children."""
    app = PiCodingAgentApp()
    async with app.run_test():
        message_list = app.query_one(f"#{MESSAGE_LIST_ID}", MessageList)
        state = AppState(output_blocks_with_role=[])
        message_list.update_from_state(state)
        assert len(message_list.children) == 0


def test_tool_card_collapsed():
    """ToolCard collapsed stores first-line summary internally."""
    card = ToolCard("line1\nline2\nline3", index=0, expanded=False)
    assert card._content == "line1\nline2\nline3"
    assert card._expanded is False
    assert card._index == 0


def test_tool_card_expanded():
    """ToolCard expanded shows full content."""
    content = "full\ncontent"
    card = ToolCard(content, index=0, expanded=True)
    assert card._content == content
    assert card._expanded is True
    card.set_expanded(False)
    assert card._expanded is False

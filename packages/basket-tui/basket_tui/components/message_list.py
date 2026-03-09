"""
Message list and tool card for chat log (Phase 3).
Replaces single TextArea with card-based list; ToolCard supports expand/collapse.
"""

from textual.containers import Vertical, Horizontal
from textual.widgets import Static

from ..constants import (
    MESSAGE_BLOCK_CLASS,
    MESSAGE_USER_CLASS,
    MESSAGE_ASSISTANT_CLASS,
    MESSAGE_SYSTEM_CLASS,
    MESSAGE_ERROR_CLASS,
    TOOL_BLOCK_CLASS,
)

TOOL_CARD_COLLAPSED_LEN = 80


class ToolCard(Static):
    """Single tool block: collapsed shows summary, expanded shows full content."""

    def __init__(self, content: str, index: int, expanded: bool, **kwargs) -> None:
        super().__init__(**kwargs)
        self._content = content or ""
        self._index = index
        self._expanded = expanded
        self.update_render()

    def update_render(self) -> None:
        if self._expanded:
            text = self._content
        else:
            first_line = self._content.split("\n")[0] if self._content else ""
            if len(first_line) > TOOL_CARD_COLLAPSED_LEN:
                text = first_line[: TOOL_CARD_COLLAPSED_LEN - 3] + "..."
            else:
                text = first_line or "(no content)"
        self.update(text)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self.update_render()


class MessageList(Vertical):
    """Vertical list of message cards (user, assistant, system, tool). Built from state.get_transcript_blocks()."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.can_focus = True
        # So list height follows content; prevents large gap between first Q and A (override Vertical's 1fr)
        self.styles.height = "auto"

    def update_from_state(self, state) -> None:
        """Rebuild children from state.output_blocks_with_role + streaming tail and tool_expanded."""
        blocks = state.get_transcript_blocks()
        self.remove_children()
        for i, (role, content) in enumerate(blocks):
            content = content or ""
            if role == "user":
                row = Horizontal(classes="message-row message-row--user")
                self.mount(row)
                row.mount(Static("", classes="message-spacer"))
                row.mount(Static(content, classes=f"{MESSAGE_BLOCK_CLASS} {MESSAGE_USER_CLASS}"))
            elif role == "assistant":
                self.mount(Static(content, classes=f"{MESSAGE_BLOCK_CLASS} {MESSAGE_ASSISTANT_CLASS}"))
            elif role == "system":
                self.mount(Static(content, classes=f"{MESSAGE_BLOCK_CLASS} {MESSAGE_SYSTEM_CLASS}"))
            elif role == "error":
                self.mount(Static(content, classes=f"{MESSAGE_BLOCK_CLASS} {MESSAGE_ERROR_CLASS}"))
            elif role == "tool":
                expanded = state.tool_expanded.get(i, False)
                card = ToolCard(
                    content,
                    index=i,
                    expanded=expanded,
                    classes=f"{MESSAGE_BLOCK_CLASS} {TOOL_BLOCK_CLASS}",
                )
                self.mount(card)
            else:
                self.mount(Static(content, classes=f"{MESSAGE_BLOCK_CLASS} {MESSAGE_SYSTEM_CLASS}"))

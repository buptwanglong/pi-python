"""Tests for _ConversationBodyWindow mouse event filtering."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from prompt_toolkit.mouse_events import MouseEventType

from basket_tui.native.ui.layout import _ConversationBodyWindow


def _make_mouse_event(event_type: MouseEventType) -> SimpleNamespace:
    """Create a lightweight mouse event stub."""
    return SimpleNamespace(event_type=event_type, position=SimpleNamespace(x=0, y=0))


def _make_body_window(on_scroll: MagicMock | None = None) -> _ConversationBodyWindow:
    """Build a _ConversationBodyWindow with minimal dependencies."""
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.layout.controls import FormattedTextControl

    control = FormattedTextControl(text=lambda: ANSI("hello"), focusable=False)
    return _ConversationBodyWindow(
        on_scroll_event=on_scroll or MagicMock(),
        content=control,
        wrap_lines=False,
    )


class TestConversationBodyWindowMouse:
    """Verify body window only captures scroll events."""

    @pytest.mark.parametrize(
        "event_type",
        [MouseEventType.MOUSE_DOWN, MouseEventType.MOUSE_UP, MouseEventType.MOUSE_MOVE],
    )
    def test_non_scroll_events_return_not_implemented(self, event_type: MouseEventType) -> None:
        """Click and drag events must pass through to the terminal for native text selection."""
        win = _make_body_window()
        event = _make_mouse_event(event_type)
        result = win._mouse_handler(event)
        assert result is NotImplemented

    @pytest.mark.parametrize(
        "event_type",
        [MouseEventType.SCROLL_UP, MouseEventType.SCROLL_DOWN],
    )
    def test_scroll_events_are_handled(self, event_type: MouseEventType) -> None:
        """Scroll wheel events must be processed by the window for in-app scrolling."""
        win = _make_body_window()
        event = _make_mouse_event(event_type)
        # Patch the parent's _mouse_handler to avoid needing a full render_info
        with patch.object(type(win).__bases__[0], "_mouse_handler", return_value=None):
            result = win._mouse_handler(event)
        # Should NOT return NotImplemented (event was handled)
        assert result is not NotImplemented

    def test_scroll_triggers_callback_on_change(self) -> None:
        """When scroll position changes, the on_scroll_event callback fires."""
        callback = MagicMock()
        win = _make_body_window(on_scroll=callback)
        event = _make_mouse_event(MouseEventType.SCROLL_DOWN)

        def fake_parent_handler(mouse_event: object) -> None:
            # Simulate scroll position changing
            win.vertical_scroll = 5

        with patch.object(type(win).__bases__[0], "_mouse_handler", side_effect=fake_parent_handler):
            win.vertical_scroll = 0  # initial
            win._mouse_handler(event)

        callback.assert_called_once_with(win)

    def test_scroll_no_callback_when_position_unchanged(self) -> None:
        """When scroll position stays the same, no callback fires."""
        callback = MagicMock()
        win = _make_body_window(on_scroll=callback)
        event = _make_mouse_event(MouseEventType.SCROLL_UP)

        with patch.object(type(win).__bases__[0], "_mouse_handler", return_value=None):
            win.vertical_scroll = 0
            win._mouse_handler(event)

        callback.assert_not_called()

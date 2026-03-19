"""Tests for double-Ctrl+C exit confirmation."""

from basket_tui.native.ui.exit_confirm import ExitConfirmState


def test_exit_confirm_first_press_does_not_exit():
    s = ExitConfirmState()
    assert s.handle_ctrl_c() is False
    assert s.is_pending is True


def test_exit_confirm_second_press_exits():
    s = ExitConfirmState()
    assert s.handle_ctrl_c() is False
    assert s.handle_ctrl_c() is True
    assert s.is_pending is False


def test_reset_pending():
    s = ExitConfirmState()
    assert s.handle_ctrl_c() is False
    s.reset_pending()
    assert s.is_pending is False
    assert s.handle_ctrl_c() is False

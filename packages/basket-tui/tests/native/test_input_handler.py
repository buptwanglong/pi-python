"""Tests for native input_handler."""

import queue
from unittest.mock import patch

import pytest

from basket_tui.native.commands import HELP_LINES
from basket_tui.native.input_handler import handle_input, open_picker


def test_handle_input_empty_returns_handled():
    q = queue.Queue()
    body: list[str] = []
    assert handle_input("", "http://localhost", q, body) == "handled"
    assert handle_input("   ", "http://localhost", q, body) == "handled"


def test_handle_input_exit_returns_exit():
    q = queue.Queue()
    body: list[str] = []
    assert handle_input("/exit", "http://localhost", q, body) == "exit"


def test_handle_input_plain_text_returns_send():
    q = queue.Queue()
    body: list[str] = []
    assert handle_input("hello", "http://localhost", q, body) == "send"


def test_handle_input_help_returns_handled_and_appends_help_lines():
    q = queue.Queue()
    body: list[str] = []
    assert handle_input("/help", "http://localhost", q, body) == "handled"
    assert len(body) >= len(HELP_LINES)
    for line in HELP_LINES:
        assert line in body


def test_handle_input_unknown_slash_returns_handled_and_appends_message():
    q = queue.Queue()
    body: list[str] = []
    assert handle_input("/unknown", "http://localhost", q, body) == "handled"
    assert any("Unknown command" in line for line in body)


def test_open_picker_session_puts_switch_session_when_picker_returns_id():
    q = queue.Queue()
    body: list[str] = []
    with patch("basket_tui.native.input_handler.run_session_picker", return_value="sid-123"):
        open_picker("session", "http://localhost", q, body)
    assert q.get_nowait() == ("switch_session", "sid-123")


def test_open_picker_agent_puts_switch_agent_when_picker_returns_name():
    q = queue.Queue()
    body: list[str] = []
    with patch("basket_tui.native.input_handler.run_agent_picker", return_value="explore"):
        open_picker("agent", "http://localhost", q, body)
    assert q.get_nowait() == ("switch_agent", "explore")

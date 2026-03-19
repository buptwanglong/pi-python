"""Tests for native input_handler."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from basket_tui.native.ui import HELP_LINES, handle_input, open_picker


def _make_mock_connection():
    conn = AsyncMock()
    conn.send_message = AsyncMock()
    conn.send_abort = AsyncMock()
    conn.send_new_session = AsyncMock()
    conn.send_switch_session = AsyncMock()
    conn.send_switch_agent = AsyncMock()
    return conn


def _collector() -> tuple[list[str], object]:
    body: list[str] = []

    def output_put(line: str) -> None:
        body.append(line)

    return body, output_put


def test_handle_input_empty_returns_handled():
    mock_conn = _make_mock_connection()
    body, output_put = _collector()
    assert handle_input("", "http://localhost", mock_conn, output_put) == "handled"
    assert handle_input("   ", "http://localhost", mock_conn, output_put) == "handled"


def test_handle_input_exit_returns_exit():
    mock_conn = _make_mock_connection()
    _, output_put = _collector()
    assert handle_input("/exit", "http://localhost", mock_conn, output_put) == "exit"


@pytest.mark.asyncio
async def test_handle_input_plain_text_returns_send():
    mock_conn = _make_mock_connection()
    _, output_put = _collector()
    result = handle_input("hello", "http://localhost", mock_conn, output_put)
    assert result == "send"
    await asyncio.sleep(0.05)
    mock_conn.send_message.assert_called_once_with("hello")


def test_handle_input_help_returns_handled_and_appends_help_lines():
    mock_conn = _make_mock_connection()
    body, output_put = _collector()
    assert handle_input("/help", "http://localhost", mock_conn, output_put) == "handled"
    assert len(body) >= len(HELP_LINES)
    for line in HELP_LINES:
        assert line in body


def test_handle_input_unknown_slash_returns_handled_and_appends_message():
    mock_conn = _make_mock_connection()
    body, output_put = _collector()
    assert handle_input("/unknown", "http://localhost", mock_conn, output_put) == "handled"
    assert any("Unknown command" in line for line in body)


@pytest.mark.asyncio
async def test_handle_input_abort_calls_send_abort():
    mock_conn = _make_mock_connection()
    _, output_put = _collector()
    result = handle_input("/abort", "http://localhost", mock_conn, output_put)
    assert result == "handled"
    await asyncio.sleep(0.05)
    mock_conn.send_abort.assert_called_once()


@pytest.mark.asyncio
async def test_handle_input_new_calls_send_new_session():
    mock_conn = _make_mock_connection()
    _, output_put = _collector()
    result = handle_input("/new", "http://localhost", mock_conn, output_put)
    assert result == "handled"
    await asyncio.sleep(0.05)
    mock_conn.send_new_session.assert_called_once()


@pytest.mark.asyncio
async def test_open_picker_session_puts_switch_session_when_picker_returns_id():
    mock_conn = _make_mock_connection()
    _, output_put = _collector()
    with patch("basket_tui.native.ui.input_handler.run_session_picker", return_value="sid-123"):
        open_picker("session", "http://localhost", mock_conn, output_put)
    await asyncio.sleep(0.05)
    mock_conn.send_switch_session.assert_called_once_with("sid-123")


@pytest.mark.asyncio
async def test_open_picker_agent_puts_switch_agent_when_picker_returns_name():
    mock_conn = _make_mock_connection()
    _, output_put = _collector()
    with patch("basket_tui.native.ui.input_handler.run_agent_picker", return_value="explore"):
        open_picker("agent", "http://localhost", mock_conn, output_put)
    await asyncio.sleep(0.05)
    mock_conn.send_switch_agent.assert_called_once_with("explore")

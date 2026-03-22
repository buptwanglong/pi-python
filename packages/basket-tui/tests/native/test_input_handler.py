"""Tests for native input_handler."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from basket_tui.native.ui import HELP_LINES, handle_input, open_picker
from basket_tui.native.ui.pickers import PLUGIN_HELP_LINES


def _make_mock_connection():
    conn = AsyncMock()
    conn.send_message = AsyncMock()
    conn.send_abort = AsyncMock()
    conn.send_new_session = AsyncMock()
    conn.send_switch_session = AsyncMock()
    conn.send_switch_agent = AsyncMock()
    conn.send_plugin_install = AsyncMock()
    return conn


def _collector() -> tuple[list[str], object]:
    body: list[str] = []

    def output_put(line: str) -> None:
        body.append(line)

    return body, output_put


@pytest.mark.asyncio
async def test_handle_input_empty_returns_handled():
    mock_conn = _make_mock_connection()
    body, output_put = _collector()
    assert await handle_input("", "http://localhost", mock_conn, output_put) == "handled"
    assert await handle_input("   ", "http://localhost", mock_conn, output_put) == "handled"


@pytest.mark.asyncio
async def test_handle_input_exit_returns_exit():
    mock_conn = _make_mock_connection()
    _, output_put = _collector()
    assert await handle_input("/exit", "http://localhost", mock_conn, output_put) == "exit"


@pytest.mark.asyncio
async def test_handle_input_quit_returns_exit():
    mock_conn = _make_mock_connection()
    _, output_put = _collector()
    assert await handle_input("/quit", "http://localhost", mock_conn, output_put) == "exit"


@pytest.mark.asyncio
async def test_handle_input_plain_text_returns_send():
    mock_conn = _make_mock_connection()
    _, output_put = _collector()
    result = await handle_input("hello", "http://localhost", mock_conn, output_put)
    assert result == "send"
    await asyncio.sleep(0.05)
    mock_conn.send_message.assert_called_once_with("hello")


@pytest.mark.asyncio
async def test_handle_input_help_returns_handled_and_appends_help_lines():
    mock_conn = _make_mock_connection()
    body, output_put = _collector()
    assert await handle_input("/help", "http://localhost", mock_conn, output_put) == "handled"
    assert len(body) >= len(HELP_LINES)
    for line in HELP_LINES:
        assert line in body


@pytest.mark.asyncio
async def test_handle_input_plugin_bare_shows_usage():
    mock_conn = _make_mock_connection()
    body, output_put = _collector()
    assert await handle_input("/plugin", "http://localhost", mock_conn, output_put) == "handled"
    mock_conn.send_message.assert_not_called()
    for line in PLUGIN_HELP_LINES:
        assert line in body


@pytest.mark.asyncio
async def test_handle_input_plugins_runs_plugin_list_picker():
    mock_conn = _make_mock_connection()
    _, output_put = _collector()
    with patch(
        "basket_tui.native.ui.pickers.run_plugin_list_picker",
        new_callable=AsyncMock,
    ) as m:
        result = await handle_input("/plugins", "http://localhost", mock_conn, output_put)
    assert result == "handled"
    mock_conn.send_message.assert_not_called()
    m.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_input_plugin_list_runs_picker():
    mock_conn = _make_mock_connection()
    _, output_put = _collector()
    with patch(
        "basket_tui.native.ui.pickers.run_plugin_list_picker",
        new_callable=AsyncMock,
    ) as m:
        result = await handle_input("/plugin list", "http://localhost", mock_conn, output_put)
    assert result == "handled"
    mock_conn.send_message.assert_not_called()
    m.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_input_plugin_install_sends_plugin_install_ws():
    mock_conn = _make_mock_connection()
    _, output_put = _collector()
    result = await handle_input(
        "/plugin install /tmp/my-plugin",
        "http://localhost",
        mock_conn,
        output_put,
    )
    assert result == "handled"
    mock_conn.send_message.assert_not_called()
    await asyncio.sleep(0.05)
    mock_conn.send_plugin_install.assert_called_once_with("/tmp/my-plugin")


@pytest.mark.asyncio
async def test_handle_input_plugin_uninstall_forwards_to_gateway():
    mock_conn = _make_mock_connection()
    body, output_put = _collector()
    result = await handle_input(
        "/plugin uninstall foo",
        "http://localhost",
        mock_conn,
        output_put,
    )
    assert result == "send"
    assert not any("Unknown command" in line for line in body)
    await asyncio.sleep(0.05)
    mock_conn.send_message.assert_called_once_with("/plugin uninstall foo")


@pytest.mark.asyncio
async def test_handle_input_abort_calls_send_abort():
    mock_conn = _make_mock_connection()
    _, output_put = _collector()
    result = await handle_input("/abort", "http://localhost", mock_conn, output_put)
    assert result == "handled"
    await asyncio.sleep(0.05)
    mock_conn.send_abort.assert_called_once()


@pytest.mark.asyncio
async def test_handle_input_new_calls_send_new_session():
    mock_conn = _make_mock_connection()
    _, output_put = _collector()
    result = await handle_input("/new", "http://localhost", mock_conn, output_put)
    assert result == "handled"
    await asyncio.sleep(0.05)
    mock_conn.send_new_session.assert_called_once()


@pytest.mark.asyncio
async def test_open_picker_session_puts_switch_session_when_picker_returns_id():
    mock_conn = _make_mock_connection()
    _, output_put = _collector()

    async def mock_run_session_picker(base_url):
        return "sid-123"

    with patch(
        "basket_tui.native.ui.input_handler.run_session_picker",
        side_effect=mock_run_session_picker,
    ):
        await open_picker("session", "http://localhost", mock_conn, output_put)
    await asyncio.sleep(0.05)
    mock_conn.send_switch_session.assert_called_once_with("sid-123")


@pytest.mark.asyncio
async def test_open_picker_agent_puts_switch_agent_when_picker_returns_name():
    mock_conn = _make_mock_connection()
    _, output_put = _collector()

    async def mock_run_agent_picker(base_url):
        return "explore"

    with patch(
        "basket_tui.native.ui.input_handler.run_agent_picker",
        side_effect=mock_run_agent_picker,
    ):
        await open_picker("agent", "http://localhost", mock_conn, output_put)
    await asyncio.sleep(0.05)
    mock_conn.send_switch_agent.assert_called_once_with("explore")

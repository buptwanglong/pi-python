"""Tests for GatewayWsConnection: reader dispatch and send_* methods."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from basket_tui.native.connection import GatewayHandlers, GatewayWsConnection


@pytest.mark.asyncio
async def test_reader_calls_on_text_delta_for_inbound_messages():
    """Inbound text_delta messages call on_text_delta and append deltas."""
    deltas: list[str] = []

    async def gen():
        yield '{"type":"text_delta","delta":"a"}'
        yield '{"type":"text_delta","delta":"b"}'

    mock_ws = MagicMock()
    mock_ws.__aiter__ = lambda self: gen()
    mock_ws.send = MagicMock()
    mock_ws.close = AsyncMock()

    class AsyncCtx:
        async def __aenter__(self):
            return mock_ws

        async def __aexit__(self, *args):
            return None

    handlers: GatewayHandlers = {
        "on_text_delta": lambda event: deltas.append(event.delta),
    }
    ready_event = asyncio.Event()
    conn = GatewayWsConnection("ws://test/ws", handlers, ready_event)

    with patch("basket_tui.native.connection.client.websockets") as mock_websockets:
        mock_websockets.connect.return_value = AsyncCtx()
        task = asyncio.create_task(conn.run())
        try:
            await asyncio.wait_for(ready_event.wait(), timeout=5.0)
            await asyncio.sleep(0.15)
            assert deltas == ["a", "b"]
        finally:
            await conn.close()
            await asyncio.wait_for(asyncio.shield(task), timeout=2.0)


@pytest.mark.asyncio
async def test_send_message_sends_json_with_type_message():
    """send_message(text) sends {"type":"message","content":text}."""
    never_set = asyncio.Event()

    async def never_end():
        await never_set.wait()

    mock_ws = MagicMock()
    mock_ws.__aiter__ = lambda self: never_end()
    mock_ws.send = AsyncMock()
    mock_ws.close = AsyncMock()

    class AsyncCtx:
        async def __aenter__(self):
            return mock_ws

        async def __aexit__(self, *args):
            return None

    handlers: GatewayHandlers = {}
    ready_event = asyncio.Event()
    conn = GatewayWsConnection("ws://test/ws", handlers, ready_event)

    with patch("basket_tui.native.connection.client.websockets") as mock_websockets:
        mock_websockets.connect.return_value = AsyncCtx()
        task = asyncio.create_task(conn.run())
        try:
            await asyncio.wait_for(ready_event.wait(), timeout=5.0)
            await conn.send_message("hi")
            mock_ws.send.assert_called_once()
            (arg,) = mock_ws.send.call_args[0]
            assert json.loads(arg) == {"type": "message", "content": "hi"}
        finally:
            await conn.close()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_send_abort_sends_type_abort():
    """send_abort() sends {"type":"abort"}."""
    async def never_end():
        await asyncio.Event().wait()

    mock_ws = MagicMock()
    mock_ws.__aiter__ = lambda self: never_end()
    mock_ws.send = AsyncMock()
    mock_ws.close = AsyncMock()

    class AsyncCtx:
        async def __aenter__(self):
            return mock_ws

        async def __aexit__(self, *args):
            return None

    ready_event = asyncio.Event()
    conn = GatewayWsConnection("ws://test/ws", {}, ready_event)

    with patch("basket_tui.native.connection.client.websockets") as mock_websockets:
        mock_websockets.connect.return_value = AsyncCtx()
        task = asyncio.create_task(conn.run())
        try:
            await asyncio.wait_for(ready_event.wait(), timeout=5.0)
            await conn.send_abort()
            mock_ws.send.assert_called_once_with(json.dumps({"type": "abort"}))
        finally:
            await conn.close()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_send_new_session_sends_type_new_session():
    """send_new_session() sends {"type":"new_session"}."""
    async def never_end():
        await asyncio.Event().wait()

    mock_ws = MagicMock()
    mock_ws.__aiter__ = lambda self: never_end()
    mock_ws.send = AsyncMock()
    mock_ws.close = AsyncMock()

    class AsyncCtx:
        async def __aenter__(self):
            return mock_ws

        async def __aexit__(self, *args):
            return None

    ready_event = asyncio.Event()
    conn = GatewayWsConnection("ws://test/ws", {}, ready_event)

    with patch("basket_tui.native.connection.client.websockets") as mock_websockets:
        mock_websockets.connect.return_value = AsyncCtx()
        task = asyncio.create_task(conn.run())
        try:
            await asyncio.wait_for(ready_event.wait(), timeout=5.0)
            await conn.send_new_session()
            mock_ws.send.assert_called_once_with(
                json.dumps({"type": "new_session"})
            )
        finally:
            await conn.close()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_send_switch_session_sends_type_switch_session_and_session_id():
    """send_switch_session(session_id) sends {"type":"switch_session","session_id":session_id}."""
    async def never_end():
        await asyncio.Event().wait()

    mock_ws = MagicMock()
    mock_ws.__aiter__ = lambda self: never_end()
    mock_ws.send = AsyncMock()
    mock_ws.close = AsyncMock()

    class AsyncCtx:
        async def __aenter__(self):
            return mock_ws

        async def __aexit__(self, *args):
            return None

    ready_event = asyncio.Event()
    conn = GatewayWsConnection("ws://test/ws", {}, ready_event)

    with patch("basket_tui.native.connection.client.websockets") as mock_websockets:
        mock_websockets.connect.return_value = AsyncCtx()
        task = asyncio.create_task(conn.run())
        try:
            await asyncio.wait_for(ready_event.wait(), timeout=5.0)
            await conn.send_switch_session("sess-123")
            mock_ws.send.assert_called_once_with(
                json.dumps({"type": "switch_session", "session_id": "sess-123"})
            )
        finally:
            await conn.close()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_send_switch_agent_sends_type_switch_agent_and_agent_name():
    """send_switch_agent(agent_name) sends {"type":"switch_agent","agent_name":agent_name}."""
    async def never_end():
        await asyncio.Event().wait()

    mock_ws = MagicMock()
    mock_ws.__aiter__ = lambda self: never_end()
    mock_ws.send = AsyncMock()
    mock_ws.close = AsyncMock()

    class AsyncCtx:
        async def __aenter__(self):
            return mock_ws

        async def __aexit__(self, *args):
            return None

    ready_event = asyncio.Event()
    conn = GatewayWsConnection("ws://test/ws", {}, ready_event)

    with patch("basket_tui.native.connection.client.websockets") as mock_websockets:
        mock_websockets.connect.return_value = AsyncCtx()
        task = asyncio.create_task(conn.run())
        try:
            await asyncio.wait_for(ready_event.wait(), timeout=5.0)
            await conn.send_switch_agent("explore")
            mock_ws.send.assert_called_once_with(
                json.dumps({"type": "switch_agent", "agent_name": "explore"})
            )
        finally:
            await conn.close()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_send_plugin_install_sends_type_and_source():
    """send_plugin_install(source) sends {"type":"plugin_install","source":...}."""
    async def never_end():
        await asyncio.Event().wait()

    mock_ws = MagicMock()
    mock_ws.__aiter__ = lambda self: never_end()
    mock_ws.send = AsyncMock()
    mock_ws.close = AsyncMock()

    class AsyncCtx:
        async def __aenter__(self):
            return mock_ws

        async def __aexit__(self, *args):
            return None

    ready_event = asyncio.Event()
    conn = GatewayWsConnection("ws://test/ws", {}, ready_event)

    with patch("basket_tui.native.connection.client.websockets") as mock_websockets:
        mock_websockets.connect.return_value = AsyncCtx()
        task = asyncio.create_task(conn.run())
        try:
            await asyncio.wait_for(ready_event.wait(), timeout=5.0)
            await conn.send_plugin_install("https://example.com/p.zip")
            mock_ws.send.assert_called_once_with(
                json.dumps({"type": "plugin_install", "source": "https://example.com/p.zip"})
            )
        finally:
            await conn.close()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

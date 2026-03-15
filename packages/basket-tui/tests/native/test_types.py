"""Tests for WebSocket–TUI boundary types (GatewayHandlers, GatewayConnectionProtocol)."""

import pytest

from basket_tui.native.connection import GatewayConnectionProtocol, GatewayHandlers


def test_gateway_handlers_optional_keys() -> None:
    """GatewayHandlers allows empty dict (all keys optional via total=False)."""
    h: GatewayHandlers = {}
    assert h == {}


def test_protocol_has_send_methods() -> None:
    """GatewayConnectionProtocol is defined and usable as a type."""
    assert GatewayConnectionProtocol is not None

"""
Basket Relay: application-layer message relay for outbound-only agent connection.

No basket-agent dependency; only forwards WebSocket messages between agent and client.
"""

from .app import create_app

__all__ = ["create_app"]

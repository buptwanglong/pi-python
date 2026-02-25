"""
Channel protocol: channels mount routes or start background tasks via mount(app, gateway, config).
"""

from typing import Any, Protocol

from starlette.applications import Starlette


class Channel(Protocol):
    """Protocol for gateway channels. mount() may add routes or start background tasks."""

    def mount(
        self,
        app: Starlette,
        gateway: Any,
        config: dict,
    ) -> None:
        """Mount this channel onto the app (add routes, start threads, etc.)."""
        ...

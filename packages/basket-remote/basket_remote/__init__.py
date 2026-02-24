"""
pi-remote: Remote web terminal for Pi (ttyd-based).

Use with ZeroTier or LAN: bind to your machine's IP and open the URL from
another device (e.g. phone). Requires ttyd to be installed on the system.
"""

from .serve import run_serve

__all__ = ["run_serve"]

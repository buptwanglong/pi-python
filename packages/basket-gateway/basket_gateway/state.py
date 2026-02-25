"""
State files for the resident assistant gateway: pid and port under ~/.basket/.
"""

import os
from pathlib import Path
from typing import Optional


def _config_dir() -> Path:
    return Path.home() / ".basket"


def _pid_file() -> Path:
    return _config_dir() / "serve.pid"


def _port_file() -> Path:
    return _config_dir() / "serve.port"


def read_serve_state() -> tuple[Optional[int], Optional[int]]:
    """
    Read pid and port from state files.

    Returns:
        (pid, port) or (None, None) if files missing or invalid.
    """
    pid_path = _pid_file()
    port_path = _port_file()
    pid = None
    port = None
    if pid_path.exists():
        try:
            raw = pid_path.read_text().strip()
            if raw:
                pid = int(raw)
        except (ValueError, OSError):
            pass
    if port_path.exists():
        try:
            raw = port_path.read_text().strip()
            if raw:
                port = int(raw)
        except (ValueError, OSError):
            pass
    return pid, port


def write_serve_state(pid: int, port: int) -> None:
    """Write pid and port to state files. Creates config dir if needed."""
    d = _config_dir()
    d.mkdir(parents=True, exist_ok=True)
    _pid_file().write_text(str(pid))
    _port_file().write_text(str(port))


def clear_serve_state() -> None:
    """Remove pid and port files if they exist."""
    for p in (_pid_file(), _port_file()):
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass


def is_serve_running() -> tuple[bool, Optional[int]]:
    """
    Check if the gateway process is still running.

    Returns:
        (running, pid). running is True iff pid file exists and process exists.
    """
    pid, _ = read_serve_state()
    if pid is None:
        return False, None
    try:
        os.kill(pid, 0)
        return True, pid
    except OSError:
        return False, pid


def get_serve_port() -> Optional[int]:
    """Return the port from state file, or None."""
    _, port = read_serve_state()
    return port

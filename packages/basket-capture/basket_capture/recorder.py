"""PTY recorder: run a command in a pseudo-terminal and write asciinema v2 .cast."""

import json
import os
import select
import signal
import subprocess
import time
from pathlib import Path
from typing import Union

try:
    import pty
except ImportError:
    pty = None  # type: ignore[assignment]


def record(
    command: Union[str, list[str]],
    output_path: Union[str, Path],
    timeout: float | None = None,
    *,
    width: int = 80,
    height: int = 24,
) -> None:
    """
    Run command in a PTY and record stdout to an asciinema v2 .cast file.

    Args:
        command: Shell command string (passed to shell) or list of args (exec directly).
        output_path: Path to write the .cast JSON file.
        timeout: Optional max recording time in seconds; None = until process exits.
        width: Terminal width for cast header (default 80).
        height: Terminal height for cast header (default 24).

    Raises:
        OSError: If PTY cannot be allocated (e.g. not available on this platform).
    """
    if pty is None:
        raise OSError("pty not available on this platform")

    output_path = Path(output_path)
    master_fd, slave_fd = pty.openpty()

    # Set slave window size so child sees correct dimensions
    try:
        import fcntl
        import struct
        import termios

        buf = struct.pack("HHHH", height, width, 0, 0)
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, buf)
    except (ImportError, OSError):
        pass

    if isinstance(command, str):
        proc = subprocess.Popen(
            command,
            shell=True,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )
    else:
        proc = subprocess.Popen(
            command,
            shell=False,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )

    os.close(slave_fd)

    stdout_events: list[list[Union[float, str]]] = []
    last_ts = time.time()
    start_ts = last_ts
    interrupt_requested = False

    def _on_sigint(_signum: int, _frame: object) -> None:
        nonlocal interrupt_requested
        interrupt_requested = True

    old_sigint = signal.signal(signal.SIGINT, _on_sigint)
    try:
        while True:
            if timeout is not None and (time.time() - start_ts) >= timeout:
                break
            if interrupt_requested:
                break
            ready, _, _ = select.select([master_fd], [], [], 0.1)
            if not ready:
                continue
            try:
                data = os.read(master_fd, 4096)
            except OSError:
                break
            if not data:
                break
            now = time.time()
            delay = round(now - last_ts, 6)
            last_ts = now
            text = data.decode("utf-8", errors="replace")
            stdout_events.append([delay, text])
    except KeyboardInterrupt:
        interrupt_requested = True
        # Fall through to save
    finally:
        signal.signal(signal.SIGINT, old_sigint)
        try:
            os.close(master_fd)
        except OSError:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=1.0)
        except (OSError, subprocess.TimeoutExpired):
            try:
                proc.kill()
            except OSError:
                pass

    cast = {
        "version": 2,
        "width": width,
        "height": height,
        "timestamp": int(start_ts),
        "env": {},
        "title": "",
        "stdout": stdout_events,
    }
    output_path.write_text(json.dumps(cast), encoding="utf-8")

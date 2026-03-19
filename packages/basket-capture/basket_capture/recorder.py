"""PTY recorder: run a command in a pseudo-terminal and write asciinema v2 .cast."""

from __future__ import annotations

import json
import os
import select
import signal
import subprocess
import sys
import time
import tty
from pathlib import Path
from typing import Union

try:
    import pty
    import termios
except ImportError:
    pty = None  # type: ignore[assignment]
    termios = None  # type: ignore[assignment]

from basket_capture.session_bundle import (
    DEFAULT_ACTION_BOUNDARY_BYTE,
    ActionRecord,
    SessionBundleWriter,
)


def record(
    command: Union[str, list[str]],
    output_path: Union[str, Path],
    timeout: float | None = None,
    *,
    width: int = 0,
    height: int = 0,
    bundle: SessionBundleWriter | None = None,
    action_boundary_byte: int = DEFAULT_ACTION_BOUNDARY_BYTE,
    forward_action_boundary: bool = False,
    screenshot_cmd: str | None = None,
) -> None:
    """
    Run command in a PTY, forward keyboard input, display its output,
    and record stdout to an asciinema v2 .cast file.

    The caller's terminal is switched to raw mode so every keystroke
    reaches the child immediately. Child output is both displayed on
    screen and recorded into the .cast file.

    When ``bundle`` is set, also writes ``input.jsonl``, splits actions on
    ``action_boundary_byte`` (default 0x1C = Ctrl+\\), and on session end
    writes ``session_manifest.json`` and per-action ``meta.json``.
    Unless ``forward_action_boundary`` is True, the boundary byte is not
    sent to the child.

    Args:
        command: Shell command string (passed to shell) or list of args.
        output_path: Path to write the .cast JSON file (should match
            ``bundle.cast_path`` when bundle mode).
        timeout: Optional max recording time in seconds; None = until process exits.
        width: Terminal width (0 = auto-detect from current terminal).
        height: Terminal height (0 = auto-detect from current terminal).
        bundle: Optional session bundle writer (input log opened here).
        action_boundary_byte: Byte that ends the current action (default Ctrl+\\).
        forward_action_boundary: If True, forward boundary byte to the PTY.
        screenshot_cmd: If set, shell command run at each action end;
            ``{out_path}`` is replaced with the screenshot file path.

    Raises:
        OSError: If PTY cannot be allocated, executable not found, or spawn fails.
        RuntimeError: If not running in a TTY.
    """
    if pty is None or termios is None:
        raise OSError("pty/termios not available on this platform")
    if not sys.stdin.isatty():
        raise RuntimeError("请在终端中运行 (run in a terminal)")

    stdin_fd = sys.stdin.fileno()
    stdout_fd = sys.stdout.fileno()

    if width == 0 or height == 0:
        try:
            cols, rows = os.get_terminal_size(stdout_fd)
            if width == 0:
                width = cols
            if height == 0:
                height = rows
        except OSError:
            width = width or 80
            height = height or 24

    output_path = Path(output_path)
    if bundle is not None and output_path.resolve() != bundle.cast_path.resolve():
        raise ValueError("output_path must equal bundle.cast_path when bundle is set")

    try:
        master_fd, slave_fd = pty.openpty()
    except OSError as e:
        raise OSError(f"Failed to allocate PTY: {e}") from e

    try:
        import fcntl
        import struct

        buf = struct.pack("HHHH", height, width, 0, 0)
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, buf)
    except (ImportError, OSError):
        pass

    try:
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
    except FileNotFoundError as e:
        os.close(slave_fd)
        os.close(master_fd)
        raise OSError(f"Executable not found: {e}") from e
    except OSError as e:
        os.close(slave_fd)
        os.close(master_fd)
        raise OSError(f"Spawn failed: {e}") from e

    os.close(slave_fd)

    stdout_events: list[list[Union[float, str]]] = []
    last_ts = time.time()
    start_ts = last_ts
    interrupt_requested = False
    boundary_requested = False

    # Bundle / action state
    action_seq = 1
    action_start_wall = start_ts
    label_buffer = ""

    if bundle is not None:
        bundle.open_input_log()

    def rel_t() -> float:
        return round(time.time() - start_ts, 6)

    def boundary_reason() -> str:
        if action_boundary_byte == DEFAULT_ACTION_BOUNDARY_BYTE:
            return "hotkey_ctrl_backslash"
        return "hotkey_custom_byte"

    def finalize_current_action() -> None:
        if bundle is None:
            return
        t_end_s = time.time() - start_ts
        t_start_s = action_start_wall - start_ts
        slug_src = label_buffer.strip() or "segment"
        adir = bundle.ensure_action_dir(action_seq, slug_src)
        screenshots_rel: list[str] = []
        if screenshot_cmd:
            shot = adir / "screenshots" / f"end-{time.time():.3f}.png"
            shot.parent.mkdir(parents=True, exist_ok=True)
            try:
                cmd = screenshot_cmd.replace("{out_path}", str(shot))
                subprocess.run(
                    cmd,
                    shell=True,
                    timeout=60,
                    check=False,
                    capture_output=True,
                )
                if shot.exists():
                    screenshots_rel.append(str(shot.relative_to(bundle.root)))
            except (OSError, subprocess.TimeoutExpired):
                pass
        bundle.write_action_meta(
            adir,
            seq=action_seq,
            slug=slug_src,
            t_start_s=t_start_s,
            t_end_s=t_end_s,
            screenshots=screenshots_rel,
        )
        bundle.register_action(
            ActionRecord(
                dir_relative=str(adir.relative_to(bundle.root)).replace("\\", "/"),
                t_start_s=round(t_start_s, 6),
                t_end_s=round(t_end_s, 6),
            )
        )

    def advance_action_after_boundary() -> None:
        nonlocal action_seq, action_start_wall, label_buffer
        action_seq += 1
        action_start_wall = time.time()
        label_buffer = ""

    def handle_action_boundary(source: str) -> None:
        if bundle is None:
            return
        next_seq = action_seq + 1
        bundle.append_input_event(
            {
                "t": rel_t(),
                "type": "action_boundary",
                "reason": boundary_reason() if source == "hotkey" else "signal_usr1",
                "action_seq": next_seq,
            }
        )
        finalize_current_action()
        advance_action_after_boundary()

    def forward_stdin_raw(data: bytes) -> None:
        if not data:
            return
        try:
            os.write(master_fd, data)
        except OSError:
            pass

    def forward_stdin_bundle(data: bytes) -> None:
        nonlocal label_buffer
        if not data:
            return
        delim = bytes([action_boundary_byte & 0xFF])
        parts = data.split(delim)
        for i, part in enumerate(parts):
            if part:
                try:
                    os.write(master_fd, part)
                except OSError:
                    return
                try:
                    text = part.decode("utf-8")
                except UnicodeDecodeError:
                    bundle.append_input_event(  # type: ignore[union-attr]
                        {"t": rel_t(), "type": "bytes", "hex": part.hex()}
                    )
                else:
                    bundle.append_input_event(  # type: ignore[union-attr]
                        {"t": rel_t(), "type": "text", "text": text}
                    )
                    for ch in text:
                        if ch.isprintable():
                            label_buffer += ch
                    if len(label_buffer) > 256:
                        label_buffer = label_buffer[-256:]
            if i < len(parts) - 1:
                if forward_action_boundary:
                    forward_stdin_raw(delim)
                handle_action_boundary("hotkey")

    def _on_sigint(_signum: int, _frame: object) -> None:
        nonlocal interrupt_requested
        interrupt_requested = True

    def _on_usr1(_signum: int, _frame: object) -> None:
        nonlocal boundary_requested
        boundary_requested = True

    old_sigint = signal.signal(signal.SIGINT, _on_sigint)
    old_sigusr1: object = signal.SIG_DFL
    usr1_handler_installed = False
    if bundle is not None and hasattr(signal, "SIGUSR1"):
        old_sigusr1 = signal.signal(signal.SIGUSR1, _on_usr1)
        usr1_handler_installed = True

    old_tty_attrs = termios.tcgetattr(stdin_fd)
    try:
        tty.setraw(stdin_fd)
        while True:
            if bundle is not None and boundary_requested:
                boundary_requested = False
                handle_action_boundary("usr1")
            if timeout is not None and (time.time() - start_ts) >= timeout:
                break
            if interrupt_requested:
                break
            if proc.poll() is not None:
                try:
                    data = os.read(master_fd, 4096)
                    if data:
                        now = time.time()
                        delay = round(now - last_ts, 6)
                        last_ts = now
                        text = data.decode("utf-8", errors="replace")
                        stdout_events.append([delay, text])
                        os.write(stdout_fd, data)
                except OSError:
                    pass
                break
            try:
                ready, _, _ = select.select([master_fd, stdin_fd], [], [], 0.1)
            except InterruptedError:
                continue
            if not ready:
                continue
            if master_fd in ready:
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
                os.write(stdout_fd, data)
            if stdin_fd in ready:
                try:
                    data = os.read(stdin_fd, 4096)
                except OSError:
                    break
                if not data:
                    break
                if bundle is None:
                    forward_stdin_raw(data)
                else:
                    forward_stdin_bundle(data)
    except KeyboardInterrupt:
        interrupt_requested = True
    finally:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_tty_attrs)
        signal.signal(signal.SIGINT, old_sigint)
        if usr1_handler_installed:
            signal.signal(signal.SIGUSR1, old_sigusr1)  # type: ignore[arg-type]
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

        if bundle is not None:
            # Finalize the open action (always one in flight).
            finalize_current_action()
            bundle.close_input_log()
            bundle.write_manifest(time.time())

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

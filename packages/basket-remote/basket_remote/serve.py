"""
Serve a command in a web terminal via ttyd.

Requires ttyd to be installed on the system (e.g. brew install ttyd).
"""

import shutil
import signal
import subprocess
import sys
from typing import List


def run_serve(
    bind: str = "0.0.0.0",
    port: int = 7681,
    command: List[str] | None = None,
) -> None:
    """
    Run ttyd to serve a command in a web terminal.

    Each browser connection gets a new subprocess running the given command.
    This process blocks until ttyd exits (e.g. Ctrl+C). SIGINT is forwarded
    to the ttyd child process.

    Args:
        bind: Address to bind (e.g. "0.0.0.0" or a ZeroTier IP).
        port: Port to listen on.
        command: Command and args to run in the terminal (e.g. ["pi", "--tui"]).
                 Caller must pass this; no default.

    Raises:
        RuntimeError: If ttyd is not found on PATH.
    """
    if command is None:
        command = []
    ttyd_path = shutil.which("ttyd")
    if not ttyd_path:
        raise RuntimeError(
            "ttyd not found. Install it to use remote web terminal.\n"
            "  macOS:   brew install ttyd\n"
            "  Linux:   see https://github.com/tsl0922/ttyd#installation\n"
            "  Windows: choco install ttyd (or download from GitHub releases)"
        )
    argv = [ttyd_path, "-b", bind, "-p", str(port)] + command
    proc = subprocess.Popen(argv)
    try:

        def sigint_handler(_signum: int, _frame: object) -> None:
            proc.terminate()

        signal.signal(signal.SIGINT, sigint_handler)
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait()
    finally:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    if proc.returncode and proc.returncode != 0:
        sys.exit(proc.returncode)

"""CLI for basket-capture: record TUI sessions to asciinema v2 .cast files."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from basket_capture.recorder import record as recorder_record
from basket_capture.session_bundle import (
    SessionBundleWriter,
    create_session_bundle,
    default_sessions_parent,
)


def resolve_record_output_path(
    output: Path | None,
    *,
    home: Path | None = None,
    now: datetime | None = None,
) -> Path:
    """
    Default: ~/.basket/capture/capture-YYYYMMDD-HHMMSS.cast (directory created if needed).

    If ``output`` is a path ending in ``.cast``, use that file (parent dirs created).
    Otherwise treat ``output`` as a directory and write capture-<timestamp>.cast inside it.
    """
    root = Path.home() if home is None else home
    ts = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    filename = f"capture-{ts}.cast"

    if output is None:
        out_dir = root / ".basket" / "capture"
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / filename

    out = output.expanduser()
    if out.suffix.lower() == ".cast":
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    out.mkdir(parents=True, exist_ok=True)
    return out / filename


def resolve_sessions_parent(
    output: Path | None,
    *,
    home: Path | None = None,
) -> Path:
    """Parent directory for bundle mode session-* folders."""
    if output is None:
        return default_sessions_parent(home)
    p = output.expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _parse_byte(s: str) -> int:
    return int(s, 0)


def _cmd_record(
    command: str,
    output_path: Path,
    timeout: float | None,
    *,
    bundle: SessionBundleWriter | None,
    action_boundary_byte: int,
    forward_action_boundary: bool,
    screenshot_cmd: str | None,
) -> None:
    """Record command to .cast file (and optional session bundle)."""
    try:
        recorder_record(
            command,
            output_path,
            timeout=timeout,
            bundle=bundle,
            action_boundary_byte=action_boundary_byte,
            forward_action_boundary=forward_action_boundary,
            screenshot_cmd=screenshot_cmd,
        )
    except OSError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise SystemExit(2) from e

    print(f"Cast written to {output_path}", file=sys.stderr)
    if bundle is not None:
        root = getattr(bundle, "root", None)
        if root is not None:
            print(f"Session bundle: {root}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="basket-capture",
        description="Record TUI terminal sessions to asciinema v2 .cast files.",
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    rec = subparsers.add_parser("record", help="Record a command in a PTY to a .cast file")
    rec.add_argument(
        "--command",
        default="bash",
        dest="record_command",
        help="Command to run (default: bash)",
    )
    rec.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Without --bundle: .cast file or directory for capture-*.cast "
            "(default ~/.basket/capture/). With --bundle: parent directory for "
            "session-* folders (default ~/.basket/capture/sessions/)."
        ),
    )
    rec.add_argument(
        "--timeout",
        type=float,
        default=None,
        metavar="SECS",
        help="Max recording time in seconds (default: until process exits)",
    )
    rec.add_argument(
        "--bundle",
        action="store_true",
        help=(
            "Write a session bundle: session.cast, input.jsonl, actions/*/meta.json, "
            "session_manifest.json under ~/.basket/capture/sessions/session-TIMESTAMP/ "
            "(or under --output when combined with --bundle)."
        ),
    )
    rec.add_argument(
        "--forward-action-boundary",
        action="store_true",
        help=(
            "Forward the action-boundary byte to the child PTY (default: consume "
            "Ctrl+\\ / 0x1C so the TUI does not see it)."
        ),
    )
    rec.add_argument(
        "--action-boundary-byte",
        type=_parse_byte,
        default=0x1C,
        metavar="N",
        help="Byte that ends an action segment (default: 0x1C = Ctrl+\\).",
    )
    rec.add_argument(
        "--screenshot-cmd",
        default=None,
        metavar="CMD",
        help=(
            "Shell command run at each action end; {out_path} is replaced with the "
            "PNG path (e.g. a script that captures the terminal window)."
        ),
    )

    args = parser.parse_args()

    if args.action == "record":
        if args.bundle:
            parent = resolve_sessions_parent(args.output, home=None)
            bundle = create_session_bundle(parent)
            out = bundle.cast_path
            _cmd_record(
                command=args.record_command,
                output_path=out,
                timeout=args.timeout,
                bundle=bundle,
                action_boundary_byte=args.action_boundary_byte,
                forward_action_boundary=args.forward_action_boundary,
                screenshot_cmd=args.screenshot_cmd,
            )
        else:
            out = resolve_record_output_path(args.output)
            _cmd_record(
                command=args.record_command,
                output_path=out,
                timeout=args.timeout,
                bundle=None,
                action_boundary_byte=args.action_boundary_byte,
                forward_action_boundary=False,
                screenshot_cmd=None,
            )
        return

    parser.error("Unknown subcommand")


if __name__ == "__main__":
    main()

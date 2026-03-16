"""CLI for basket-capture: record TUI sessions and generate PRD from .cast files."""

import argparse
import sys
from pathlib import Path

from basket_capture.cast import parse_cast
from basket_capture.layout import infer_regions
from basket_capture.interactions import detect_interactions
from basket_capture.renderer import AnalysisResult, render_prd
from basket_capture.recorder import record as recorder_record


def _cmd_generate_prd(cast_path: Path, output_path: Path | None) -> None:
    """Run generate-prd pipeline: parse_cast → infer_regions → detect_interactions → render_prd."""
    try:
        cast_result = parse_cast(cast_path)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise SystemExit(1) from e

    regions = infer_regions(cast_result)
    interactions = detect_interactions(cast_result)
    analysis = AnalysisResult(
        layout=regions,
        interactions=interactions,
        screenshots=[],
    )
    out = output_path or (cast_path.parent / f"{cast_path.stem}_prd.md")
    try:
        render_prd(analysis, out)
    except OSError as e:
        print(f"Error: cannot write output to {out}: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    except PermissionError as e:
        print(f"Error: output path not writable: {out}: {e}", file=sys.stderr)
        raise SystemExit(1) from e

    print(f"PRD written to {out}", file=sys.stderr)


def _cmd_record(
    command: str,
    output_path: Path,
    auto_generate: bool,
    timeout: float | None,
) -> None:
    """Record command to .cast; optionally run generate-prd on the result."""
    try:
        recorder_record(command, output_path, timeout=timeout)
    except OSError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise SystemExit(1) from e

    print(f"Cast written to {output_path}", file=sys.stderr)
    if auto_generate:
        _cmd_generate_prd(output_path, None)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="basket-capture",
        description="Record TUI terminal sessions to .cast and generate PRD from cast files.",
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    # record
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
        required=True,
        help="Output .cast file path",
    )
    rec.add_argument(
        "--auto-generate",
        action="store_true",
        help="After recording, run generate-prd on the new cast and write PRD next to it",
    )
    rec.add_argument(
        "--timeout",
        type=float,
        default=None,
        metavar="SECS",
        help="Max recording time in seconds (default: until process exits)",
    )

    # generate-prd
    gen = subparsers.add_parser(
        "generate-prd",
        help="Parse a .cast file and render a PRD Markdown file",
    )
    gen.add_argument(
        "--cast",
        type=Path,
        required=True,
        help="Input .cast file path",
    )
    gen.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="PATH",
        help="Output PRD path (default: same dir as cast, <cast_stem>_prd.md)",
    )

    args = parser.parse_args()

    if args.action == "record":
        _cmd_record(
            command=args.record_command,
            output_path=args.output,
            auto_generate=args.auto_generate,
            timeout=args.timeout,
        )
        return
    if args.action == "generate-prd":
        _cmd_generate_prd(args.cast, args.output)
        return

    parser.error("Unknown subcommand")


if __name__ == "__main__":
    main()

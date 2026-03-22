"""CLI argument parsing for the Basket assistant.

Extracts raw argv into a structured ParsedArgs dataclass without
using argparse — keeps the manual flag-popping approach from the
original main.py so that positional messages pass through unchanged.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ParsedArgs:
    """Immutable container for parsed CLI arguments."""

    command: str  # "help", "version", "init", "agent", "gateway", "remote",
    #               "relay", "tui", "tui-native", "interactive", "once"
    debug: bool = False
    plan_mode: bool = False
    session_id: Optional[str] = None
    tui_agent: Optional[str] = None
    tui_max_cols: Optional[int] = None
    tui_live_rows: Optional[int] = None
    remote_bind: str = "0.0.0.0"
    remote_port: int = 7681
    remaining_args: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers — each pops its flags from *args* and returns the value
# ---------------------------------------------------------------------------


def _pop_flag(args: list[str], flag: str) -> tuple[list[str], bool]:
    """Remove a boolean flag from *args* and return (new_args, was_present)."""
    if flag in args:
        return [a for a in args if a != flag], True
    return args, False


def _pop_valued(args: list[str], flag: str) -> tuple[list[str], Optional[str]]:
    """Remove ``flag <value>`` pair from *args*; return (new_args, value|None)."""
    if flag not in args:
        return args, None
    i = args.index(flag)
    if i + 1 < len(args):
        value = args[i + 1]
        return args[:i] + args[i + 2 :], value
    # Flag present but no value — just strip the flag
    return args[:i] + args[i + 1 :], None


def _pop_int_valued(args: list[str], flag: str) -> tuple[list[str], Optional[int]]:
    """Like :func:`_pop_valued` but coerces to int (returns None on failure)."""
    args, raw = _pop_valued(args, flag)
    if raw is None:
        return args, None
    try:
        return args, int(raw)
    except ValueError:
        return args, None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[list[str]] = None) -> ParsedArgs:
    """Parse CLI arguments into :class:`ParsedArgs`.

    The function mirrors the manual flag-popping approach of the original
    ``main_async`` so that every existing invocation keeps working.
    """
    args = list(argv) if argv is not None else list(sys.argv[1:])

    # -- boolean flags -------------------------------------------------------
    args, debug = _pop_flag(args, "--debug")
    args, plan_mode = _pop_flag(args, "--plan")
    args, use_remote = _pop_flag(args, "--remote")

    # -- valued flags --------------------------------------------------------
    args, session_id = _pop_valued(args, "--session")

    # --permission-mode plan is an alias for --plan
    args, perm_mode = _pop_valued(args, "--permission-mode")
    if perm_mode == "plan":
        plan_mode = True

    # -- help / version (early exit commands) --------------------------------
    if "--help" in args or "-h" in args:
        return ParsedArgs(command="help", debug=debug)
    if "--version" in args or "-v" in args:
        return ParsedArgs(command="version", debug=debug)

    # -- subcommands that consume args[0] ------------------------------------
    use_tui = len(args) >= 1 and args[0] == "tui"
    use_tui_native = len(args) >= 1 and args[0] in ("tui-native", "tn")

    if use_tui or use_tui_native:
        tui_kind = args[0]
        args = args[1:]

        # TUI-specific flags
        args, tui_agent = _pop_valued(args, "--agent")
        if tui_agent is not None:
            tui_agent = tui_agent.strip() or None
        if tui_agent is None:
            tui_agent = os.environ.get("BASKET_AGENT") or None
        if tui_agent is not None:
            tui_agent = tui_agent.strip() or None
        args, tui_max_cols = _pop_int_valued(args, "--max-cols")
        args, tui_live_rows = _pop_int_valued(args, "--live-rows")

        return ParsedArgs(
            command="tui" if tui_kind == "tui" else "tui-native",
            debug=debug,
            plan_mode=plan_mode,
            session_id=session_id,
            tui_agent=tui_agent,
            tui_max_cols=tui_max_cols,
            tui_live_rows=tui_live_rows,
            remaining_args=args,
        )

    if len(args) >= 1 and args[0] == "init":
        return ParsedArgs(
            command="init",
            debug=debug,
            remaining_args=args[1:],
        )

    if len(args) >= 1 and args[0] == "agent":
        return ParsedArgs(
            command="agent",
            debug=debug,
            remaining_args=args[1:],
        )

    if len(args) >= 1 and args[0] == "gateway":
        return ParsedArgs(
            command="gateway",
            debug=debug,
            remaining_args=args[1:],
        )

    if len(args) >= 1 and args[0] == "relay":
        return ParsedArgs(
            command="relay",
            debug=debug,
            remaining_args=args[1:],
        )

    # -- remote mode (flag, not subcommand) ----------------------------------
    if use_remote:
        remote_bind = os.environ.get("BASKET_REMOTE_BIND", "0.0.0.0")
        remote_port = 7681
        try:
            remote_port = int(os.environ.get("BASKET_REMOTE_PORT", "7681"))
        except ValueError:
            pass
        args, bind_val = _pop_valued(args, "--bind")
        if bind_val is not None:
            remote_bind = bind_val
        args, port_val = _pop_int_valued(args, "--port")
        if port_val is not None:
            remote_port = port_val

        return ParsedArgs(
            command="remote",
            debug=debug,
            remote_bind=remote_bind,
            remote_port=remote_port,
            remaining_args=args,
        )

    # -- strip remote bind/port even outside remote mode (compat) ------------
    args, _ = _pop_valued(args, "--bind")
    args, _ = _pop_int_valued(args, "--port")

    # -- interactive vs one-shot ---------------------------------------------
    command = "interactive" if len(args) == 0 else "once"

    return ParsedArgs(
        command=command,
        debug=debug,
        plan_mode=plan_mode,
        session_id=session_id,
        remaining_args=args,
    )

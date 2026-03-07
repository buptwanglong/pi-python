"""CLI entry: basket [--agent NAME] ..."""

from __future__ import annotations

import os
import sys


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    agent_name: str | None = None
    rest: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--agent" and i + 1 < len(argv):
            agent_name = argv[i + 1]
            i += 2
            continue
        if argv[i].startswith("--agent="):
            agent_name = argv[i].split("=", 1)[1]
            i += 1
            continue
        rest.append(argv[i])
        i += 1
    if agent_name is not None:
        os.environ["BASKET_AGENT"] = agent_name
    # Forward to package __main__ (repl/chat); agent code reads BASKET_AGENT for LLM config
    import runpy

    sys.argv = [sys.argv[0]] + rest
    runpy.run_module("basket_assistant", run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""python -m basket_assistant [--agent NAME] : run with optional agent (main agent when omitted)."""

from __future__ import annotations

import os
import sys


def _parse_agent(argv: list[str]) -> tuple[str | None, list[str]]:
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
    return agent_name, rest


def main() -> None:
    argv = sys.argv[1:]
    agent_name, rest = _parse_agent(argv)
    if agent_name is not None:
        os.environ["BASKET_AGENT"] = agent_name
    sys.argv = [sys.argv[0]] + rest
    # Delegate to agent package main (repl/chat)
    import basket_assistant.agent as agent_mod

    fn = getattr(agent_mod, "main", None) or getattr(agent_mod, "run", None)
    if fn is None:
        raise RuntimeError("basket_assistant.agent has no main() or run()")
    fn()


if __name__ == "__main__":
    main()

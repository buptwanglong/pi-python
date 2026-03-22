"""``basket agent list|add|remove`` — manage subagents in settings.json."""

from __future__ import annotations

from .parser import ParsedArgs


async def run(parsed: ParsedArgs) -> int:
    """Run the ``basket agent`` subcommand tree."""
    from ..core.configuration import (
        ConfigurationManager,
        AgentExistsError,
        AgentNotFoundError,
        CannotRemoveDefaultAgentError,
    )
    from ..core.configuration.validation import ValidationError

    rest = list(parsed.remaining_args)

    # -- help ----------------------------------------------------------------
    if len(rest) == 0 or rest[0] in ("--help", "-h"):
        _print_usage()
        return 0

    sub = rest[0]
    rest = rest[1:]

    # -- optional --path <file> ---------------------------------------------
    path_arg = None
    if "--path" in rest:
        i = rest.index("--path")
        if i + 1 < len(rest):
            path_arg = rest[i + 1]
            rest = rest[:i] + rest[i + 2 :]
        else:
            rest = rest[:i] + rest[i + 1 :]

    manager = ConfigurationManager(path_arg)

    if sub == "list":
        return _handle_list(manager)

    if sub == "remove":
        return _handle_remove(manager, rest)

    if sub == "add":
        return _handle_add(manager, rest)

    _print_usage()
    return 1


# ---------------------------------------------------------------------------
# Sub-handlers
# ---------------------------------------------------------------------------


def _print_usage() -> None:
    print("Usage: basket agent <list|add|remove> [options]")
    print("  list              List subagents in settings.json")
    print("  add               Add a subagent (--name; optional --tools, --force)")
    print("  remove <name>     Remove a subagent")
    print(
        "  --path <file>     Use given settings file "
        "(default: BASKET_SETTINGS_PATH or ~/.basket/settings.json)"
    )


def _handle_list(manager) -> int:
    agents = manager.list_agents()
    if not agents:
        print("No subagents configured.")
        return 0
    for a in agents:
        ws = a.workspace_dir or "(workspace)"
        print(f"{a.name}\t{ws}")
    return 0


def _handle_remove(manager, rest: list[str]) -> int:
    from ..core.configuration import AgentNotFoundError, CannotRemoveDefaultAgentError

    if not rest:
        print("Usage: basket agent remove <name>")
        return 1
    try:
        manager.remove_agent(rest[0])
        print(f"Removed subagent {rest[0]!r}.")
        return 0
    except AgentNotFoundError:
        print(f"Subagent {rest[0]!r} not found.")
        return 1
    except CannotRemoveDefaultAgentError:
        print(f"Cannot remove default agent {rest[0]!r}.")
        return 1


def _handle_add(manager, rest: list[str]) -> int:
    from ..core.configuration import AgentExistsError
    from ..core.configuration.validation import ValidationError

    force = "--force" in rest
    rest = [a for a in rest if a != "--force"]

    name = None
    tools_s = None
    i = 0
    while i < len(rest):
        if rest[i] == "--name" and i + 1 < len(rest):
            name = rest[i + 1]
            rest = rest[:i] + rest[i + 2 :]
            continue
        if rest[i] == "--tools" and i + 1 < len(rest):
            tools_s = rest[i + 1]
            rest = rest[:i] + rest[i + 2 :]
            continue
        i += 1

    if not name:
        try:
            name = input("Subagent name: ").strip()
        except EOFError:
            return 1
        if not name:
            print("Name is required.")
            return 1

    tools_dict = None
    if tools_s:
        tools_dict = {t.strip(): True for t in tools_s.split(",") if t.strip()}

    try:
        manager.add_agent(name=name, tools=tools_dict, force=force)
        print(f"Added subagent {name!r}.")
        return 0
    except ValidationError as e:
        print(f"Validation error: {e}")
        return 1
    except AgentExistsError:
        if not force:
            try:
                answer = (
                    input(f"Subagent {name!r} already exists. Overwrite? [y/N]: ")
                    .strip()
                    .lower()
                )
            except EOFError:
                return 1
            if answer in ("y", "yes"):
                manager.add_agent(name=name, tools=tools_dict, force=True)
                print(f"Added subagent {name!r}.")
                return 0
        print("Aborted.")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1

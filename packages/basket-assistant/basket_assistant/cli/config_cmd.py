"""``basket init`` — guided setup (create or overwrite settings.json)."""

from __future__ import annotations

import asyncio

from .parser import ParsedArgs


async def run(parsed: ParsedArgs) -> int:
    """Run the ``basket init`` command.

    Delegates to :class:`ConfigurationManager.run_guided_init`.
    """
    rest = list(parsed.remaining_args)
    force = "--force" in rest
    rest = [a for a in rest if a != "--force"]

    path_arg = None
    if "--path" in rest:
        i = rest.index("--path")
        if i + 1 < len(rest):
            path_arg = rest[i + 1]
            rest = rest[:i] + rest[i + 2 :]
        else:
            rest = rest[:i] + rest[i + 1 :]

    def _do_init() -> int:
        from ..core.configuration import ConfigurationManager

        manager = ConfigurationManager(path_arg)
        manager.run_guided_init(force=force)
        print(f"\nSettings written to {manager.config_path}. You can run 'basket gateway start' to start.")
        return 0

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _do_init)

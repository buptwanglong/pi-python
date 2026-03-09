"""
CLI for managing subagents (Task tool): basket agent list | add | remove.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _default_settings_path() -> Path:
    env = os.environ.get("BASKET_SETTINGS_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return (Path.home() / ".basket" / "settings.json").resolve()


def load_settings_raw(settings_path: Path | str | None = None) -> dict[str, Any]:
    """Load settings.json as raw dict; return {} with agents key if file missing."""
    path = Path(settings_path) if settings_path else _default_settings_path()
    if not path.exists():
        return {"agents": {}}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {"agents": {}}
    return data


def save_settings_raw(data: dict[str, Any], settings_path: Path | str | None = None) -> None:
    """Write settings.json; create parent dir if needed."""
    path = Path(settings_path) if settings_path else _default_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def run_list(settings_path: Path | str | None = None) -> int:
    """List subagents from settings.json agents. Returns 0."""
    data = load_settings_raw(settings_path)
    agents = data.get("agents") or {}
    if not isinstance(agents, dict):
        agents = {}
    if not agents:
        print("No subagents configured.")
        return 0
    for name, cfg in sorted(agents.items()):
        if not isinstance(cfg, dict):
            continue
        desc = (cfg.get("description") or "").strip() or "(no description)"
        print(f"{name}\t{desc}")
    return 0


def run_add(
    name: str,
    description: str,
    prompt: str,
    tools_dict: dict[str, bool] | None = None,
    force: bool = False,
    settings_path: Path | str | None = None,
) -> int:
    """Add a subagent to settings.agents. Returns 0 on success, 1 on abort/error."""
    path = Path(settings_path) if settings_path else _default_settings_path()
    data = load_settings_raw(settings_path)
    agents = data.setdefault("agents", {})
    if not isinstance(agents, dict):
        agents = {}
        data["agents"] = agents
    if name in agents and not force:
        try:
            answer = input(f"Subagent {name!r} already exists. Overwrite? [y/N]: ").strip().lower()
        except EOFError:
            return 1
        if answer not in ("y", "yes"):
            print("Aborted.")
            return 1
    entry: dict[str, Any] = {
        "description": description.strip(),
        "prompt": prompt.strip(),
    }
    if tools_dict:
        entry["tools"] = tools_dict
    agents[name] = entry
    save_settings_raw(data, settings_path)
    print(f"Added subagent {name!r}.")
    return 0


def run_remove(name: str, settings_path: Path | str | None = None) -> int:
    """Remove a subagent from settings.agents. Returns 0 on success, 1 if not found."""
    data = load_settings_raw(settings_path)
    agents = data.get("agents") or {}
    if not isinstance(agents, dict):
        agents = {}
        data["agents"] = agents
    if name not in agents:
        print(f"Subagent {name!r} not found.")
        return 1
    del agents[name]
    save_settings_raw(data, settings_path)
    print(f"Removed subagent {name!r}.")
    return 0


def parse_tools(s: str) -> dict[str, bool]:
    """Parse comma-separated tool names into { name: True, ... }."""
    if not s or not s.strip():
        return {}
    return {t.strip(): True for t in s.split(",") if t.strip()}

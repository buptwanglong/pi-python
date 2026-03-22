"""Plugin loader: discover installed plugins and aggregate their content.

Scans ~/.basket/plugins/ for plugin directories and collects their
skills, hooks, commands, and agents into the existing loader pipelines.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .manifest import PluginManifest, load_plugin_manifest, validate_plugin_dir

logger = logging.getLogger(__name__)

DEFAULT_PLUGINS_DIR = "~/.basket/plugins"


@dataclass(frozen=True)
class DiscoveredPlugin:
    """A discovered plugin with its manifest and directory path."""

    name: str
    version: str
    description: str
    path: Path


class PluginLoader:
    """Discover installed plugins and aggregate their content.

    Scans a plugins directory for sub-directories, validates each,
    and provides methods to collect skill dirs, hook defs, command dirs,
    and agent dirs from all valid plugins.
    """

    def __init__(self, plugins_dir: Optional[Path] = None):
        self._plugins_dir = (
            plugins_dir
            if plugins_dir is not None
            else Path(DEFAULT_PLUGINS_DIR).expanduser().resolve()
        )
        self._discovered: Optional[List[DiscoveredPlugin]] = None

    def discover(self) -> List[DiscoveredPlugin]:
        """Discover all valid plugins in the plugins directory.

        Returns a list of DiscoveredPlugin, sorted by name.
        Invalid (empty) plugin directories are skipped with a warning.
        """
        if not self._plugins_dir.exists() or not self._plugins_dir.is_dir():
            return []

        plugins: List[DiscoveredPlugin] = []
        for entry in sorted(self._plugins_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue

            errors = validate_plugin_dir(entry)
            if errors:
                logger.debug("Skipping invalid plugin %s: %s", entry.name, errors)
                continue

            manifest = load_plugin_manifest(entry)
            plugins.append(
                DiscoveredPlugin(
                    name=manifest.name,
                    version=manifest.version,
                    description=manifest.description,
                    path=entry,
                )
            )

        self._discovered = plugins
        return plugins

    def _ensure_discovered(self) -> List[DiscoveredPlugin]:
        if self._discovered is None:
            self.discover()
        return self._discovered or []

    def get_all_skill_dirs(self) -> List[Path]:
        """Return skill parent directories from all plugins.

        Each plugin's skills/ directory is returned (if it exists and is non-empty).
        These are appended after ~/.basket/skills and cwd/.basket/skills.
        """
        dirs: List[Path] = []
        for plugin in self._ensure_discovered():
            skills_dir = plugin.path / "skills"
            if skills_dir.is_dir() and any(skills_dir.iterdir()):
                dirs.append(skills_dir)
        return dirs

    def get_all_hook_defs(self) -> Dict[str, List[Dict[str, Any]]]:
        """Return merged hook definitions from all plugin hooks.json files.

        Returns event_name -> list of hook def dicts, ready to merge
        for optional merging into hook configuration.
        """
        merged: Dict[str, List[Dict[str, Any]]] = {}
        for plugin in self._ensure_discovered():
            hooks_file = plugin.path / "hooks.json"
            if not hooks_file.is_file():
                continue
            try:
                data = json.loads(hooks_file.read_text(encoding="utf-8"))
                hooks = data.get("hooks", {})
                if not isinstance(hooks, dict):
                    continue
                for event_name, defs in hooks.items():
                    if not isinstance(defs, list):
                        continue
                    if event_name not in merged:
                        merged[event_name] = []
                    merged[event_name].extend(
                        d for d in defs if isinstance(d, dict) and d.get("command")
                    )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(
                    "Failed to load hooks from plugin %s: %s", plugin.name, e
                )
        return merged

    def get_all_commands_dirs(self) -> List[Path]:
        """Return commands directories from all plugins (declarative *.md slash commands)."""
        dirs: List[Path] = []
        for plugin in self._ensure_discovered():
            cmd_dir = plugin.path / "commands"
            if cmd_dir.is_dir() and any(cmd_dir.iterdir()):
                dirs.append(cmd_dir)
        return dirs

    def get_all_agent_dirs(self) -> List[Path]:
        """Return agent directories from all plugins."""
        dirs: List[Path] = []
        for plugin in self._ensure_discovered():
            agent_dir = plugin.path / "agents"
            if agent_dir.is_dir() and any(agent_dir.iterdir()):
                dirs.append(agent_dir)
        return dirs

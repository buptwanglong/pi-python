"""Plugin CLI commands: install, uninstall, list.

Install copies a plugin directory into ~/.basket/plugins/.
Uninstall removes a plugin directory.
List shows all installed plugins with their metadata.
"""

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .loader import DiscoveredPlugin, PluginLoader
from .manifest import load_plugin_manifest, validate_plugin_dir

logger = logging.getLogger(__name__)

DEFAULT_PLUGINS_DIR = "~/.basket/plugins"


@dataclass(frozen=True)
class PluginCommandResult:
    """Result of a plugin command (immutable)."""

    success: bool
    message: str = ""
    error: str = ""
    plugins: List[DiscoveredPlugin] = field(default_factory=list)


def _resolve_plugins_dir(plugins_dir: Optional[Path] = None) -> Path:
    if plugins_dir is not None:
        return plugins_dir
    return Path(DEFAULT_PLUGINS_DIR).expanduser().resolve()


async def plugin_install(
    source: str,
    plugins_dir: Optional[Path] = None,
) -> PluginCommandResult:
    """Install a plugin from a local directory path.

    Copies the source directory into plugins_dir/<plugin-name>/.
    Validates the source before copying.
    """
    target_root = _resolve_plugins_dir(plugins_dir)
    target_root.mkdir(parents=True, exist_ok=True)

    source_path = Path(source).expanduser().resolve()
    if not source_path.is_dir():
        return PluginCommandResult(
            success=False,
            error=f"Source is not a directory: {source}",
        )

    errors = validate_plugin_dir(source_path)
    if errors:
        return PluginCommandResult(
            success=False,
            error="; ".join(errors),
        )

    manifest = load_plugin_manifest(source_path)
    target_dir = target_root / manifest.name

    if target_dir.exists():
        shutil.rmtree(target_dir)

    shutil.copytree(source_path, target_dir)

    return PluginCommandResult(
        success=True,
        message=f"Installed plugin '{manifest.name}' v{manifest.version} to {target_dir}",
    )


async def plugin_uninstall(
    name: str,
    plugins_dir: Optional[Path] = None,
) -> PluginCommandResult:
    """Uninstall a plugin by name.

    Removes the plugin directory from plugins_dir.
    """
    target_root = _resolve_plugins_dir(plugins_dir)
    plugin_dir = target_root / name

    if not plugin_dir.exists():
        return PluginCommandResult(
            success=False,
            error=f"Plugin not found: {name}",
        )

    shutil.rmtree(plugin_dir)

    return PluginCommandResult(
        success=True,
        message=f"Uninstalled plugin '{name}'",
    )


async def plugin_list(
    plugins_dir: Optional[Path] = None,
) -> PluginCommandResult:
    """List all installed plugins."""
    target_root = _resolve_plugins_dir(plugins_dir)
    loader = PluginLoader(plugins_dir=target_root)
    plugins = loader.discover()

    return PluginCommandResult(
        success=True,
        plugins=plugins,
        message=f"{len(plugins)} plugin(s) installed",
    )

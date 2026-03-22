"""Plugin CLI commands: install, uninstall, list.

Install copies a plugin directory into ~/.basket/plugins/.
Uninstall removes a plugin directory.
List shows all installed plugins with their metadata.
"""

import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, List, Optional

from .loader import DiscoveredPlugin, PluginLoader
from .manifest import load_plugin_manifest, validate_plugin_dir
from .source_fetch import (
    MaterializedPluginRoot,
    materialize_plugin_source,
    parse_install_source,
)

logger = logging.getLogger(__name__)

DEFAULT_PLUGINS_DIR = "~/.basket/plugins"

RESTART_HINT = (
    "请重启 basket 以加载新插件的技能列表与斜杠命令。"
)


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
    *,
    progress_sink: Optional[Callable[[dict], Awaitable[None]]] = None,
) -> PluginCommandResult:
    """Install a plugin from a local directory, zip/tar file, https archive URL, or git URL.

    Copies the plugin tree into plugins_dir/<plugin-name>/.
    On success, message includes a restart hint for TUI/CLI.
    """
    target_root = _resolve_plugins_dir(plugins_dir)
    target_root.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    preview = source.strip()[:120] + ("…" if len(source.strip()) > 120 else "")

    async def _emit(payload: dict) -> None:
        if progress_sink is not None:
            await progress_sink(payload)

    await _emit(
        {
            "type": "plugin_install_progress",
            "phase": "started",
            "source_preview": preview,
        }
    )

    parsed, perr = parse_install_source(source)
    if parsed is None:
        elapsed = round(time.monotonic() - t0, 1)
        await _emit(
            {
                "type": "plugin_install_progress",
                "phase": "done",
                "success": False,
                "elapsed_seconds": elapsed,
                "message": perr or "Invalid source",
            }
        )
        return PluginCommandResult(success=False, error=perr or "Invalid source")

    materialized: Optional[MaterializedPluginRoot] = None
    try:
        if parsed.kind == "local_dir":
            source_path = Path(parsed.primary).resolve()
        else:
            mat, merr = await materialize_plugin_source(
                parsed, progress_sink=progress_sink
            )
            if merr or mat is None:
                elapsed = round(time.monotonic() - t0, 1)
                await _emit(
                    {
                        "type": "plugin_install_progress",
                        "phase": "done",
                        "success": False,
                        "elapsed_seconds": elapsed,
                        "message": merr or "Materialize failed",
                    }
                )
                return PluginCommandResult(
                    success=False,
                    error=merr or "Materialize failed",
                )
            materialized = mat
            source_path = mat.path

        errors = validate_plugin_dir(source_path)
        if errors:
            elapsed = round(time.monotonic() - t0, 1)
            err_text = "; ".join(errors)
            await _emit(
                {
                    "type": "plugin_install_progress",
                    "phase": "done",
                    "success": False,
                    "elapsed_seconds": elapsed,
                    "message": err_text,
                }
            )
            return PluginCommandResult(success=False, error=err_text)

        manifest = load_plugin_manifest(source_path)
        target_dir = target_root / manifest.name

        if target_dir.exists():
            shutil.rmtree(target_dir)

        shutil.copytree(source_path, target_dir)

        elapsed = round(time.monotonic() - t0, 1)
        msg = (
            f"Installed plugin '{manifest.name}' v{manifest.version} to {target_dir} "
            f"(took {elapsed}s). {RESTART_HINT}"
        )
        await _emit(
            {
                "type": "plugin_install_progress",
                "phase": "done",
                "success": True,
                "elapsed_seconds": elapsed,
                "message": msg,
            }
        )
        return PluginCommandResult(success=True, message=msg)
    finally:
        if materialized is not None:
            materialized.cleanup_tmp()


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

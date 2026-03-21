"""Plugin packaging system for basket-assistant."""

from .commands import PluginCommandResult, plugin_install, plugin_list, plugin_uninstall
from .loader import DiscoveredPlugin, PluginLoader
from .manifest import PluginManifest, load_plugin_manifest, validate_plugin_dir

__all__ = [
    "DiscoveredPlugin",
    "PluginCommandResult",
    "PluginLoader",
    "PluginManifest",
    "load_plugin_manifest",
    "plugin_install",
    "plugin_list",
    "plugin_uninstall",
    "validate_plugin_dir",
]

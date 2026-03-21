"""Plugin packaging system for basket-assistant."""

from .loader import DiscoveredPlugin, PluginLoader
from .manifest import PluginManifest, load_plugin_manifest, validate_plugin_dir

__all__ = [
    "DiscoveredPlugin",
    "PluginLoader",
    "PluginManifest",
    "load_plugin_manifest",
    "validate_plugin_dir",
]

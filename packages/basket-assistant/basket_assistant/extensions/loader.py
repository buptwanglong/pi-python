"""
Extension Loader

Dynamically loads and manages extensions for the coding agent.
Creates HookRunner from hooks.json and settings.hooks for subprocess-based hooks.
"""

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .api import ExtensionAPI
from .hook_runner import HookRunner

logger = logging.getLogger(__name__)


class ExtensionLoader:
    """
    Manages loading and lifecycle of extensions.

    Extensions are Python modules with a `setup(pi: ExtensionAPI)` function.
    Also creates and holds HookRunner for subprocess-based hooks (loaded from
    hooks.json and settings.hooks).
    """

    def __init__(self, agent):
        """
        Initialize the extension loader.

        Args:
            agent: The AssistantAgent instance
        """
        self._agent = agent
        project_root = Path.cwd()
        settings = getattr(agent, "settings", None)
        settings_hooks = getattr(settings, "hooks", None) if settings else None
        self._hook_runner = HookRunner(
            project_root=project_root,
            settings_hooks=settings_hooks or {},
        )
        self._api = ExtensionAPI(agent, self._hook_runner)
        self._loaded_extensions: Dict[str, Any] = {}

    @property
    def extension_api(self) -> ExtensionAPI:
        """Public access to the extension API (for tests and callers)."""
        return self._api

    @property
    def hook_runner(self) -> HookRunner:
        """Public access to the hook runner (for tool wrapper and session hooks)."""
        return self._hook_runner

    def load_extension(self, path: Path) -> bool:
        """
        Load an extension from a file path.

        Args:
            path: Path to the extension file (.py)

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            # Load module from file
            spec = importlib.util.spec_from_file_location(path.stem, path)
            if not spec or not spec.loader:
                print(f"❌ Failed to load extension: {path}")
                return False

            module = importlib.util.module_from_spec(spec)
            sys.modules[path.stem] = module
            spec.loader.exec_module(module)

            # Call setup function
            if not hasattr(module, "setup"):
                print(f"❌ Extension missing setup() function: {path}")
                return False

            module.setup(self._api)

            # Track loaded extension
            self._loaded_extensions[str(path)] = module

            logger.info("Extension loaded from path: %s", path.resolve())
            print(f"✅ Loaded extension: {path.stem}")
            return True

        except Exception as e:
            logger.warning("Error loading extension %s: %s", path, e)
            print(f"❌ Error loading extension {path}: {e}")
            return False

    def load_extensions_from_dir(self, directory: Path) -> int:
        """
        Load all extensions from a directory.

        Args:
            directory: Path to extensions directory

        Returns:
            Number of extensions loaded successfully
        """
        if not directory.exists() or not directory.is_dir():
            return 0

        loaded = 0
        for ext_file in directory.glob("*.py"):
            # Skip __init__.py and private files
            if ext_file.name.startswith("_"):
                continue

            if self.load_extension(ext_file):
                loaded += 1

        return loaded

    def load_default_extensions(self) -> int:
        """
        Load extensions from default locations.

        Searches:
        1. Package examples/extensions/ (bundled)
        2. ~/.basket/extensions/
        3. ./extensions/ (current directory)

        Returns:
            Total number of extensions loaded
        """
        total = 0

        # Package bundled examples (e.g. memory_extension)
        package_root = Path(__file__).resolve().parent.parent.parent
        examples_ext_dir = package_root / "examples" / "extensions"
        if examples_ext_dir.exists():
            total += self.load_extensions_from_dir(examples_ext_dir)

        # User extensions
        user_ext_dir = Path.home() / ".basket" / "extensions"
        if user_ext_dir.exists():
            total += self.load_extensions_from_dir(user_ext_dir)

        # Local extensions (cwd)
        local_ext_dir = Path.cwd() / "extensions"
        if local_ext_dir.exists():
            total += self.load_extensions_from_dir(local_ext_dir)

        return total

    def get_loaded_extensions(self) -> List[str]:
        """
        Get list of loaded extension paths.

        Returns:
            List of extension file paths
        """
        return list(self._loaded_extensions.keys())

    def get_api(self) -> ExtensionAPI:
        """
        Get the ExtensionAPI instance.

        Returns:
            The ExtensionAPI used by loaded extensions
        """
        return self._api


__all__ = ["ExtensionLoader"]

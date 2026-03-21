# Phase 3 Extensibility Alignment: Plugin Packaging Format

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Introduce a directory-based Plugin packaging format that bundles skills, hooks, extensions, and agents into a single distributable unit — aligning with Claude Code's plugin system. Add `basket plugin install/uninstall/list` CLI commands.

**Architecture:** A Plugin is a directory containing an optional `plugin.json` manifest plus any combination of `skills/`, `hooks.json`, `extensions/`, and `agents/` sub-directories. The `PluginLoader` scans `~/.basket/plugins/` for installed plugins and merges their content into the existing loader pipelines (skills → skills_loader, hooks → hook_runner, extensions → extension_loader, agents → agent loader). CLI commands copy/remove plugin directories. No code execution at install time.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest + pytest-asyncio

**Note:** MCP Client support (P0 gap #1) is excluded — it needs its own dedicated design phase.

---

### Task 1: Write failing tests for `plugin.json` manifest parsing

**Files:**
- Create: `packages/basket-assistant/tests/test_plugins.py`

**Step 1: Write the failing tests**

```python
"""Tests for Plugin packaging format — manifest parsing and directory structure."""

import json
import pytest
from pathlib import Path

from basket_assistant.plugins.manifest import (
    PluginManifest,
    load_plugin_manifest,
    validate_plugin_dir,
)


class TestPluginManifest:
    """Test plugin.json manifest parsing."""

    def test_load_manifest_minimal(self, tmp_path):
        """Test loading a minimal plugin.json."""
        manifest = {"name": "my-plugin", "version": "1.0.0"}
        (tmp_path / "plugin.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        result = load_plugin_manifest(tmp_path)

        assert result.name == "my-plugin"
        assert result.version == "1.0.0"
        assert result.description == ""
        assert result.author == ""

    def test_load_manifest_full(self, tmp_path):
        """Test loading a full plugin.json with all fields."""
        manifest = {
            "name": "my-plugin",
            "version": "2.1.0",
            "description": "A useful plugin",
            "author": "Test Author",
        }
        (tmp_path / "plugin.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        result = load_plugin_manifest(tmp_path)

        assert result.name == "my-plugin"
        assert result.version == "2.1.0"
        assert result.description == "A useful plugin"
        assert result.author == "Test Author"

    def test_load_manifest_missing_file(self, tmp_path):
        """Test loading when plugin.json doesn't exist — infer from dirname."""
        result = load_plugin_manifest(tmp_path)

        assert result.name == tmp_path.name
        assert result.version == "0.0.0"

    def test_load_manifest_invalid_json(self, tmp_path):
        """Test loading invalid JSON returns fallback manifest."""
        (tmp_path / "plugin.json").write_text("not json", encoding="utf-8")

        result = load_plugin_manifest(tmp_path)

        assert result.name == tmp_path.name
        assert result.version == "0.0.0"

    def test_load_manifest_missing_name(self, tmp_path):
        """Test manifest without name falls back to dirname."""
        manifest = {"version": "1.0.0"}
        (tmp_path / "plugin.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        result = load_plugin_manifest(tmp_path)

        assert result.name == tmp_path.name

    def test_plugin_name_validation(self, tmp_path):
        """Test plugin name must match ^[a-z0-9]+(-[a-z0-9]+)*$ pattern."""
        manifest = {"name": "Invalid Name!", "version": "1.0.0"}
        (tmp_path / "plugin.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        result = load_plugin_manifest(tmp_path)

        # Should sanitize or reject; falls back to dirname
        assert result.name == tmp_path.name


class TestValidatePluginDir:
    """Test plugin directory structure validation."""

    def test_valid_plugin_with_skills(self, tmp_path):
        """Test valid plugin with skills/ directory."""
        skills_dir = tmp_path / "skills" / "my-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: A skill\n---\nContent",
            encoding="utf-8",
        )

        errors = validate_plugin_dir(tmp_path)
        assert errors == []

    def test_valid_plugin_with_hooks(self, tmp_path):
        """Test valid plugin with hooks.json."""
        (tmp_path / "hooks.json").write_text(
            json.dumps({
                "hooks": {
                    "PreToolUse": [{"command": "echo test"}]
                }
            }),
            encoding="utf-8",
        )

        errors = validate_plugin_dir(tmp_path)
        assert errors == []

    def test_valid_plugin_with_extensions(self, tmp_path):
        """Test valid plugin with extensions/ directory."""
        ext_dir = tmp_path / "extensions"
        ext_dir.mkdir()
        (ext_dir / "my_ext.py").write_text(
            "def setup(basket): pass", encoding="utf-8"
        )

        errors = validate_plugin_dir(tmp_path)
        assert errors == []

    def test_empty_plugin_returns_error(self, tmp_path):
        """Test empty directory returns validation error."""
        errors = validate_plugin_dir(tmp_path)
        assert len(errors) > 0
        assert any("empty" in e.lower() or "no content" in e.lower() for e in errors)

    def test_valid_plugin_with_agents(self, tmp_path):
        """Test valid plugin with agents/ directory."""
        agent_dir = tmp_path / "agents" / "my-agent"
        agent_dir.mkdir(parents=True)
        ws = agent_dir / "workspace"
        ws.mkdir()
        (ws / "AGENTS.md").write_text("You are a test agent.", encoding="utf-8")

        errors = validate_plugin_dir(tmp_path)
        assert errors == []
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_plugins.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'basket_assistant.plugins'`

**Step 3: Commit**

```bash
git add packages/basket-assistant/tests/test_plugins.py
git commit -m "test: add failing tests for plugin manifest parsing"
```

---

### Task 2: Implement plugin manifest module

**Files:**
- Create: `packages/basket-assistant/basket_assistant/plugins/__init__.py`
- Create: `packages/basket-assistant/basket_assistant/plugins/manifest.py`

**Step 1: Create `__init__.py`**

```python
"""Plugin packaging system for basket-assistant."""

from .manifest import PluginManifest, load_plugin_manifest, validate_plugin_dir

__all__ = ["PluginManifest", "load_plugin_manifest", "validate_plugin_dir"]
```

**Step 2: Create `manifest.py`**

```python
"""Plugin manifest parsing and directory validation.

A Plugin is a directory containing an optional plugin.json manifest plus
any combination of skills/, hooks.json, extensions/, and agents/ sub-dirs.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


@dataclass(frozen=True)
class PluginManifest:
    """Parsed plugin.json manifest (immutable)."""

    name: str
    version: str = "0.0.0"
    description: str = ""
    author: str = ""


def _sanitize_name(raw: str) -> Optional[str]:
    """Return raw if it matches the naming convention, else None."""
    if _NAME_RE.match(raw) and len(raw) <= 64:
        return raw
    return None


def load_plugin_manifest(plugin_dir: Path) -> PluginManifest:
    """Load plugin.json from a plugin directory.

    Falls back to directory name when plugin.json is missing or invalid.
    """
    fallback_name = _sanitize_name(plugin_dir.name) or plugin_dir.name.lower().replace(" ", "-")
    fallback = PluginManifest(name=fallback_name)

    manifest_path = plugin_dir / "plugin.json"
    if not manifest_path.exists():
        return fallback

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to parse plugin.json in %s: %s", plugin_dir, e)
        return fallback

    if not isinstance(data, dict):
        return fallback

    raw_name = data.get("name", "")
    name = _sanitize_name(str(raw_name)) if raw_name else None
    if not name:
        name = fallback_name

    return PluginManifest(
        name=name,
        version=str(data.get("version", "0.0.0")),
        description=str(data.get("description", "")),
        author=str(data.get("author", "")),
    )


def validate_plugin_dir(plugin_dir: Path) -> List[str]:
    """Validate a plugin directory structure.

    Returns a list of error messages (empty = valid).
    A valid plugin must contain at least one of:
    skills/, hooks.json, extensions/, agents/
    """
    errors: List[str] = []

    has_content = False

    skills_dir = plugin_dir / "skills"
    if skills_dir.is_dir() and any(skills_dir.iterdir()):
        has_content = True

    hooks_file = plugin_dir / "hooks.json"
    if hooks_file.is_file():
        has_content = True

    extensions_dir = plugin_dir / "extensions"
    if extensions_dir.is_dir() and any(extensions_dir.iterdir()):
        has_content = True

    agents_dir = plugin_dir / "agents"
    if agents_dir.is_dir() and any(agents_dir.iterdir()):
        has_content = True

    if not has_content:
        errors.append(
            "Plugin has no content: expected at least one of "
            "skills/, hooks.json, extensions/, agents/"
        )

    return errors
```

**Step 3: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_plugins.py -v`
Expected: All manifest tests PASS

**Step 4: Commit**

```bash
git add packages/basket-assistant/basket_assistant/plugins/
git commit -m "feat: add plugin manifest parsing and directory validation"
```

---

### Task 3: Write failing tests for PluginLoader

**Files:**
- Modify: `packages/basket-assistant/tests/test_plugins.py`

**Step 1: Add PluginLoader tests**

```python
from basket_assistant.plugins.loader import PluginLoader


class TestPluginLoader:
    """Test plugin discovery and content aggregation."""

    def test_discover_plugins_empty(self, tmp_path):
        """Test discovering plugins from empty directory."""
        loader = PluginLoader(plugins_dir=tmp_path)

        plugins = loader.discover()

        assert plugins == []

    def test_discover_plugins_finds_valid(self, tmp_path):
        """Test discovering valid plugins."""
        # Create a plugin with skills
        plugin_dir = tmp_path / "my-plugin"
        skill_dir = plugin_dir / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test-skill\ndescription: A test\n---\nBody",
            encoding="utf-8",
        )

        loader = PluginLoader(plugins_dir=tmp_path)
        plugins = loader.discover()

        assert len(plugins) == 1
        assert plugins[0].name == "my-plugin"

    def test_get_all_skill_dirs(self, tmp_path):
        """Test aggregating skill dirs from all plugins."""
        # Plugin 1
        p1 = tmp_path / "plugin-a" / "skills" / "skill-a"
        p1.mkdir(parents=True)
        (p1 / "SKILL.md").write_text(
            "---\nname: skill-a\ndescription: Skill A\n---\n", encoding="utf-8"
        )

        # Plugin 2
        p2 = tmp_path / "plugin-b" / "skills" / "skill-b"
        p2.mkdir(parents=True)
        (p2 / "SKILL.md").write_text(
            "---\nname: skill-b\ndescription: Skill B\n---\n", encoding="utf-8"
        )

        loader = PluginLoader(plugins_dir=tmp_path)
        skill_dirs = loader.get_all_skill_dirs()

        assert len(skill_dirs) == 2

    def test_get_all_hook_defs(self, tmp_path):
        """Test aggregating hook definitions from all plugins."""
        plugin_dir = tmp_path / "hook-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "hooks.json").write_text(
            json.dumps({
                "hooks": {
                    "PreToolUse": [{"command": "echo test"}]
                }
            }),
            encoding="utf-8",
        )

        loader = PluginLoader(plugins_dir=tmp_path)
        hook_defs = loader.get_all_hook_defs()

        assert "PreToolUse" in hook_defs or "tool.execute.before" in hook_defs

    def test_get_all_extension_dirs(self, tmp_path):
        """Test aggregating extension dirs from all plugins."""
        ext_dir = tmp_path / "ext-plugin" / "extensions"
        ext_dir.mkdir(parents=True)
        (ext_dir / "my_ext.py").write_text(
            "def setup(basket): pass", encoding="utf-8"
        )

        loader = PluginLoader(plugins_dir=tmp_path)
        ext_dirs = loader.get_all_extension_dirs()

        assert len(ext_dirs) == 1

    def test_get_all_agent_dirs(self, tmp_path):
        """Test aggregating agent dirs from all plugins."""
        agent_dir = tmp_path / "agent-plugin" / "agents" / "my-agent"
        agent_dir.mkdir(parents=True)
        ws = agent_dir / "workspace"
        ws.mkdir()
        (ws / "AGENTS.md").write_text("Agent config.", encoding="utf-8")

        loader = PluginLoader(plugins_dir=tmp_path)
        agent_dirs = loader.get_all_agent_dirs()

        assert len(agent_dirs) == 1

    def test_skip_invalid_plugins(self, tmp_path):
        """Test that invalid (empty) plugin dirs are skipped."""
        # Valid plugin
        valid = tmp_path / "valid-plugin" / "skills" / "s"
        valid.mkdir(parents=True)
        (valid / "SKILL.md").write_text(
            "---\nname: s\ndescription: S\n---\n", encoding="utf-8"
        )

        # Invalid (empty) plugin
        (tmp_path / "empty-plugin").mkdir()

        loader = PluginLoader(plugins_dir=tmp_path)
        plugins = loader.discover()

        assert len(plugins) == 1
        assert plugins[0].name == "valid-plugin"
```

**Step 2: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_plugins.py -v -k "Loader"`
Expected: FAIL — `ModuleNotFoundError: No module named 'basket_assistant.plugins.loader'`

**Step 3: Commit**

```bash
git add packages/basket-assistant/tests/test_plugins.py
git commit -m "test: add failing tests for PluginLoader discovery and aggregation"
```

---

### Task 4: Implement PluginLoader

**Files:**
- Create: `packages/basket-assistant/basket_assistant/plugins/loader.py`
- Modify: `packages/basket-assistant/basket_assistant/plugins/__init__.py`

**Step 1: Create `loader.py`**

```python
"""Plugin loader: discover installed plugins and aggregate their content.

Scans ~/.basket/plugins/ for plugin directories and collects their
skills, hooks, extensions, and agents into the existing loader pipelines.
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
    and provides methods to collect skill dirs, hook defs, extension dirs,
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
        These can be appended to the skills_dirs search path.
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
        into HookRunner via _merge_hook_defs.
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

    def get_all_extension_dirs(self) -> List[Path]:
        """Return extension directories from all plugins."""
        dirs: List[Path] = []
        for plugin in self._ensure_discovered():
            ext_dir = plugin.path / "extensions"
            if ext_dir.is_dir() and any(ext_dir.iterdir()):
                dirs.append(ext_dir)
        return dirs

    def get_all_agent_dirs(self) -> List[Path]:
        """Return agent directories from all plugins."""
        dirs: List[Path] = []
        for plugin in self._ensure_discovered():
            agent_dir = plugin.path / "agents"
            if agent_dir.is_dir() and any(agent_dir.iterdir()):
                dirs.append(agent_dir)
        return dirs
```

**Step 2: Update `__init__.py`**

```python
"""Plugin packaging system for basket-assistant."""

from .manifest import PluginManifest, load_plugin_manifest, validate_plugin_dir
from .loader import PluginLoader, DiscoveredPlugin

__all__ = [
    "PluginManifest",
    "load_plugin_manifest",
    "validate_plugin_dir",
    "PluginLoader",
    "DiscoveredPlugin",
]
```

**Step 3: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_plugins.py -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add packages/basket-assistant/basket_assistant/plugins/
git commit -m "feat: add PluginLoader for discovering and aggregating plugin content"
```

---

### Task 5: Write failing tests for `basket plugin` CLI commands

**Files:**
- Modify: `packages/basket-assistant/tests/test_plugins.py`

**Step 1: Add CLI command tests**

```python
from basket_assistant.plugins.commands import (
    plugin_install,
    plugin_uninstall,
    plugin_list,
)


class TestPluginCommands:
    """Test basket plugin install/uninstall/list commands."""

    @pytest.mark.asyncio
    async def test_plugin_list_empty(self, tmp_path):
        """Test listing plugins when none installed."""
        result = await plugin_list(plugins_dir=tmp_path)

        assert result.success is True
        assert result.plugins == []

    @pytest.mark.asyncio
    async def test_plugin_install_from_local_dir(self, tmp_path):
        """Test installing a plugin from a local directory."""
        # Source plugin
        source = tmp_path / "source" / "my-plugin"
        skill_dir = source / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: Test\n---\nBody",
            encoding="utf-8",
        )
        manifest = {"name": "my-plugin", "version": "1.0.0"}
        (source / "plugin.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        # Target plugins dir
        target = tmp_path / "plugins"
        target.mkdir()

        result = await plugin_install(source=str(source), plugins_dir=target)

        assert result.success is True
        assert (target / "my-plugin").is_dir()
        assert (target / "my-plugin" / "skills" / "my-skill" / "SKILL.md").is_file()

    @pytest.mark.asyncio
    async def test_plugin_install_rejects_empty(self, tmp_path):
        """Test that installing an empty directory fails."""
        source = tmp_path / "empty"
        source.mkdir()
        target = tmp_path / "plugins"
        target.mkdir()

        result = await plugin_install(source=str(source), plugins_dir=target)

        assert result.success is False
        assert "no content" in result.error.lower() or "empty" in result.error.lower()

    @pytest.mark.asyncio
    async def test_plugin_uninstall(self, tmp_path):
        """Test uninstalling a plugin."""
        # Install a plugin first
        plugin_dir = tmp_path / "my-plugin"
        skills = plugin_dir / "skills" / "s"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text(
            "---\nname: s\ndescription: S\n---\n", encoding="utf-8"
        )

        result = await plugin_uninstall(name="my-plugin", plugins_dir=tmp_path)

        assert result.success is True
        assert not plugin_dir.exists()

    @pytest.mark.asyncio
    async def test_plugin_uninstall_not_found(self, tmp_path):
        """Test uninstalling non-existent plugin."""
        result = await plugin_uninstall(name="not-found", plugins_dir=tmp_path)

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_plugin_list_shows_installed(self, tmp_path):
        """Test listing shows installed plugins."""
        # Create installed plugin
        plugin_dir = tmp_path / "test-plugin"
        skills = plugin_dir / "skills" / "s"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text(
            "---\nname: s\ndescription: S\n---\n", encoding="utf-8"
        )
        manifest = {"name": "test-plugin", "version": "2.0.0", "description": "Test"}
        (plugin_dir / "plugin.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        result = await plugin_list(plugins_dir=tmp_path)

        assert result.success is True
        assert len(result.plugins) == 1
        assert result.plugins[0].name == "test-plugin"
        assert result.plugins[0].version == "2.0.0"
```

**Step 2: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_plugins.py -v -k "Commands"`
Expected: FAIL — `ModuleNotFoundError: No module named 'basket_assistant.plugins.commands'`

**Step 3: Commit**

```bash
git add packages/basket-assistant/tests/test_plugins.py
git commit -m "test: add failing tests for basket plugin CLI commands"
```

---

### Task 6: Implement plugin CLI commands

**Files:**
- Create: `packages/basket-assistant/basket_assistant/plugins/commands.py`
- Modify: `packages/basket-assistant/basket_assistant/plugins/__init__.py`

**Step 1: Create `commands.py`**

```python
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
```

**Step 2: Update `__init__.py`**

Add imports:
```python
from .commands import plugin_install, plugin_uninstall, plugin_list, PluginCommandResult
```

**Step 3: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_plugins.py -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add packages/basket-assistant/basket_assistant/plugins/
git commit -m "feat: add plugin install/uninstall/list CLI commands"
```

---

### Task 7: Register `/plugin` slash command

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/interaction/commands/handlers.py`
- Modify: `packages/basket-assistant/tests/interaction/commands/test_handlers.py`

**Step 1: Write failing test**

Add to `TestBuiltinCommandHandlers`:

```python
@pytest.mark.asyncio
async def test_handle_plugin_list(self):
    """Test /plugin list shows plugins."""
    agent = MockAgent()
    handlers = BuiltinCommandHandlers(agent)

    success, error = await handlers.handle_plugin("list")

    assert success is True
    assert error == ""

@pytest.mark.asyncio
async def test_handle_plugin_no_args(self):
    """Test /plugin with no args shows usage."""
    agent = MockAgent()
    handlers = BuiltinCommandHandlers(agent)

    success, error = await handlers.handle_plugin("")

    assert success is False
    assert "Usage:" in error
```

**Step 2: Add `handle_plugin` to BuiltinCommandHandlers**

```python
async def handle_plugin(self, args: str) -> tuple[bool, str]:
    """Handle /plugin command — manage installed plugins.

    Subcommands:
      /plugin list                    List installed plugins
      /plugin install <path>          Install plugin from local directory
      /plugin uninstall <name>        Uninstall a plugin by name
    """
    parts = args.strip().split(maxsplit=1)
    if not parts:
        return False, (
            "Usage: /plugin <list|install|uninstall>\n"
            "  /plugin list                  List installed plugins\n"
            "  /plugin install <path>        Install from local directory\n"
            "  /plugin uninstall <name>      Uninstall by name"
        )

    subcmd = parts[0].lower()
    subcmd_args = parts[1] if len(parts) > 1 else ""

    from basket_assistant.plugins.commands import (
        plugin_install,
        plugin_uninstall,
        plugin_list,
    )

    if subcmd == "list":
        result = await plugin_list()
        if not result.plugins:
            print("No plugins installed.")
        else:
            print(f"{len(result.plugins)} plugin(s) installed:")
            for p in result.plugins:
                desc = f" — {p.description}" if p.description else ""
                print(f"  {p.name} v{p.version}{desc}")
        return True, ""

    elif subcmd == "install":
        if not subcmd_args.strip():
            return False, "Usage: /plugin install <path>"
        result = await plugin_install(source=subcmd_args.strip())
        if result.success:
            print(result.message)
            return True, ""
        return False, result.error

    elif subcmd == "uninstall":
        if not subcmd_args.strip():
            return False, "Usage: /plugin uninstall <name>"
        result = await plugin_uninstall(name=subcmd_args.strip())
        if result.success:
            print(result.message)
            return True, ""
        return False, result.error

    else:
        return False, (
            f"Unknown subcommand: {subcmd}\n"
            "Usage: /plugin <list|install|uninstall>"
        )
```

**Step 3: Register in `register_builtin_commands`**

```python
# Register /plugin command
registry.register(
    name="plugin",
    handler=handlers.handle_plugin,
    description="Manage installed plugins",
    usage="/plugin <list|install|uninstall>",
    aliases=["plugin", "/plugin"],
)
```

**Step 4: Update /help text**

```
  /plugin <subcmd>    Manage plugins (list/install/uninstall)
```

**Step 5: Add registration assertions to `TestRegisterBuiltinCommands`**

```python
assert registry.get_command("plugin") is not None
assert registry.get_command("/plugin") is not None
```

**Step 6: Run tests**

Run: `cd packages/basket-assistant && poetry run pytest tests/interaction/commands/test_handlers.py tests/test_plugins.py -v`
Expected: All tests PASS

**Step 7: Commit**

```bash
git add packages/basket-assistant/basket_assistant/interaction/commands/handlers.py packages/basket-assistant/tests/interaction/commands/test_handlers.py
git commit -m "feat: add /plugin slash command for managing plugins"
```

---

### Task 8: Integrate PluginLoader into AssistantAgent startup

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/agent/__init__.py`
- Modify: `packages/basket-assistant/basket_assistant/agent/prompts.py`

**Step 1: Wire PluginLoader into AssistantAgent**

In `__init__.py`, add after extension loading (after line 69):

```python
# Load plugins and merge into search paths
from ..plugins.loader import PluginLoader
self._plugin_loader = PluginLoader()
self._plugin_loader.discover()
```

**Step 2: Merge plugin skill dirs into `get_skills_dirs`**

In `prompts.py`, modify `get_skills_dirs` to accept an optional `plugin_skill_dirs` parameter:

```python
def get_skills_dirs(settings: Any, plugin_skill_dirs: Optional[List[Path]] = None) -> List[Path]:
    """Resolve skills directories; default includes Basket, OpenCode, Claude, Agents, Plugin paths."""
    dirs = []
    if getattr(settings, "skills_dirs", None):
        dirs = [Path(d).expanduser().resolve() for d in settings.skills_dirs]
    else:
        dirs = [
            Path.home() / ".basket" / "skills",
            Path.cwd() / ".basket" / "skills",
            Path.home() / ".config" / "opencode" / "skills",
            Path.cwd() / ".opencode" / "skills",
            Path.home() / ".claude" / "skills",
            Path.cwd() / ".claude" / "skills",
            Path.home() / ".agents" / "skills",
            Path.cwd() / ".agents" / "skills",
        ]
    # Append plugin skill dirs
    if plugin_skill_dirs:
        dirs.extend(plugin_skill_dirs)
    return dirs
```

**Step 3: Merge plugin extension dirs into ExtensionLoader**

In `loader.py` `load_default_extensions`, add plugin extensions after local extensions:

```python
# Plugin extensions
if hasattr(agent, "_plugin_loader") and agent._plugin_loader:
    for ext_dir in agent._plugin_loader.get_all_extension_dirs():
        total += self.load_extensions_from_dir(ext_dir)
```

**Step 4: Run full test suite**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_plugins.py tests/interaction/commands/test_handlers.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add packages/basket-assistant/basket_assistant/agent/__init__.py packages/basket-assistant/basket_assistant/agent/prompts.py packages/basket-assistant/basket_assistant/extensions/loader.py
git commit -m "feat: integrate PluginLoader into agent startup pipeline"
```

---

### Task 9: Full test suite verification

**Files:** None (verification only)

**Step 1: Run all basket-assistant tests**

Run: `cd packages/basket-assistant && poetry run pytest -v --ignore=tests/test_tui_mode.py --ignore=tests/adapters/test_tui.py --ignore=tests/interaction/modes/test_tui_mode.py --ignore=tests/interaction/modes/test_attach_mode.py`
Expected: All tests PASS (pre-existing TUI failures excluded)

**Step 2: Verify plugin imports**

Run: `cd packages/basket-assistant && poetry run python -c "from basket_assistant.plugins import PluginManifest, PluginLoader, plugin_install, plugin_uninstall, plugin_list; print('All plugin imports OK')"`
Expected: `All plugin imports OK`

**Step 3: Final commit**

```bash
git add -A
git commit -m "chore: verify all tests pass after Phase 3 plugin packaging implementation"
```

---

## Summary of Changes

| File | Action | Description |
|------|--------|-------------|
| `plugins/__init__.py` | Create | Package init with exports |
| `plugins/manifest.py` | Create | `PluginManifest` dataclass, `load_plugin_manifest()`, `validate_plugin_dir()` |
| `plugins/loader.py` | Create | `PluginLoader` class — discover, aggregate skills/hooks/extensions/agents |
| `plugins/commands.py` | Create | `plugin_install()`, `plugin_uninstall()`, `plugin_list()` |
| `handlers.py` | Modify | Add `handle_plugin()` method + register `/plugin` command |
| `agent/__init__.py` | Modify | Wire `PluginLoader` into startup |
| `prompts.py` | Modify | Accept plugin skill dirs in `get_skills_dirs()` |
| `extensions/loader.py` | Modify | Load extensions from plugin dirs |
| `test_plugins.py` | Create | 18 tests for manifest, loader, and commands |
| `test_handlers.py` | Modify | 2 tests for `/plugin` command + registration |

**Total new tests:** ~20
**Total new production code:** ~350 lines (4 new modules + 3 modifications)
**Estimated effort:** ~60 minutes

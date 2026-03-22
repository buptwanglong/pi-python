"""Tests for Plugin packaging format — manifest parsing and directory structure."""

import json
import zipfile
import pytest
from pathlib import Path

from basket_assistant.plugins.manifest import (
    PluginManifest,
    load_plugin_manifest,
    validate_plugin_dir,
)
from basket_assistant.plugins.loader import PluginLoader
from basket_assistant.plugins.commands import (
    RESTART_HINT,
    plugin_install,
    plugin_list,
    plugin_uninstall,
)
from basket_assistant.plugins.source_fetch import parse_install_source


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

    def test_valid_plugin_with_commands(self, tmp_path):
        """Test valid plugin with commands/ directory (declarative slash *.md)."""
        cmd_dir = tmp_path / "commands"
        cmd_dir.mkdir()
        (cmd_dir / "hello.md").write_text(
            "---\ndescription: Hello\n---\nSay hi {{args}}", encoding="utf-8"
        )

        errors = validate_plugin_dir(tmp_path)
        assert errors == []

    def test_plugin_with_only_extensions_dir_is_invalid(self, tmp_path):
        """extensions/ alone is not valid plugin content (extension system removed)."""
        ext_dir = tmp_path / "extensions"
        ext_dir.mkdir()
        (ext_dir / "my_ext.py").write_text(
            "def setup(basket): pass", encoding="utf-8"
        )

        errors = validate_plugin_dir(tmp_path)
        assert len(errors) > 0

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

    def test_get_all_commands_dirs(self, tmp_path):
        """Test aggregating commands dirs from all plugins."""
        p = tmp_path / "cmd-plugin" / "commands"
        p.mkdir(parents=True)
        (p / "foo.md").write_text(
            "---\ndescription: Foo\n---\nbody", encoding="utf-8"
        )

        loader = PluginLoader(plugins_dir=tmp_path)
        cmd_dirs = loader.get_all_commands_dirs()

        assert len(cmd_dirs) == 1
        assert cmd_dirs[0].name == "commands"

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


class TestParseInstallSource:
    """Tests for install source string parsing."""

    def test_local_directory(self, tmp_path):
        d = tmp_path / "my-plug"
        d.mkdir()
        parsed, err = parse_install_source(str(d))
        assert err is None and parsed is not None
        assert parsed.kind == "local_dir"

    def test_https_git_default(self):
        parsed, err = parse_install_source("https://github.com/o/r.git")
        assert err is None and parsed is not None
        assert parsed.kind == "git"
        assert parsed.ref is None

    def test_git_at(self):
        parsed, err = parse_install_source("git@github.com:o/r.git")
        assert err is None and parsed is not None
        assert parsed.kind == "git"

    def test_url_fragment_ref(self):
        parsed, err = parse_install_source("https://github.com/o/r.git#v1.2.0")
        assert err is None and parsed is not None
        assert parsed.kind == "git"
        assert parsed.ref == "v1.2.0"

    def test_space_separated_ref(self):
        parsed, err = parse_install_source("https://github.com/o/r.git release")
        assert err is None and parsed is not None
        assert parsed.ref == "release"

    def test_https_zip_url(self):
        parsed, err = parse_install_source("https://example.com/a.zip")
        assert err is None and parsed is not None
        assert parsed.kind == "url_archive"


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
        assert RESTART_HINT in result.message
        assert (target / "my-plugin").is_dir()
        assert (target / "my-plugin" / "skills" / "my-skill" / "SKILL.md").is_file()

    @pytest.mark.asyncio
    async def test_plugin_install_from_local_zip(self, tmp_path):
        """Install from a local .zip containing a valid plugin tree."""
        root = tmp_path / "src-plugin"
        skills = root / "skills" / "s1"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text(
            "---\nname: s1\ndescription: S\n---\n", encoding="utf-8"
        )
        (root / "plugin.json").write_text(
            json.dumps({"name": "zip-plugin", "version": "1.0.0"}),
            encoding="utf-8",
        )
        zpath = tmp_path / "bundle.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in root.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(root).as_posix())

        target = tmp_path / "plugins"
        target.mkdir()
        result = await plugin_install(source=str(zpath), plugins_dir=target)

        assert result.success is True
        assert (target / "zip-plugin").is_dir()
        assert (target / "zip-plugin" / "skills" / "s1" / "SKILL.md").is_file()

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

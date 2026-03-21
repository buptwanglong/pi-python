"""Tests for Plugin packaging format — manifest parsing and directory structure."""

import json
import pytest
from pathlib import Path

from basket_assistant.plugins.manifest import (
    PluginManifest,
    load_plugin_manifest,
    validate_plugin_dir,
)
from basket_assistant.plugins.loader import PluginLoader


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

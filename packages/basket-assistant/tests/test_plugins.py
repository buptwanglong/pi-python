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

"""Tests for multi-agent settings (agents, default_agent, resolve_agent)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from basket_assistant.core.settings_full import Settings, load_settings


def test_load_settings_requires_agents_and_default_agent() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"workspace": "/tmp"}, f)
        path = f.name
    try:
        with pytest.raises(ValueError, match="agents"):
            load_settings(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_load_settings_with_agents_and_default_agent() -> None:
    raw = {
        "default_agent": "default",
        "agents": {
            "default": {
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-main",
            },
            "coder": {
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-coder",
            },
        },
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(raw, f)
        path = f.name
    try:
        s = load_settings(path)
        assert isinstance(s, Settings)
        assert s.default_agent == "default"
        assert "default" in s.agents and "coder" in s.agents
        main = s.resolve_agent(None)
        assert main.api_key == "sk-main"
        coder = s.resolve_agent("coder")
        assert coder.api_key == "sk-coder"
    finally:
        Path(path).unlink(missing_ok=True)


def test_load_settings_default_agent_must_exist_in_agents() -> None:
    raw = {
        "default_agent": "main",
        "agents": {"default": {"api_key": "k", "base_url": "https://x", "provider": "openai"}},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(raw, f)
        path = f.name
    try:
        with pytest.raises(ValueError, match="default_agent"):
            load_settings(path)
    finally:
        Path(path).unlink(missing_ok=True)

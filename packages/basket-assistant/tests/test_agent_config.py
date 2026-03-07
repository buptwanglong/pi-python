"""Tests for multi-agent AgentConfig and resolve_agent."""

from __future__ import annotations

import pytest

from basket_assistant.core.agent_config import (
    AgentConfig,
    migrate_legacy_to_agents,
    resolve_agent_config,
)


def test_agent_config_from_dict() -> None:
    cfg = AgentConfig.from_dict(
        {"provider": "openai", "base_url": "https://api.openai.com/v1", "api_key": "sk-x"}
    )
    assert cfg.provider == "openai"
    assert cfg.base_url == "https://api.openai.com/v1"
    assert cfg.api_key == "sk-x"


def test_migrate_legacy_to_agents() -> None:
    raw = {"provider": "openai", "base_url": "https://x/v1", "api_key": "sk-y"}
    out = migrate_legacy_to_agents(raw)
    assert "agents" in out
    assert "default" in out["agents"]
    assert out["agents"]["default"]["api_key"] == "sk-y"
    assert out.get("default_agent") == "default"


def test_resolve_agent_config_uses_default() -> None:
    agents = {
        "default": AgentConfig(provider="openai", base_url="https://a", api_key="k1"),
        "coder": AgentConfig(provider="openai", base_url="https://b", api_key="k2"),
    }
    cfg = resolve_agent_config(agents, "default", None)
    assert cfg.api_key == "k1"
    cfg = resolve_agent_config(agents, "default", "")
    assert cfg.api_key == "k1"


def test_resolve_agent_config_by_name() -> None:
    agents = {
        "default": AgentConfig(api_key="k1"),
        "coder": AgentConfig(api_key="k2"),
    }
    assert resolve_agent_config(agents, "default", "coder").api_key == "k2"


def test_resolve_agent_config_unknown_raises() -> None:
    agents = {"default": AgentConfig(api_key="k1")}
    with pytest.raises(KeyError, match="Unknown agent"):
        resolve_agent_config(agents, "default", "missing")

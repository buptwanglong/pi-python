"""测试配置数据模型"""
import pytest
from pydantic import ValidationError

from basket_assistant.core.configuration.models import (
    ModelSettings,
    AgentSettings,
    PermissionsSettings,
    SubAgentConfig,
    Settings,
    AgentConfig,
    AgentInfo,
)


def test_model_settings_defaults():
    """测试 ModelSettings 默认值"""
    settings = ModelSettings()
    assert settings.provider == "openai"
    assert settings.model_id == "gpt-4o-mini"
    assert settings.temperature == 0.7
    assert settings.max_tokens == 4096
    assert settings.context_window == 128000
    assert settings.base_url is None


def test_model_settings_custom():
    """测试 ModelSettings 自定义值"""
    settings = ModelSettings(
        provider="anthropic",
        model_id="claude-sonnet-4",
        base_url="https://custom.api"
    )
    assert settings.provider == "anthropic"
    assert settings.model_id == "claude-sonnet-4"
    assert settings.base_url == "https://custom.api"


def test_agent_settings_defaults():
    """测试 AgentSettings 默认值"""
    settings = AgentSettings()
    assert settings.max_turns == 10
    assert settings.auto_save is True
    assert settings.verbose is False


def test_permissions_settings_defaults():
    """测试 PermissionsSettings 默认值"""
    settings = PermissionsSettings()
    assert settings.default_mode == "default"


def test_sub_agent_config_optional_fields():
    """测试 SubAgentConfig 可选字段"""
    config = SubAgentConfig()
    assert config.model is None
    assert config.tools is None
    assert config.agent_dir is None
    assert config.workspace_dir is None


def test_sub_agent_config_with_values():
    """测试 SubAgentConfig 带值"""
    config = SubAgentConfig(
        model={"provider": "openai", "model_id": "gpt-4"},
        tools={"read": True, "write": False},
        workspace_dir="/path/to/workspace"
    )
    assert config.model == {"provider": "openai", "model_id": "gpt-4"}
    assert config.tools == {"read": True, "write": False}
    assert config.workspace_dir == "/path/to/workspace"


def test_settings_defaults():
    """测试 Settings 默认值"""
    settings = Settings()
    assert settings.model.provider == "openai"
    assert settings.agent.max_turns == 10
    assert settings.permissions.default_mode == "default"
    assert settings.api_keys == {}
    assert settings.sessions_dir == "~/.basket/sessions"
    assert settings.trajectory_dir == "~/.basket/trajectories"
    assert settings.agents == {}
    assert settings.default_agent is None


def test_settings_validate_agents_consistency():
    """测试 Settings 校验 agents 和 default_agent 一致性"""
    # default_agent 存在于 agents 中 - 正常
    settings = Settings(
        default_agent="main",
        agents={"main": SubAgentConfig()}
    )
    assert settings.default_agent == "main"

    # default_agent 不存在于 agents 中 - 抛出异常
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            default_agent="main",
            agents={"other": SubAgentConfig()}
        )
    assert "default_agent" in str(exc_info.value).lower()


def test_agent_config():
    """测试 AgentConfig 运行时配置"""
    config = AgentConfig(
        provider="anthropic",
        base_url="https://api.anthropic.com",
        api_key="sk-ant-xxx",
        model="claude-sonnet-4",
        temperature=0.8
    )
    assert config.provider == "anthropic"
    assert config.base_url == "https://api.anthropic.com"
    assert config.model == "claude-sonnet-4"


def test_agent_info():
    """测试 AgentInfo 展示模型"""
    info = AgentInfo(
        name="test-agent",
        workspace_dir="/path/to/workspace",
        has_model_override=True,
        tools={"read": True}
    )
    assert info.name == "test-agent"
    assert info.workspace_dir == "/path/to/workspace"
    assert info.has_model_override is True
    assert info.tools == {"read": True}

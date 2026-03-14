"""测试智能体管理器"""
import pytest
from pathlib import Path

from basket_assistant.core.configuration.models import Settings, SubAgentConfig, AgentInfo
from basket_assistant.core.configuration.agents import (
    AgentManager,
    AgentError,
    AgentExistsError,
    AgentNotFoundError,
    CannotRemoveDefaultAgentError,
)


def test_agent_manager_init(tmp_path):
    """测试 AgentManager 初始化"""
    config_path = tmp_path / "settings.json"

    # 需要一个 ConfigurationManager 实例
    from basket_assistant.core.configuration.manager import ConfigurationManager
    config_manager = ConfigurationManager(config_path)

    # 创建 AgentManager
    agent_manager = AgentManager(config_manager)

    assert agent_manager.config_manager is config_manager


def test_list_agents_empty(tmp_path):
    """测试列出智能体 - 空列表"""
    config_path = tmp_path / "settings.json"

    from basket_assistant.core.configuration.manager import ConfigurationManager
    config_manager = ConfigurationManager(config_path)
    agent_manager = AgentManager(config_manager)

    # 默认配置没有智能体
    agents = agent_manager.list_agents()
    assert agents == []


def test_list_agents_with_agents(tmp_path):
    """测试列出智能体 - 有智能体"""
    config_path = tmp_path / "settings.json"

    from basket_assistant.core.configuration.manager import ConfigurationManager
    config_manager = ConfigurationManager(config_path)

    # 创建包含智能体的配置
    settings = Settings(
        agents={
            "agent-1": SubAgentConfig(workspace_dir="~/workspace/agent-1"),
            "agent-2": SubAgentConfig(
                workspace_dir="~/workspace/agent-2",
                model={"provider": "anthropic"}
            ),
        }
    )
    config_manager.save(settings)

    agent_manager = AgentManager(config_manager)
    agents = agent_manager.list_agents()

    assert len(agents) == 2

    # 检查返回的 AgentInfo
    agent_names = [a.name for a in agents]
    assert "agent-1" in agent_names
    assert "agent-2" in agent_names

    # 检查字段
    agent_2 = [a for a in agents if a.name == "agent-2"][0]
    assert agent_2.workspace_dir == "~/workspace/agent-2"
    assert agent_2.has_model_override is True


def test_exception_types():
    """测试异常类型"""
    # 测试 AgentExistsError
    err1 = AgentExistsError("test-agent")
    assert err1.name == "test-agent"
    assert "test-agent" in str(err1)
    assert "已存在" in str(err1)
    assert isinstance(err1, AgentError)

    # 测试 AgentNotFoundError
    err2 = AgentNotFoundError("missing-agent")
    assert err2.name == "missing-agent"
    assert "missing-agent" in str(err2)
    assert "不存在" in str(err2)
    assert isinstance(err2, AgentError)

    # 测试 CannotRemoveDefaultAgentError
    err3 = CannotRemoveDefaultAgentError("default-agent")
    assert err3.name == "default-agent"
    assert "default-agent" in str(err3)
    assert "不能删除" in str(err3)
    assert isinstance(err3, AgentError)


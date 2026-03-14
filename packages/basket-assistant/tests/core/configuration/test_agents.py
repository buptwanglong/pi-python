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


# === add_agent() 测试 ===


def test_add_agent_basic(tmp_path):
    """测试添加智能体 - 基本功能"""
    config_path = tmp_path / "settings.json"

    from basket_assistant.core.configuration.manager import ConfigurationManager
    config_manager = ConfigurationManager(config_path)
    agent_manager = AgentManager(config_manager)

    # 添加智能体
    new_settings = agent_manager.add_agent(name="test-agent")

    # 验证返回新配置
    assert "test-agent" in new_settings.agents
    assert new_settings.agents["test-agent"].workspace_dir is not None

    # 验证配置已保存
    loaded = config_manager.load()
    assert "test-agent" in loaded.agents


def test_add_agent_with_workspace(tmp_path):
    """测试添加智能体 - 指定 workspace"""
    config_path = tmp_path / "settings.json"
    workspace_dir = str(tmp_path / "my-workspace")

    from basket_assistant.core.configuration.manager import ConfigurationManager
    config_manager = ConfigurationManager(config_path)
    agent_manager = AgentManager(config_manager)

    # 添加智能体并指定 workspace
    new_settings = agent_manager.add_agent(
        name="test-agent",
        workspace_dir=workspace_dir
    )

    assert new_settings.agents["test-agent"].workspace_dir == workspace_dir

    # 验证目录已创建
    assert Path(workspace_dir).exists()


def test_add_agent_with_model_override(tmp_path):
    """测试添加智能体 - 模型覆盖"""
    config_path = tmp_path / "settings.json"

    from basket_assistant.core.configuration.manager import ConfigurationManager
    config_manager = ConfigurationManager(config_path)
    agent_manager = AgentManager(config_manager)

    # 添加智能体并覆盖模型
    new_settings = agent_manager.add_agent(
        name="test-agent",
        model={"provider": "anthropic", "model_id": "claude-sonnet-4"}
    )

    assert new_settings.agents["test-agent"].model is not None
    assert new_settings.agents["test-agent"].model["provider"] == "anthropic"


def test_add_agent_invalid_name(tmp_path):
    """测试添加智能体 - 名称格式不正确"""
    config_path = tmp_path / "settings.json"

    from basket_assistant.core.configuration.manager import ConfigurationManager
    from basket_assistant.core.configuration.validation import ValidationError
    config_manager = ConfigurationManager(config_path)
    agent_manager = AgentManager(config_manager)

    # 大写字母
    with pytest.raises(ValidationError) as exc:
        agent_manager.add_agent(name="MyAgent")
    assert "invalid" in str(exc.value).lower()

    # 下划线
    with pytest.raises(ValidationError) as exc:
        agent_manager.add_agent(name="my_agent")
    assert "invalid" in str(exc.value).lower()

    # 空名称
    with pytest.raises(ValidationError) as exc:
        agent_manager.add_agent(name="")
    assert "empty" in str(exc.value).lower()


def test_add_agent_already_exists(tmp_path):
    """测试添加智能体 - 已存在"""
    config_path = tmp_path / "settings.json"

    from basket_assistant.core.configuration.manager import ConfigurationManager
    config_manager = ConfigurationManager(config_path)
    agent_manager = AgentManager(config_manager)

    # 添加第一次
    agent_manager.add_agent(name="test-agent")

    # 再次添加应该抛出异常
    with pytest.raises(AgentExistsError) as exc:
        agent_manager.add_agent(name="test-agent")
    assert exc.value.name == "test-agent"


def test_add_agent_force_overwrite(tmp_path):
    """测试添加智能体 - force 覆盖"""
    config_path = tmp_path / "settings.json"

    from basket_assistant.core.configuration.manager import ConfigurationManager
    config_manager = ConfigurationManager(config_path)
    agent_manager = AgentManager(config_manager)

    # 添加第一次
    agent_manager.add_agent(name="test-agent", model={"provider": "openai"})

    # force=True 覆盖
    new_settings = agent_manager.add_agent(
        name="test-agent",
        model={"provider": "anthropic"},
        force=True
    )

    assert new_settings.agents["test-agent"].model["provider"] == "anthropic"


def test_add_agent_workspace_files(tmp_path):
    """测试添加智能体 - 验证 workspace 文件内容"""
    config_path = tmp_path / "settings.json"

    from basket_assistant.core.configuration.manager import ConfigurationManager
    config_manager = ConfigurationManager(config_path)
    agent_manager = AgentManager(config_manager)

    # 添加智能体
    new_settings = agent_manager.add_agent(name="test-agent")

    # 验证默认 workspace 路径
    workspace_path = Path.home() / ".basket" / "workspace" / "test-agent"
    assert workspace_path.exists()

    # 验证 IDENTITY.md
    identity_file = workspace_path / "IDENTITY.md"
    assert identity_file.exists()
    identity_content = identity_file.read_text(encoding="utf-8")
    assert "Agent Identity" in identity_content
    assert "Role and responsibilities" in identity_content

    # 验证 README.md
    readme_file = workspace_path / "README.md"
    assert readme_file.exists()
    readme_content = readme_file.read_text(encoding="utf-8")
    assert "Agent Workspace" in readme_content
    assert "Session data" in readme_content

    # 清理测试创建的目录
    import shutil
    shutil.rmtree(workspace_path)


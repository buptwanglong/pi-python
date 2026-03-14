"""测试 ConfigurationManager"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from basket_assistant.core.configuration import ConfigurationManager
from basket_assistant.core.configuration.models import Settings


def test_manager_init_default_path(tmp_path):
    """测试 Manager 默认路径"""
    manager = ConfigurationManager()
    assert manager.config_path is not None


def test_manager_init_custom_path(tmp_path):
    """测试 Manager 自定义路径"""
    config_path = tmp_path / "custom_settings.json"
    manager = ConfigurationManager(config_path)
    assert manager.config_path == config_path


def test_manager_exists(tmp_path):
    """测试配置文件存在性检查"""
    config_path = tmp_path / "settings.json"
    manager = ConfigurationManager(config_path)

    assert not manager.exists()

    config_path.write_text("{}")
    assert manager.exists()


def test_manager_save_and_load(tmp_path):
    """测试保存和加载配置"""
    config_path = tmp_path / "settings.json"
    manager = ConfigurationManager(config_path)

    # 保存配置
    settings = Settings(
        model={"provider": "anthropic", "model_id": "claude-sonnet-4"}
    )
    manager.save(settings)

    # 加载配置
    loaded = manager.load()
    assert loaded.model.provider == "anthropic"
    assert loaded.model.model_id == "claude-sonnet-4"


def test_manager_load_nonexistent_returns_default(tmp_path):
    """测试加载不存在的配置返回默认值"""
    config_path = tmp_path / "nonexistent.json"
    manager = ConfigurationManager(config_path)

    settings = manager.load()
    assert settings.model.provider == "openai"  # 默认值


@patch("sys.stdin.isatty", return_value=False)
def test_run_guided_init_non_interactive(mock_isatty, tmp_path):
    """测试 run_guided_init 非交互模式"""
    config_path = tmp_path / "settings.json"
    manager = ConfigurationManager(config_path)
    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
        settings = manager.run_guided_init(force=True)
    assert settings.model.provider == "openai"
    assert config_path.exists()


def test_list_agents_empty(tmp_path):
    """测试无智能体时 list_agents 返回空列表"""
    config_path = tmp_path / "settings.json"
    manager = ConfigurationManager(config_path)
    manager.save(Settings())
    agents = manager.list_agents()
    assert agents == []


def test_get_agent_config_no_agents(tmp_path):
    """测试无智能体时 get_agent_config 使用顶层配置"""
    config_path = tmp_path / "settings.json"
    manager = ConfigurationManager(config_path)
    manager.save(
        Settings(
            model={"provider": "anthropic", "model_id": "claude-3-opus"},
            api_keys={"anthropic": "sk-ant-test"},
        )
    )
    cfg = manager.get_agent_config(None)
    assert cfg.provider == "anthropic"
    assert cfg.model == "claude-3-opus"
    assert cfg.api_key == "sk-ant-test"


def test_get_model_config_no_agents(tmp_path):
    """测试无智能体时 get_model_config 返回顶层模型配置"""
    config_path = tmp_path / "settings.json"
    manager = ConfigurationManager(config_path)
    manager.save(
        Settings(model={"provider": "google", "model_id": "gemini-1.5-pro"})
    )
    cfg = manager.get_model_config(None)
    assert cfg["provider"] == "google"
    assert cfg["model_id"] == "gemini-1.5-pro"

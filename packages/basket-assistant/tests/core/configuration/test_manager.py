"""测试 ConfigurationManager"""
import json
import pytest
from pathlib import Path

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

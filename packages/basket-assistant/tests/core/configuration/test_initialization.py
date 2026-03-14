"""测试初始化向导"""
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from basket_assistant.core.configuration.initialization import ConfigInitializer
from basket_assistant.core.configuration.models import Settings


def test_initializer_init(tmp_path):
    """测试 ConfigInitializer 初始化"""
    config_path = tmp_path / "settings.json"

    from basket_assistant.core.configuration.manager import ConfigurationManager
    config_manager = ConfigurationManager(config_path)

    initializer = ConfigInitializer(config_manager)

    assert initializer.config_manager is config_manager


@patch('sys.stdin.isatty', return_value=False)
def test_run_non_interactive_mode(mock_isatty, tmp_path):
    """测试非交互模式（自动使用默认值）"""
    config_path = tmp_path / "settings.json"

    from basket_assistant.core.configuration.manager import ConfigurationManager
    config_manager = ConfigurationManager(config_path)
    initializer = ConfigInitializer(config_manager)

    # 非交互模式应该返回默认配置
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        settings = initializer.run(force=True)

    assert settings.model.provider == "openai"
    assert config_path.exists()


def test_provider_info():
    """测试 provider 信息定义"""
    from basket_assistant.core.configuration.initialization import PROVIDER_CHOICES

    assert len(PROVIDER_CHOICES) >= 3

    # 验证格式：(provider_id, display_name, default_model, env_var)
    openai_info = PROVIDER_CHOICES[0]
    assert openai_info[0] == "openai"
    assert "OpenAI" in openai_info[1]
    assert openai_info[3] == "OPENAI_API_KEY"


@patch('sys.stdin.isatty', return_value=False)
def test_run_with_existing_config_force_true(mock_isatty, tmp_path):
    """测试覆盖现有配置 - force=True"""
    config_path = tmp_path / "settings.json"

    # 创建现有配置
    existing_config = {"model": {"provider": "anthropic"}}
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(existing_config))

    from basket_assistant.core.configuration.manager import ConfigurationManager
    config_manager = ConfigurationManager(config_path)
    initializer = ConfigInitializer(config_manager)

    # force=True 应该直接覆盖
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        settings = initializer.run(force=True)

    # 验证配置被覆盖（使用环境变量检测到的 provider）
    assert settings.model.provider == "openai"


@patch('sys.stdin.isatty', return_value=False)
def test_run_with_existing_config_force_false(mock_isatty, tmp_path):
    """测试现有配置 - force=False - 非交互模式应该保留原配置"""
    config_path = tmp_path / "settings.json"

    # 创建现有配置
    existing_config = {"model": {"provider": "anthropic", "model_id": "claude-3-opus-20240229"}}
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(existing_config))

    from basket_assistant.core.configuration.manager import ConfigurationManager
    config_manager = ConfigurationManager(config_path)
    initializer = ConfigInitializer(config_manager)

    # force=False + 非交互模式 应该加载现有配置
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        settings = initializer.run(force=False)

    # 验证配置未被覆盖
    assert settings.model.provider == "anthropic"
    assert settings.model.model_id == "claude-3-opus-20240229"


@patch('sys.stdin.isatty', return_value=False)
def test_detect_anthropic_from_env(mock_isatty, tmp_path):
    """测试环境变量检测 - Anthropic"""
    config_path = tmp_path / "settings.json"

    from basket_assistant.core.configuration.manager import ConfigurationManager
    config_manager = ConfigurationManager(config_path)
    initializer = ConfigInitializer(config_manager)

    with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'sk-ant-test123'}, clear=True):
        settings = initializer.run(force=True)

    assert settings.model.provider == "anthropic"
    assert settings.model.model_id == "claude-3-5-sonnet-20241022"
    assert "anthropic_api_key" in settings.api_keys


@patch('sys.stdin.isatty', return_value=False)
def test_detect_google_from_env(mock_isatty, tmp_path):
    """测试环境变量检测 - Google"""
    config_path = tmp_path / "settings.json"

    from basket_assistant.core.configuration.manager import ConfigurationManager
    config_manager = ConfigurationManager(config_path)
    initializer = ConfigInitializer(config_manager)

    with patch.dict('os.environ', {'GOOGLE_API_KEY': 'AIzaTest123'}, clear=True):
        settings = initializer.run(force=True)

    assert settings.model.provider == "google"
    assert settings.model.model_id == "gemini-1.5-pro"
    assert "google_api_key" in settings.api_keys


@patch('sys.stdin.isatty', return_value=False)
def test_no_api_key_in_env(mock_isatty, tmp_path):
    """测试没有 API Key 环境变量的情况"""
    config_path = tmp_path / "settings.json"

    from basket_assistant.core.configuration.manager import ConfigurationManager
    config_manager = ConfigurationManager(config_path)
    initializer = ConfigInitializer(config_manager)

    with patch.dict('os.environ', {}, clear=True):
        settings = initializer.run(force=True)

    # 应该使用默认 provider (openai)，但没有 API Key
    assert settings.model.provider == "openai"
    assert settings.model.model_id == "gpt-4o-mini"
    assert len(settings.api_keys) == 0

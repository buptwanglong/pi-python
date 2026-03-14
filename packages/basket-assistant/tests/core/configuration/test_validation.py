"""测试配置校验逻辑"""
import pytest

from basket_assistant.core.configuration.models import Settings, SubAgentConfig
from basket_assistant.core.configuration.validation import (
    ConfigValidator,
    ValidationError,
    ValidationWarning,
)


class TestAgentNameValidation:
    """测试智能体名称校验"""

    def test_validate_agent_name_valid(self):
        """测试合法的智能体名称"""
        validator = ConfigValidator()

        # 合法名称
        valid_names = [
            "my-agent",
            "agent-123",
            "a",
            "agent-with-multiple-parts",
            "123-456",
        ]

        for name in valid_names:
            validator.validate_agent_name(name)  # Should not raise

    def test_validate_agent_name_invalid_empty(self):
        """测试空名称"""
        validator = ConfigValidator()

        with pytest.raises(ValidationError, match="Agent name cannot be empty"):
            validator.validate_agent_name("")

    def test_validate_agent_name_invalid_uppercase(self):
        """测试包含大写字母的名称"""
        validator = ConfigValidator()

        with pytest.raises(ValidationError, match="must contain only lowercase letters"):
            validator.validate_agent_name("MyAgent")

    def test_validate_agent_name_invalid_underscore(self):
        """测试包含下划线的名称"""
        validator = ConfigValidator()

        with pytest.raises(ValidationError, match="must contain only lowercase letters"):
            validator.validate_agent_name("my_agent")

    def test_validate_agent_name_invalid_starts_with_hyphen(self):
        """测试以连字符开头的名称"""
        validator = ConfigValidator()

        with pytest.raises(ValidationError, match="cannot start or end with a hyphen"):
            validator.validate_agent_name("-agent")

    def test_validate_agent_name_invalid_ends_with_hyphen(self):
        """测试以连字符结尾的名称"""
        validator = ConfigValidator()

        with pytest.raises(ValidationError, match="cannot start or end with a hyphen"):
            validator.validate_agent_name("agent-")

    def test_validate_agent_name_invalid_too_long(self):
        """测试过长的名称"""
        validator = ConfigValidator()

        long_name = "a" * 101
        with pytest.raises(ValidationError, match="must be 100 characters or less"):
            validator.validate_agent_name(long_name)


class TestApiKeyValidation:
    """测试 API Key 校验"""

    def test_validate_api_key_valid_openai(self):
        """测试合法的 OpenAI API Key"""
        validator = ConfigValidator()

        valid_keys = [
            "sk-1234567890abcdefghijklmnopqrstuvwxyz",
            "sk-proj-1234567890abcdefghijklmnopqrstuvwxyz",
        ]

        for key in valid_keys:
            validator.validate_api_key("openai", key)  # Should not raise

    def test_validate_api_key_valid_anthropic(self):
        """测试合法的 Anthropic API Key"""
        validator = ConfigValidator()

        key = "sk-ant-1234567890abcdefghijklmnopqrstuvwxyz"
        validator.validate_api_key("anthropic", key)  # Should not raise

    def test_validate_api_key_valid_google(self):
        """测试合法的 Google API Key"""
        validator = ConfigValidator()

        key = "AIza1234567890abcdefghijklmnopqrstuvwxyz"
        validator.validate_api_key("google", key)  # Should not raise

    def test_validate_api_key_invalid_format(self):
        """测试格式错误的 API Key"""
        validator = ConfigValidator()

        with pytest.raises(ValidationError, match="Invalid API key format"):
            validator.validate_api_key("openai", "invalid-key")

    def test_validate_api_key_empty(self):
        """测试空 API Key"""
        validator = ConfigValidator()

        with pytest.raises(ValidationError, match="API key cannot be empty"):
            validator.validate_api_key("openai", "")

    def test_validate_api_key_unknown_provider(self):
        """测试未知 provider 的 API Key（应该通过，只给出警告）"""
        validator = ConfigValidator()

        # 未知 provider 不应该抛出异常
        validator.validate_api_key("unknown-provider", "any-key")


class TestModelIdValidation:
    """测试模型 ID 校验"""

    def test_validate_model_id_valid(self):
        """测试合法的模型 ID"""
        validator = ConfigValidator()

        valid_ids = [
            "gpt-4",
            "claude-sonnet-4-20250514",
            "gemini-2.0-flash-exp",
            "llama-3.1-70b",
        ]

        for model_id in valid_ids:
            validator.validate_model_id(model_id)  # Should not raise

    def test_validate_model_id_empty(self):
        """测试空模型 ID"""
        validator = ConfigValidator()

        with pytest.raises(ValidationError, match="Model ID cannot be empty"):
            validator.validate_model_id("")

    def test_validate_model_id_invalid_chars(self):
        """测试包含非法字符的模型 ID"""
        validator = ConfigValidator()

        with pytest.raises(ValidationError, match="must contain only"):
            validator.validate_model_id("model@#$%")


class TestSettingsValidation:
    """测试完整配置校验"""

    def test_validate_settings_valid_minimal(self):
        """测试最小合法配置"""
        validator = ConfigValidator()

        settings = Settings(
            model={
                "provider": "openai",
                "model_id": "gpt-4",
            },
            api_keys={
                "openai": "sk-1234567890abcdefghijklmnopqrstuvwxyz",
            },
        )

        errors, warnings = validator.validate_settings(settings)

        assert len(errors) == 0
        assert len(warnings) == 0

    def test_validate_settings_valid_with_subagents(self):
        """测试包含子智能体的配置"""
        validator = ConfigValidator()

        settings = Settings(
            model={
                "provider": "openai",
                "model_id": "gpt-4",
            },
            api_keys={
                "openai": "sk-1234567890abcdefghijklmnopqrstuvwxyz",
            },
            agents={
                "explorer": SubAgentConfig(
                    model={"provider": "openai", "model_id": "gpt-4"},
                ),
            },
        )

        errors, warnings = validator.validate_settings(settings)

        assert len(errors) == 0
        assert len(warnings) == 0

    def test_validate_settings_invalid_agent_name(self):
        """测试非法的智能体名称"""
        validator = ConfigValidator()

        settings = Settings(
            model={
                "provider": "openai",
                "model_id": "gpt-4",
            },
            api_keys={
                "openai": "sk-1234567890abcdefghijklmnopqrstuvwxyz",
            },
            agents={
                "Invalid_Name": SubAgentConfig(
                    model={"provider": "openai", "model_id": "gpt-4"},
                ),
            },
        )

        errors, warnings = validator.validate_settings(settings)

        assert len(errors) == 1
        assert "must contain only lowercase letters" in errors[0]

    def test_validate_settings_invalid_api_key(self):
        """测试非法的 API Key"""
        validator = ConfigValidator()

        settings = Settings(
            model={
                "provider": "openai",
                "model_id": "gpt-4",
            },
            api_keys={
                "openai": "invalid-key",
            },
        )

        errors, warnings = validator.validate_settings(settings)

        assert len(errors) == 1
        assert "Invalid API key format" in errors[0]

    def test_validate_settings_missing_api_key(self):
        """测试缺失的 API Key"""
        validator = ConfigValidator()

        settings = Settings(
            model={
                "provider": "openai",
                "model_id": "gpt-4",
            },
            api_keys={},
        )

        errors, warnings = validator.validate_settings(settings)

        # 应该有警告但不是错误
        assert len(warnings) > 0
        assert any("API key not found" in w for w in warnings)

    def test_validate_settings_invalid_model_id(self):
        """测试非法的模型 ID"""
        validator = ConfigValidator()

        settings = Settings(
            model={
                "provider": "openai",
                "model_id": "invalid@model",
            },
            api_keys={
                "openai": "sk-1234567890abcdefghijklmnopqrstuvwxyz",
            },
        )

        errors, warnings = validator.validate_settings(settings)

        assert len(errors) == 1
        assert "must contain only" in errors[0]


class TestValidationWarning:
    """测试校验警告"""

    def test_validation_warning_format(self):
        """测试警告格式化"""
        warning = ValidationWarning("This is a warning")

        assert str(warning) == "This is a warning"
        assert warning.message == "This is a warning"

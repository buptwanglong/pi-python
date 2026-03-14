"""配置校验逻辑

提供配置格式检查、一致性验证和友好的错误提示。
"""
import re
from typing import Any

from basket_assistant.core.configuration.models import Settings


class ValidationError(Exception):
    """配置校验错误（阻断性）"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationWarning:
    """配置校验警告（非阻断性）"""

    def __init__(self, message: str):
        self.message = message

    def __str__(self) -> str:
        return self.message


class ConfigValidator:
    """配置校验器"""

    # 智能体名称规范：小写字母、数字、连字符，不能以连字符开头或结尾
    AGENT_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

    # API Key 格式规则（provider -> pattern）
    API_KEY_PATTERNS = {
        "openai": re.compile(r"^sk-(proj-)?[a-zA-Z0-9]{20,}$"),
        "anthropic": re.compile(r"^sk-ant-[a-zA-Z0-9\-]{20,}$"),
        "google": re.compile(r"^AIza[a-zA-Z0-9\-_]{35,}$"),
        "groq": re.compile(r"^gsk_[a-zA-Z0-9]{20,}$"),
        "together": re.compile(r"^[a-f0-9]{64}$"),
        "deepseek": re.compile(r"^sk-[a-f0-9]{32}$"),
        "cerebras": re.compile(r"^csk-[a-zA-Z0-9]{20,}$"),
        "xai": re.compile(r"^xai-[a-zA-Z0-9]{20,}$"),
    }

    # 模型 ID 格式规则
    MODEL_ID_PATTERN = re.compile(r"^[a-z0-9\.\-_]+$", re.IGNORECASE)

    def validate_settings(self, settings: Settings) -> tuple[list[str], list[str]]:
        """校验完整的配置对象

        Args:
            settings: 配置对象

        Returns:
            (errors, warnings): 错误列表和警告列表
        """
        errors: list[str] = []
        warnings: list[str] = []

        # 校验主模型配置
        try:
            self.validate_model_id(settings.model.model_id)
        except ValidationError as e:
            errors.append(f"Main model: {e.message}")

        # 校验主 API Key
        provider = settings.model.provider
        if provider:
            api_key = settings.api_keys.get(provider, "")
            if not api_key:
                warnings.append(
                    f"API key not found for provider '{provider}'. "
                    f"Set '{provider.upper()}_API_KEY' environment variable "
                    f"or add to api_keys in settings."
                )
            else:
                try:
                    self.validate_api_key(provider, api_key)
                except ValidationError as e:
                    errors.append(f"API key for '{provider}': {e.message}")

        # 校验子智能体配置
        if settings.agents:
            for agent_name, agent_config in settings.agents.items():
                # 校验智能体名称
                try:
                    self.validate_agent_name(agent_name)
                except ValidationError as e:
                    errors.append(f"Agent '{agent_name}': {e.message}")

                # 校验子智能体的模型 ID
                if agent_config.model:
                    model_id = agent_config.model.get("model_id", "")
                    if model_id:
                        try:
                            self.validate_model_id(model_id)
                        except ValidationError as e:
                            errors.append(f"Agent '{agent_name}' model: {e.message}")

                    # 校验子智能体的 API Key
                    agent_provider = agent_config.model.get("provider", "")
                    if agent_provider:
                        agent_api_key = settings.api_keys.get(agent_provider, "")
                        if not agent_api_key:
                            warnings.append(
                                f"Agent '{agent_name}': API key not found for provider "
                                f"'{agent_provider}'"
                            )
                        else:
                            try:
                                self.validate_api_key(agent_provider, agent_api_key)
                            except ValidationError as e:
                                errors.append(
                                    f"Agent '{agent_name}' API key for "
                                    f"'{agent_provider}': {e.message}"
                                )

        return errors, warnings

    def validate_agent_name(self, name: str) -> None:
        """校验智能体名称

        Args:
            name: 智能体名称

        Raises:
            ValidationError: 名称不符合规范
        """
        if not name:
            raise ValidationError("Agent name cannot be empty")

        if len(name) > 100:
            raise ValidationError("Agent name must be 100 characters or less")

        if not self.AGENT_NAME_PATTERN.match(name):
            raise ValidationError(
                f"Agent name '{name}' is invalid. "
                f"It must contain only lowercase letters, numbers, and hyphens, "
                f"and cannot start or end with a hyphen. "
                f"Valid examples: 'my-agent', 'agent-123', 'explorer'"
            )

    def validate_api_key(self, provider: str, api_key: str) -> None:
        """校验 API Key 格式

        Args:
            provider: Provider 名称
            api_key: API Key

        Raises:
            ValidationError: API Key 格式不正确
        """
        if not api_key:
            raise ValidationError("API key cannot be empty")

        # 如果是未知的 provider，跳过格式校验（给出警告但不报错）
        if provider not in self.API_KEY_PATTERNS:
            return

        pattern = self.API_KEY_PATTERNS[provider]
        if not pattern.match(api_key):
            raise ValidationError(
                f"Invalid API key format for provider '{provider}'. "
                f"Please check your API key and try again. "
                f"Expected format: {self._get_api_key_format_hint(provider)}"
            )

    def validate_model_id(self, model_id: str) -> None:
        """校验模型 ID

        Args:
            model_id: 模型 ID

        Raises:
            ValidationError: 模型 ID 不符合规范
        """
        if not model_id:
            raise ValidationError("Model ID cannot be empty")

        if not self.MODEL_ID_PATTERN.match(model_id):
            raise ValidationError(
                f"Model ID '{model_id}' is invalid. "
                f"It must contain only letters, numbers, dots, hyphens, and underscores. "
                f"Valid examples: 'gpt-4', 'claude-sonnet-4-20250514', 'gemini-2.0-flash-exp'"
            )

    def _get_api_key_format_hint(self, provider: str) -> str:
        """获取 API Key 格式提示

        Args:
            provider: Provider 名称

        Returns:
            格式提示字符串
        """
        hints = {
            "openai": "sk-... or sk-proj-...",
            "anthropic": "sk-ant-...",
            "google": "AIza...",
            "groq": "gsk_...",
            "together": "64-character hex string",
            "deepseek": "sk-... (32-character hex)",
            "cerebras": "csk-...",
            "xai": "xai-...",
        }
        return hints.get(provider, "provider-specific format")

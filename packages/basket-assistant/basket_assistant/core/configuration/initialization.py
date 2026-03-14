"""配置初始化向导：交互式配置创建"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from .models import ModelSettings, Settings
from .validation import ConfigValidator

if TYPE_CHECKING:
    from .manager import ConfigurationManager

logger = logging.getLogger(__name__)

# Provider 选项：(id, display_name, default_model, env_var)
PROVIDER_CHOICES = [
    ("openai", "OpenAI (GPT)", "gpt-4o-mini", "OPENAI_API_KEY"),
    ("anthropic", "Anthropic (Claude)", "claude-3-5-sonnet-20241022", "ANTHROPIC_API_KEY"),
    ("google", "Google (Gemini)", "gemini-1.5-pro", "GOOGLE_API_KEY"),
]

# Web 搜索选项
WEB_SEARCH_CHOICES = [
    ("duckduckgo", "duckduckgo（默认，无需 API Key）"),
    ("serper", "serper（Google 搜索，需 Serper API）"),
]


class ConfigInitializer:
    """配置初始化向导"""

    def __init__(self, config_manager: ConfigurationManager):
        """
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        self._validator = ConfigValidator()

    def run(self, force: bool = False) -> Settings:
        """
        运行 6 步初始化流程

        Args:
            force: 是否强制覆盖现有配置

        Returns:
            创建的配置

        Steps:
            1. Provider 选择
            2. API Key 输入（脱敏）
            3. Model 选择
            4. Base URL（可选）
            5. Workspace 目录（可选）
            6. Web 搜索配置
        """
        # Step 0: 检查覆盖确认
        if self.config_manager.exists() and not force:
            if not self._confirm_overwrite():
                logger.info("用户取消初始化")
                return self.config_manager.load()

        # 检查是否为交互模式
        use_interactive = self._use_interactive_mode()

        if not use_interactive:
            # 非交互模式：使用环境变量自动配置
            logger.info("非交互模式：使用环境变量自动配置")
            settings = self._create_from_environment()
        else:
            # 交互模式：6步向导
            logger.info("交互模式：启动配置向导")
            settings = self._run_interactive_wizard()

        # 保存配置
        self.config_manager.save(settings)
        logger.info(f"配置已保存到: {self.config_manager.config_path}")

        return settings

    def _use_interactive_mode(self) -> bool:
        """检查是否使用交互模式"""
        if not sys.stdin.isatty():
            return False

        # 检查 questionary 是否可用
        try:
            import questionary  # noqa: F401
            return True
        except ImportError:
            logger.warning("questionary 未安装，使用非交互模式")
            return False

    def _confirm_overwrite(self) -> bool:
        """确认覆盖现有配置"""
        path = self.config_manager.config_path

        if not self._use_interactive_mode():
            # 非交互模式：不覆盖
            return False

        # 交互模式：询问用户
        try:
            import questionary
            from prompt_toolkit.styles import Style

            ok = questionary.confirm(
                f"配置文件已存在：{path}\n是否覆盖？",
                default=False,
                qmark="•",
                style=Style.from_dict({"qmark": "ansiblue", "question": "ansiblue"}),
            ).ask()

            return ok is not None and ok
        except Exception as e:
            logger.error(f"确认覆盖失败: {e}")
            return False

    def _create_from_environment(self) -> Settings:
        """从环境变量创建配置（非交互模式）"""
        # 检测环境变量中的 API Key
        provider = "openai"
        api_key_var = "OPENAI_API_KEY"
        default_model = "gpt-4o-mini"

        for prov_id, _, model, env_var in PROVIDER_CHOICES:
            if os.environ.get(env_var):
                provider = prov_id
                api_key_var = env_var
                default_model = model
                break

        logger.info(f"检测到 {api_key_var}，使用 provider: {provider}")

        # 创建配置
        api_keys = {}
        if os.environ.get(api_key_var):
            api_keys[api_key_var.lower()] = os.environ[api_key_var]

        settings = Settings(
            model=ModelSettings(
                provider=provider,
                model_id=default_model,
            ),
            api_keys=api_keys,
        )

        return settings

    def _run_interactive_wizard(self) -> Settings:
        """运行交互式6步向导"""
        # 这里是交互式实现的占位符
        # 实际实现会在后续完成
        logger.info("交互式向导（暂未实现，使用默认配置）")
        return self._create_from_environment()

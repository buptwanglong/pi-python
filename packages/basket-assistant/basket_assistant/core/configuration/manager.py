"""ConfigurationManager - 统一配置管理入口"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional, Any

from .models import Settings
from .validation import ConfigValidator

logger = logging.getLogger(__name__)


class ConfigurationManager:
    """统一配置管理器：初始化、加载、保存、智能体管理"""

    def __init__(self, config_path: Path | str | None = None):
        """
        Args:
            config_path: 配置文件路径，None 则使用默认路径
        """
        self.config_path = self._resolve_path(config_path)
        self._validator = ConfigValidator()
        # 延迟初始化其他组件
        self._agent_manager: Optional[Any] = None
        self._initializer: Optional[Any] = None

    def _resolve_path(self, path: Path | str | None) -> Path:
        """解析配置文件路径"""
        if path is None:
            env_path = os.environ.get("BASKET_SETTINGS_PATH")
            if env_path:
                return Path(env_path).expanduser().resolve()
            return (Path.home() / ".basket" / "settings.json").resolve()
        return Path(path).expanduser().resolve()

    # === 配置加载与保存 ===

    def load(self) -> Settings:
        """加载配置，带完整校验"""
        if not self.config_path.exists():
            logger.warning(f"配置文件不存在: {self.config_path}，返回默认配置")
            return Settings()

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            settings = Settings(**data)

            # 校验并打印警告
            errors, warnings = self._validator.validate_settings(settings)
            for error in errors:
                logger.error(error)
            for warning in warnings:
                logger.warning(warning)

            return settings

        except Exception as e:
            logger.error(f"加载配置失败: {e}，返回默认配置")
            return Settings()

    def save(self, settings: Settings) -> None:
        """保存配置，带校验"""
        # 校验
        errors, warnings = self._validator.validate_settings(settings)
        for error in errors:
            logger.error(error)
        for warning in warnings:
            logger.warning(warning)

        # 确保目录存在
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(settings.model_dump(), f, indent=2, ensure_ascii=False)

        logger.info(f"配置已保存到: {self.config_path}")

    def exists(self) -> bool:
        """检查配置文件是否存在"""
        return self.config_path.exists()

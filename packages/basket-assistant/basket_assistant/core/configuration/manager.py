"""ConfigurationManager - 统一配置管理入口"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import AgentConfig, AgentInfo, Settings
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
        # 延迟初始化其他组件（避免循环导入）
        self._agent_manager: Optional[Any] = None
        self._initializer: Optional[Any] = None

    def _get_agent_manager(self) -> Any:
        if self._agent_manager is None:
            from .agents import AgentManager
            self._agent_manager = AgentManager(self)
        return self._agent_manager

    def _get_initializer(self) -> Any:
        if self._initializer is None:
            from .initialization import ConfigInitializer
            self._initializer = ConfigInitializer(self)
        return self._initializer

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

    # === 初始化 ===

    def run_guided_init(self, force: bool = False) -> Settings:
        """运行交互式初始化向导，返回创建的配置。"""
        return self._get_initializer().run(force=force)

    # === 智能体管理 ===

    def list_agents(self) -> List[AgentInfo]:
        """列出所有子智能体。"""
        return self._get_agent_manager().list_agents()

    def add_agent(
        self,
        name: str,
        workspace_dir: Optional[str] = None,
        model: Optional[Dict[str, Any]] = None,
        tools: Optional[Dict[str, bool]] = None,
        force: bool = False,
    ) -> Settings:
        """添加子智能体，返回更新后的配置。"""
        return self._get_agent_manager().add_agent(
            name=name,
            workspace_dir=workspace_dir,
            model=model,
            tools=tools,
            force=force,
        )

    def remove_agent(self, name: str) -> Settings:
        """删除子智能体，返回更新后的配置。"""
        return self._get_agent_manager().remove_agent(name)

    def update_agent(self, name: str, **updates: Any) -> Settings:
        """更新子智能体配置，返回更新后的配置。"""
        return self._get_agent_manager().update_agent(name, **updates)

    # === 配置解析 ===

    def _resolve_agent_key(self, name: str | None) -> str:
        """解析智能体名称，返回配置中的 key（default_agent 或 name）。"""
        settings = self.load()
        key = (name or "").strip() or settings.default_agent
        if key:
            return key
        return "default"

    def get_agent_config(self, name: str | None = None) -> AgentConfig:
        """
        获取指定智能体的运行时配置（用于创建 LLM 客户端）。

        Args:
            name: 智能体名称，None 表示默认智能体

        Returns:
            AgentConfig（provider, base_url, api_key, model, temperature 等）

        Raises:
            KeyError: 智能体不存在
        """
        settings = self.load()
        key = self._resolve_agent_key(name)

        if settings.agents and key not in settings.agents:
            raise KeyError(f"Unknown agent: {key!r}. Known: {list(settings.agents.keys())}")

        top = settings.model
        provider = top.provider
        base_url = top.base_url or ""
        model_id = top.model_id
        temperature = top.temperature

        if settings.agents and key in settings.agents:
            sub = settings.agents[key]
            if sub.model and isinstance(sub.model, dict):
                provider = sub.model.get("provider", provider)
                base_url = sub.model.get("base_url") or base_url
                model_id = sub.model.get("model_id", model_id)
                temperature = sub.model.get("temperature", temperature)

        api_key = settings.api_keys.get(provider, "") or ""

        return AgentConfig(
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            model=model_id,
            temperature=temperature,
        )

    def get_model_config(self, agent_name: str | None = None) -> Dict[str, Any]:
        """
        获取模型配置（provider, model_id, base_url, context_window, max_tokens）。

        Args:
            agent_name: 智能体名称，None 表示默认

        Returns:
            字典，包含 provider, model_id, base_url, context_window, max_tokens
        """
        settings = self.load()
        key = self._resolve_agent_key(agent_name)

        if settings.agents and key in settings.agents:
            sub = settings.agents[key]
            if sub.model and isinstance(sub.model, dict):
                top = settings.model
                m = sub.model
                return {
                    "provider": m.get("provider", top.provider),
                    "model_id": m.get("model_id", top.model_id),
                    "base_url": m.get("base_url") or top.base_url,
                    "context_window": m.get("context_window", top.context_window),
                    "max_tokens": m.get("max_tokens", top.max_tokens),
                }

        top = settings.model
        return {
            "provider": top.provider,
            "model_id": top.model_id,
            "base_url": top.base_url,
            "context_window": top.context_window,
            "max_tokens": top.max_tokens,
        }

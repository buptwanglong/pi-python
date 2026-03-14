"""智能体管理：添加、删除、更新、列表"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .models import AgentInfo, Settings, SubAgentConfig

if TYPE_CHECKING:
    from .manager import ConfigurationManager

logger = logging.getLogger(__name__)


class AgentManager:
    """子智能体管理器"""

    def __init__(self, config_manager: ConfigurationManager):
        """
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager

    def list_agents(self) -> List[AgentInfo]:
        """
        列出所有子智能体

        Returns:
            智能体信息列表
        """
        settings = self.config_manager.load()

        agents = []
        for name, config in settings.agents.items():
            agents.append(
                AgentInfo(
                    name=name,
                    workspace_dir=config.workspace_dir,
                    has_model_override=config.model is not None,
                    tools=config.tools,
                )
            )

        return agents

    def add_agent(
        self,
        name: str,
        workspace_dir: Optional[str] = None,
        model: Optional[Dict[str, Any]] = None,
        tools: Optional[Dict[str, bool]] = None,
        force: bool = False,
    ) -> Settings:
        """
        添加子智能体

        Args:
            name: 智能体名称（小写字母、数字、连字符）
            workspace_dir: 工作区目录（可选，默认 ~/.basket/workspace/<name>）
            model: 模型配置覆盖（可选）
            tools: 工具配置覆盖（可选）
            force: 是否覆盖已存在的智能体

        Returns:
            更新后的配置

        Raises:
            ValidationError: 名称格式不正确
            AgentExistsError: 智能体已存在且 force=False
        """
        # 1. 验证名称格式
        from .validation import ConfigValidator

        validator = ConfigValidator()
        validator.validate_agent_name(name)

        # 2. 检查是否已存在
        settings = self.config_manager.load()
        if name in settings.agents and not force:
            raise AgentExistsError(name)

        # 3. 创建 workspace 目录（如果指定了）
        if workspace_dir:
            ws_path = Path(workspace_dir).expanduser()
            ws_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"创建工作区目录: {ws_path}")

            # 填充默认文件（如果目录是新创建的）
            self._populate_workspace(ws_path)
        else:
            # 使用默认路径
            default_ws = Path.home() / ".basket" / "workspace" / name
            workspace_dir = str(default_ws)
            default_ws.mkdir(parents=True, exist_ok=True)
            self._populate_workspace(default_ws)
            logger.info(f"创建默认工作区: {default_ws}")

        # 4. 构建新配置（不可变更新）
        new_agent_config = SubAgentConfig(
            workspace_dir=workspace_dir,
            model=model,
            tools=tools,
        )

        # 使用 model_copy 创建新配置
        new_agents = dict(settings.agents)
        new_agents[name] = new_agent_config

        new_settings = settings.model_copy(update={"agents": new_agents})

        # 5. 保存并返回
        self.config_manager.save(new_settings)
        logger.info(f"添加智能体 '{name}' 成功")

        return new_settings

    def remove_agent(self, name: str) -> Settings:
        """
        删除子智能体

        Args:
            name: 智能体名称

        Returns:
            更新后的配置

        Raises:
            AgentNotFoundError: 智能体不存在
            CannotRemoveDefaultAgentError: 尝试删除默认智能体
        """
        # 加载当前配置
        settings = self.config_manager.load()

        # 检查智能体是否存在
        if name not in settings.agents:
            raise AgentNotFoundError(name)

        # 检查是否为默认智能体
        if settings.default_agent == name:
            raise CannotRemoveDefaultAgentError(name)

        # 不可变更新：创建新字典（去除指定智能体）
        new_agents = {k: v for k, v in settings.agents.items() if k != name}

        # 创建新配置
        new_settings = settings.model_copy(update={"agents": new_agents})

        # 保存并返回
        self.config_manager.save(new_settings)
        logger.info(f"删除智能体 '{name}' 成功")

        return new_settings

    def update_agent(self, name: str, **updates: Any) -> Settings:
        """
        更新子智能体配置

        仅更新提供的字段，未提供的字段保持不变。
        传入 None 可以清除可选字段。

        Args:
            name: 智能体名称
            **updates: 要更新的字段（workspace_dir, model, tools）

        Returns:
            更新后的配置

        Raises:
            AgentNotFoundError: 智能体不存在
            ValueError: 传入了不支持的字段
        """
        # 加载当前配置
        settings = self.config_manager.load()

        # 检查智能体是否存在
        if name not in settings.agents:
            raise AgentNotFoundError(name)

        # 验证更新字段
        allowed_fields = {"workspace_dir", "model", "tools"}
        invalid_fields = set(updates.keys()) - allowed_fields
        if invalid_fields:
            raise ValueError(f"不支持更新以下字段: {', '.join(invalid_fields)}")

        # 获取当前配置并更新
        current_config = settings.agents[name]
        new_config_dict = current_config.model_dump()
        new_config_dict.update(updates)

        # 创建新的 SubAgentConfig
        new_agent_config = SubAgentConfig(**new_config_dict)

        # 不可变更新
        new_agents = dict(settings.agents)
        new_agents[name] = new_agent_config

        new_settings = settings.model_copy(update={"agents": new_agents})

        # 保存并返回
        self.config_manager.save(new_settings)
        logger.info(f"更新智能体 '{name}' 成功")

        return new_settings

    def _populate_workspace(self, workspace_path: Path) -> None:
        """
        填充工作区默认文件

        Args:
            workspace_path: 工作区路径
        """
        # 检查是否已有文件
        identity_file = workspace_path / "IDENTITY.md"
        if identity_file.exists():
            return  # 已有内容，不覆盖

        # 创建 IDENTITY.md
        identity_content = """# Agent Identity

This is a placeholder identity file for the agent.

You can customize this file to define the agent's:
- Role and responsibilities
- Capabilities and limitations
- Working style and preferences
"""
        identity_file.write_text(identity_content, encoding="utf-8")
        logger.debug(f"创建 IDENTITY.md: {identity_file}")

        # 创建 README.md
        readme_file = workspace_path / "README.md"
        readme_content = """# Agent Workspace

This workspace is used by the agent for:
- Session data
- Temporary files
- Agent-specific configurations
"""
        readme_file.write_text(readme_content, encoding="utf-8")
        logger.debug(f"创建 README.md: {readme_file}")


# === 异常类型 ===


class AgentError(Exception):
    """智能体操作基础异常"""

    pass


class AgentExistsError(AgentError):
    """智能体已存在"""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"智能体 '{name}' 已存在")


class AgentNotFoundError(AgentError):
    """智能体不存在"""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"智能体 '{name}' 不存在")


class CannotRemoveDefaultAgentError(AgentError):
    """不能删除默认智能体"""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"不能删除默认智能体 '{name}'，请先修改 default_agent 配置")

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

"""配置数据模型

定义所有配置相关的 Pydantic 数据模型，提供类型安全和验证。
"""
from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator


class ModelSettings(BaseModel):
    """模型配置"""

    model_config = {"frozen": True}

    provider: str = Field(default="openai", description="LLM provider name")
    model_id: str = Field(default="gpt-4o-mini", description="Model identifier")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=4096, gt=0, description="Maximum tokens to generate")
    context_window: int = Field(default=128000, gt=0, description="Context window size")
    base_url: Optional[str] = Field(default=None, description="Custom API base URL")


class AgentSettings(BaseModel):
    """Agent 行为配置"""

    model_config = {"frozen": True}

    max_turns: int = Field(default=10, gt=0, description="Maximum tool execution rounds")
    auto_save: bool = Field(default=True, description="Auto-save sessions")
    verbose: bool = Field(default=False, description="Enable verbose debug output")


class PermissionsSettings(BaseModel):
    """权限配置"""

    model_config = {"frozen": True}

    default_mode: str = Field(
        default="default",
        description="Default permission mode: 'default', 'auto', 'deny'"
    )


class SubAgentConfig(BaseModel):
    """SubAgent 配置（可选覆盖主配置）"""

    model_config = {"frozen": True}

    model: Optional[dict[str, Any]] = Field(
        default=None,
        description="Model override (partial ModelSettings)"
    )
    tools: Optional[dict[str, Any]] = Field(
        default=None,
        description="Tool availability override"
    )
    agent_dir: Optional[str] = Field(
        default=None,
        description="Custom agent directory path"
    )
    workspace_dir: Optional[str] = Field(
        default=None,
        description="Custom workspace directory path"
    )


class Settings(BaseModel):
    """完整的配置模型（对应 settings.json）"""

    model_config = {"frozen": True}

    model: ModelSettings = Field(default_factory=ModelSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    permissions: PermissionsSettings = Field(default_factory=PermissionsSettings)
    api_keys: dict[str, str] = Field(default_factory=dict, description="API keys by provider")
    sessions_dir: str = Field(default="~/.basket/sessions", description="Sessions directory")
    trajectory_dir: str = Field(
        default="~/.basket/trajectories",
        description="Trajectories directory"
    )
    agents: dict[str, SubAgentConfig] = Field(
        default_factory=dict,
        description="SubAgent configurations"
    )
    default_agent: Optional[str] = Field(
        default=None,
        description="Default agent name (must exist in agents)"
    )
    workspace_dir: Optional[str] = Field(
        default=None,
        description="Workspace directory for OpenClaw-style identity files",
    )
    web_search_provider: Optional[str] = Field(
        default=None,
        description="Web search provider: None/duckduckgo or 'serper'",
    )

    @model_validator(mode="after")
    def _validate_agents(self) -> "Settings":
        """校验 default_agent 必须存在于 agents 中"""
        if self.default_agent is not None and self.default_agent not in self.agents:
            raise ValueError(
                f"default_agent '{self.default_agent}' not found in agents: "
                f"{list(self.agents.keys())}"
            )
        return self


class AgentConfig(BaseModel):
    """Agent 运行时配置（合并后的最终配置）"""

    model_config = {"frozen": True}

    provider: str
    base_url: Optional[str] = None
    api_key: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    context_window: int = 128000


class AgentInfo(BaseModel):
    """Agent 信息（用于展示）"""

    model_config = {"frozen": True}

    name: str
    workspace_dir: Optional[str] = None
    has_model_override: bool = False
    tools: Optional[dict[str, Any]] = None

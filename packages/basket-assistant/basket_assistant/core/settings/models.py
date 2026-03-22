"""
Settings Pydantic models: AgentConfig, ModelSettings, AgentSettings,
PermissionsSettings, SubAgentConfig, Settings.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

DEFAULT_TRAJECTORY_DIR = "~/.basket/trajectories"


# ========================================================================
# Agent Config (Simple multi-agent support)
# ========================================================================


class AgentConfig(BaseModel):
    """Per-agent LLM config: provider, base_url, api_key, etc."""

    provider: str = "openai"
    base_url: str = ""
    api_key: str = ""
    model: Optional[str] = None
    temperature: Optional[float] = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AgentConfig":
        """Create AgentConfig from dict (for legacy migration)."""
        return cls(
            provider=d.get("provider", "openai"),
            base_url=d.get("base_url", ""),
            api_key=d.get("api_key", ""),
            model=d.get("model"),
            temperature=d.get("temperature"),
        )


# ========================================================================
# Settings Models
# ========================================================================


class ModelSettings(BaseModel):
    """Model configuration settings."""

    provider: str = "openai"
    model_id: str = "gpt-4o-mini"
    temperature: float = 0.7
    """Maximum output tokens per response (max_tokens / max_output_tokens)."""
    max_tokens: int = 4096
    """Model context window size in tokens (input + output limit)."""
    context_window: int = 128000
    base_url: Optional[str] = None


class AgentSettings(BaseModel):
    """Agent behavior settings."""

    max_turns: int = 10
    auto_save: bool = True
    verbose: bool = False


class PermissionsSettings(BaseModel):
    """Permission mode settings (e.g. plan mode = read-only)."""

    default_mode: Literal["default", "plan"] = "default"


class SubAgentConfig(BaseModel):
    """Configuration for a subagent (used by the Task tool).
    System prompt comes from workspace (AGENTS.md, IDENTITY.md, etc.); display label from AGENTS.md first line.
    """

    model_config = {"extra": "ignore"}  # allow old configs with description/prompt to load

    model: Optional[Dict[str, Any]] = Field(None, description="Optional model override")
    tools: Optional[Dict[str, bool]] = Field(None, description="Tool name -> enabled")
    agent_dir: Optional[str] = Field(
        None,
        description="Agent root directory (parent of workspace/, sessions/); when set, workspace_dir defaults to agent_dir/workspace if workspace_dir is unset",
    )
    workspace_dir: Optional[str] = Field(
        None,
        description="Workspace directory for OpenClaw-style md files; when unset, uses agent_dir/workspace or ~/.basket/agents/<name>/workspace",
    )


class Settings(BaseModel):
    """Global settings for the coding agent (Pydantic schema)."""

    model: ModelSettings = Field(default_factory=ModelSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    permissions: PermissionsSettings = Field(default_factory=PermissionsSettings)
    api_keys: Dict[str, str] = Field(default_factory=dict)
    sessions_dir: str = "~/.basket/sessions"
    trajectory_dir: Optional[str] = Field(
        default=None,
        description="Directory for trajectory recording; default filled at load time with ~/.basket/trajectories. Set to empty to disable.",
    )
    log_level: Optional[str] = Field(
        default=None,
        description="Global log level for all basket modules (DEBUG/INFO/WARNING/ERROR). Overridden by BASKET_LOG_LEVEL env var.",
    )
    skills_dirs: List[str] = Field(default_factory=list)
    skills_include: List[str] = Field(default_factory=list)
    agents: Dict[str, SubAgentConfig] = Field(default_factory=dict)
    agents_dirs: List[str] = Field(default_factory=list)
    default_agent: Optional[str] = Field(
        default=None,
        description="Main agent name. When set and present in agents with model, main agent uses that model; otherwise uses top-level model.",
    )
    workspace_dir: Optional[str] = None
    skip_bootstrap: bool = False
    web_search_provider: Optional[str] = None
    serve: Optional[Dict[str, Any]] = None
    relay_url: Optional[str] = None
    hooks: Optional[Dict[str, List[Dict[str, Any]]]] = None
    custom: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _fill_trajectory_dir_default(self) -> "Settings":
        """Set trajectory_dir to default at config time when None (not when reading)."""
        if self.trajectory_dir is None:
            object.__setattr__(self, "trajectory_dir", DEFAULT_TRAJECTORY_DIR)
        return self

    def resolve_agent(self, name: str | None = None) -> AgentConfig:
        """
        Resolve agent by name (for backward compatibility with tests).

        Args:
            name: Agent name (None uses default_agent)

        Returns:
            AgentConfig for the specified agent
        """
        # Convert SubAgentConfig to AgentConfig for multi-agent settings
        if not self.agents:
            # No agents configured, return default
            return AgentConfig(
                provider=self.model.provider,
                base_url=self.model.base_url or "",
                api_key="",
                model=self.model.model_id,
                temperature=self.model.temperature,
            )

        # Use default_agent if name is None or empty
        key = (name or "").strip() or self.default_agent or "default"

        if key not in self.agents:
            raise KeyError(f"Unknown agent: {key!r}. Known: {list(self.agents.keys())}")

        # Get SubAgentConfig and convert to simple AgentConfig
        subagent = self.agents[key]
        if subagent.model and isinstance(subagent.model, dict):
            # Agent has model override
            return AgentConfig(
                provider=subagent.model.get("provider", self.model.provider),
                base_url=subagent.model.get("base_url", self.model.base_url or ""),
                api_key=subagent.model.get("api_key", ""),
                model=subagent.model.get("model_id", self.model.model_id),
                temperature=subagent.model.get("temperature", self.model.temperature),
            )

        # No model override, use top-level settings
        return AgentConfig(
            provider=self.model.provider,
            base_url=self.model.base_url or "",
            api_key="",
            model=self.model.model_id,
            temperature=self.model.temperature,
        )

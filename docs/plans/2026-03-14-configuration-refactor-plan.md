# Configuration Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重构配置管理代码，创建统一的 ConfigurationManager，优化初始化体验

**Architecture:** 创建 `core/configuration/` 模块，包含 models、validation、loaders、agents、initialization、manager 六个子模块。使用组合模式，ConfigurationManager 协调各子模块。遵循不可变性原则，所有修改返回新对象。

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, questionary (UI)

---

## Phase 1: 基础设施 - Models & Validation

### Task 1: 创建 configuration 模块目录结构

**Files:**
- Create: `packages/basket-assistant/basket_assistant/core/configuration/__init__.py`
- Create: `packages/basket-assistant/basket_assistant/core/configuration/models.py`
- Create: `packages/basket-assistant/basket_assistant/core/configuration/validation.py`
- Create: `packages/basket-assistant/basket_assistant/core/configuration/loaders.py`
- Create: `packages/basket-assistant/basket_assistant/core/configuration/agents.py`
- Create: `packages/basket-assistant/basket_assistant/core/configuration/initialization.py`
- Create: `packages/basket-assistant/basket_assistant/core/configuration/manager.py`

**Step 1: 创建目录和空文件**

```bash
mkdir -p packages/basket-assistant/basket_assistant/core/configuration
touch packages/basket-assistant/basket_assistant/core/configuration/__init__.py
touch packages/basket-assistant/basket_assistant/core/configuration/models.py
touch packages/basket-assistant/basket_assistant/core/configuration/validation.py
touch packages/basket-assistant/basket_assistant/core/configuration/loaders.py
touch packages/basket-assistant/basket_assistant/core/configuration/agents.py
touch packages/basket-assistant/basket_assistant/core/configuration/initialization.py
touch packages/basket-assistant/basket_assistant/core/configuration/manager.py
```

**Step 2: 提交目录结构**

```bash
cd packages/basket-assistant
git add basket_assistant/core/configuration/
git commit -m "chore: create configuration module structure"
```

---

### Task 2: 实现 models.py - 数据模型

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/core/configuration/models.py`
- Create: `packages/basket-assistant/tests/core/configuration/test_models.py`

**Step 1: 写测试 - 基础模型**

Create: `packages/basket-assistant/tests/core/configuration/__init__.py`
Create: `packages/basket-assistant/tests/core/configuration/test_models.py`

```python
"""测试配置数据模型"""
import pytest
from pydantic import ValidationError

from basket_assistant.core.configuration.models import (
    ModelSettings,
    AgentSettings,
    PermissionsSettings,
    SubAgentConfig,
    Settings,
    AgentConfig,
    AgentInfo,
)


def test_model_settings_defaults():
    """测试 ModelSettings 默认值"""
    settings = ModelSettings()
    assert settings.provider == "openai"
    assert settings.model_id == "gpt-4o-mini"
    assert settings.temperature == 0.7
    assert settings.max_tokens == 4096
    assert settings.context_window == 128000
    assert settings.base_url is None


def test_model_settings_custom():
    """测试 ModelSettings 自定义值"""
    settings = ModelSettings(
        provider="anthropic",
        model_id="claude-sonnet-4",
        base_url="https://custom.api"
    )
    assert settings.provider == "anthropic"
    assert settings.model_id == "claude-sonnet-4"
    assert settings.base_url == "https://custom.api"


def test_agent_settings_defaults():
    """测试 AgentSettings 默认值"""
    settings = AgentSettings()
    assert settings.max_turns == 10
    assert settings.auto_save is True
    assert settings.verbose is False


def test_permissions_settings_defaults():
    """测试 PermissionsSettings 默认值"""
    settings = PermissionsSettings()
    assert settings.default_mode == "default"


def test_sub_agent_config_optional_fields():
    """测试 SubAgentConfig 可选字段"""
    config = SubAgentConfig()
    assert config.model is None
    assert config.tools is None
    assert config.agent_dir is None
    assert config.workspace_dir is None


def test_sub_agent_config_with_values():
    """测试 SubAgentConfig 带值"""
    config = SubAgentConfig(
        model={"provider": "openai", "model_id": "gpt-4"},
        tools={"read": True, "write": False},
        workspace_dir="/path/to/workspace"
    )
    assert config.model == {"provider": "openai", "model_id": "gpt-4"}
    assert config.tools == {"read": True, "write": False}
    assert config.workspace_dir == "/path/to/workspace"


def test_settings_defaults():
    """测试 Settings 默认值"""
    settings = Settings()
    assert settings.model.provider == "openai"
    assert settings.agent.max_turns == 10
    assert settings.permissions.default_mode == "default"
    assert settings.api_keys == {}
    assert settings.sessions_dir == "~/.basket/sessions"
    assert settings.trajectory_dir == "~/.basket/trajectories"
    assert settings.agents == {}
    assert settings.default_agent is None


def test_settings_validate_agents_consistency():
    """测试 Settings 校验 agents 和 default_agent 一致性"""
    # default_agent 存在于 agents 中 - 正常
    settings = Settings(
        default_agent="main",
        agents={"main": SubAgentConfig()}
    )
    assert settings.default_agent == "main"

    # default_agent 不存在于 agents 中 - 抛出异常
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            default_agent="main",
            agents={"other": SubAgentConfig()}
        )
    assert "default_agent" in str(exc_info.value).lower()


def test_agent_config():
    """测试 AgentConfig 运行时配置"""
    config = AgentConfig(
        provider="anthropic",
        base_url="https://api.anthropic.com",
        api_key="sk-ant-xxx",
        model="claude-sonnet-4",
        temperature=0.8
    )
    assert config.provider == "anthropic"
    assert config.base_url == "https://api.anthropic.com"
    assert config.model == "claude-sonnet-4"


def test_agent_info():
    """测试 AgentInfo 展示模型"""
    info = AgentInfo(
        name="test-agent",
        workspace_dir="/path/to/workspace",
        has_model_override=True,
        tools={"read": True}
    )
    assert info.name == "test-agent"
    assert info.workspace_dir == "/path/to/workspace"
    assert info.has_model_override is True
    assert info.tools == {"read": True}
```

**Step 2: 运行测试（应该失败）**

```bash
cd packages/basket-assistant
poetry run pytest tests/core/configuration/test_models.py -v
```

Expected: ImportError - models.py 还未实现

**Step 3: 实现 models.py**

```python
"""配置数据模型：Settings, SubAgentConfig, AgentConfig 等"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


# === 基础模型 ===

class ModelSettings(BaseModel):
    """LLM 模型配置"""
    provider: str = "openai"
    model_id: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 4096
    context_window: int = 128000
    base_url: Optional[str] = None


class AgentSettings(BaseModel):
    """智能体行为配置"""
    max_turns: int = 10
    auto_save: bool = True
    verbose: bool = False


class PermissionsSettings(BaseModel):
    """权限模式配置"""
    default_mode: Literal["default", "plan"] = "default"


class SubAgentConfig(BaseModel):
    """子智能体配置（Task 工具使用）"""
    model_config = {"extra": "ignore"}

    model: Optional[Dict[str, Any]] = Field(None, description="模型覆盖配置")
    tools: Optional[Dict[str, bool]] = Field(None, description="工具启用状态")
    agent_dir: Optional[str] = Field(None, description="智能体根目录")
    workspace_dir: Optional[str] = Field(None, description="工作区目录（OpenClaw 风格）")


# === 主配置模型 ===

class Settings(BaseModel):
    """全局配置（从 settings.json 加载）"""

    model: ModelSettings = Field(default_factory=ModelSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    permissions: PermissionsSettings = Field(default_factory=PermissionsSettings)
    api_keys: Dict[str, str] = Field(default_factory=dict)
    sessions_dir: str = "~/.basket/sessions"
    trajectory_dir: Optional[str] = "~/.basket/trajectories"
    skills_dirs: List[str] = Field(default_factory=list)
    skills_include: List[str] = Field(default_factory=list)
    agents: Dict[str, SubAgentConfig] = Field(default_factory=dict)
    agents_dirs: List[str] = Field(default_factory=list)
    default_agent: Optional[str] = None
    workspace_dir: Optional[str] = None
    skip_bootstrap: bool = False
    web_search_provider: Optional[str] = None
    serve: Optional[Dict[str, Any]] = None
    relay_url: Optional[str] = None
    hooks: Optional[Dict[str, List[Dict[str, Any]]]] = None
    custom: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_agents(self) -> "Settings":
        """校验 agents 和 default_agent 的一致性"""
        if self.default_agent and self.default_agent not in self.agents:
            raise ValueError(
                f"default_agent '{self.default_agent}' 不在 agents 中: {list(self.agents.keys())}"
            )
        return self


# === 运行时模型 ===

class AgentConfig(BaseModel):
    """运行时智能体配置（解析后用于创建 LLM 客户端）"""
    provider: str = "openai"
    base_url: str = ""
    api_key: str = ""
    model: Optional[str] = None
    temperature: Optional[float] = None


class AgentInfo(BaseModel):
    """智能体信息（用于列表展示）"""
    name: str
    workspace_dir: Optional[str] = None
    has_model_override: bool = False
    tools: Optional[Dict[str, bool]] = None
```

**Step 4: 运行测试（应该通过）**

```bash
poetry run pytest tests/core/configuration/test_models.py -v
```

Expected: All tests PASS

**Step 5: 提交**

```bash
git add basket_assistant/core/configuration/models.py tests/core/configuration/
git commit -m "feat(config): implement data models with validation"
```

---

### Task 3: 实现 validation.py - 配置校验

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/core/configuration/validation.py`
- Create: `packages/basket-assistant/tests/core/configuration/test_validation.py`

**Step 1: 写测试 - 校验器**

```python
"""测试配置校验逻辑"""
import pytest

from basket_assistant.core.configuration.models import Settings, SubAgentConfig
from basket_assistant.core.configuration.validation import (
    ConfigValidator,
    ValidationError,
    ValidationWarning,
)


def test_validate_agent_name_valid():
    """测试合法的智能体名称"""
    validator = ConfigValidator()

    # 合法名称
    validator.validate_agent_name("test-agent")
    validator.validate_agent_name("my-agent-v2")
    validator.validate_agent_name("agent123")


def test_validate_agent_name_invalid():
    """测试非法的智能体名称"""
    validator = ConfigValidator()

    # 空名称
    with pytest.raises(ValidationError) as exc:
        validator.validate_agent_name("")
    assert "不能为空" in str(exc.value)

    # 大写字母
    with pytest.raises(ValidationError) as exc:
        validator.validate_agent_name("MyAgent")
    assert "格式不正确" in str(exc.value)

    # 下划线
    with pytest.raises(ValidationError) as exc:
        validator.validate_agent_name("my_agent")
    assert "格式不正确" in str(exc.value)

    # 以连字符开头
    with pytest.raises(ValidationError) as exc:
        validator.validate_agent_name("-agent")
    assert "格式不正确" in str(exc.value)

    # 过长
    with pytest.raises(ValidationError) as exc:
        validator.validate_agent_name("a" * 65)
    assert "过长" in str(exc.value)


def test_validate_api_key():
    """测试 API Key 格式校验"""
    validator = ConfigValidator()

    # OpenAI - 合法
    assert validator.validate_api_key("sk-" + "x" * 48, "openai") is None

    # OpenAI - 非法
    error = validator.validate_api_key("invalid-key", "openai")
    assert error is not None
    assert "sk-" in error

    # Anthropic - 合法
    assert validator.validate_api_key("sk-ant-" + "x" * 95, "anthropic") is None

    # 空 key
    error = validator.validate_api_key("", "openai")
    assert "不能为空" in error


def test_validate_model_id():
    """测试模型 ID 校验"""
    validator = ConfigValidator()

    # 已知模型 - 无警告
    assert validator.validate_model_id("gpt-4o", "openai") is None
    assert validator.validate_model_id("claude-sonnet-4-20250514", "anthropic") is None

    # 未知模型 - 有警告
    warning = validator.validate_model_id("unknown-model", "openai")
    assert warning is not None
    assert "未知" in warning or "常用模型" in warning


def test_validate_settings():
    """测试完整配置校验"""
    validator = ConfigValidator()

    # 正常配置 - 无警告
    settings = Settings()
    warnings = validator.validate_settings(settings)
    assert len(warnings) == 0

    # default_agent 不在 agents 中 - 有警告（但不抛出异常，因为 Pydantic 已经校验过）
    # 这里测试其他警告情况

    # Base URL 格式不正确
    settings = Settings(model={"base_url": "invalid-url"})
    warnings = validator.validate_settings(settings)
    # 应该有关于 base_url 的警告
    url_warnings = [w for w in warnings if "base_url" in w.field]
    assert len(url_warnings) > 0


def test_validation_warning_format():
    """测试 ValidationWarning 格式化"""
    warning = ValidationWarning(
        field="test_field",
        message="测试消息",
        suggestion="测试建议"
    )

    formatted = warning.format()
    assert "⚠️" in formatted
    assert "test_field" in formatted
    assert "测试消息" in formatted
    assert "测试建议" in formatted
```

**Step 2: 运行测试（应该失败）**

```bash
poetry run pytest tests/core/configuration/test_validation.py -v
```

Expected: ImportError - validation.py 还未实现

**Step 3: 实现 validation.py**

```python
"""配置校验：格式检查、一致性验证、友好错误提示"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .models import Settings, SubAgentConfig


class ConfigValidator:
    """配置验证器"""

    # 智能体名称规范：小写字母、数字、连字符
    AGENT_NAME_PATTERN = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')

    # API Key 格式规则
    API_KEY_PATTERNS = {
        "openai": re.compile(r'^sk-[A-Za-z0-9]{48}$'),
        "anthropic": re.compile(r'^sk-ant-[A-Za-z0-9\-_]{95,}$'),
        "google": re.compile(r'^[A-Za-z0-9_\-]{39}$'),
    }

    def validate_settings(self, settings: Settings) -> list[ValidationWarning]:
        """
        全面校验配置

        Returns:
            警告列表（不阻断保存，但提示用户）
        """
        warnings = []

        # 1. 校验 agents 和 default_agent 一致性
        if settings.default_agent:
            if not settings.agents:
                warnings.append(ValidationWarning(
                    field="default_agent",
                    message=f"default_agent 设置为 '{settings.default_agent}'，但 agents 为空",
                    suggestion="移除 default_agent 或添加对应的智能体配置"
                ))
            elif settings.default_agent not in settings.agents:
                warnings.append(ValidationWarning(
                    field="default_agent",
                    message=f"default_agent '{settings.default_agent}' 不在 agents 中",
                    suggestion=f"可用的智能体: {', '.join(settings.agents.keys())}"
                ))

        # 2. 校验 API Keys
        for key_name, key_value in settings.api_keys.items():
            if not key_value or not key_value.strip():
                warnings.append(ValidationWarning(
                    field=f"api_keys.{key_name}",
                    message=f"API Key '{key_name}' 为空",
                    suggestion="从环境变量读取或移除此配置"
                ))

        # 3. 校验 Base URL
        if settings.model.base_url:
            if not self._is_valid_url(settings.model.base_url):
                warnings.append(ValidationWarning(
                    field="model.base_url",
                    message=f"Base URL 格式可能不正确: {settings.model.base_url}",
                    suggestion="应该是完整的 HTTP/HTTPS URL"
                ))

        # 4. 校验各智能体配置
        for name, agent_cfg in settings.agents.items():
            agent_warnings = self._validate_agent_config(name, agent_cfg)
            warnings.extend(agent_warnings)

        # 5. 校验路径存在性
        if settings.workspace_dir:
            workspace_path = Path(settings.workspace_dir).expanduser()
            if not workspace_path.exists():
                warnings.append(ValidationWarning(
                    field="workspace_dir",
                    message=f"工作区目录不存在: {workspace_path}",
                    suggestion="目录将在首次使用时自动创建"
                ))

        return warnings

    def validate_agent_name(self, name: str) -> None:
        """
        校验智能体名称格式

        Raises:
            ValidationError: 名称格式不正确
        """
        if not name or not name.strip():
            raise ValidationError(
                field="agent_name",
                message="智能体名称不能为空"
            )

        if not self.AGENT_NAME_PATTERN.match(name):
            raise ValidationError(
                field="agent_name",
                message=f"智能体名称格式不正确: '{name}'",
                suggestion="只能包含小写字母、数字和连字符，且不能以连字符开头或结尾。例如: my-agent, agent-v2"
            )

        if len(name) > 64:
            raise ValidationError(
                field="agent_name",
                message=f"智能体名称过长: {len(name)} 字符",
                suggestion="名称长度应小于 64 字符"
            )

    def validate_api_key(self, key: str, provider: str) -> Optional[str]:
        """
        校验 API Key 格式

        Returns:
            错误消息，None 表示校验通过
        """
        if not key or not key.strip():
            return "API Key 不能为空"

        pattern = self.API_KEY_PATTERNS.get(provider)
        if pattern and not pattern.match(key):
            return self._get_api_key_format_hint(provider)

        return None

    def validate_model_id(self, model_id: str, provider: str) -> Optional[str]:
        """
        校验模型 ID 是否合理

        Returns:
            警告消息，None 表示校验通过
        """
        known_models = {
            "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
            "anthropic": [
                "claude-sonnet-4-20250514",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229"
            ],
            "google": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        }

        provider_models = known_models.get(provider, [])
        if provider_models and model_id not in provider_models:
            return f"未知的模型 ID '{model_id}'。常用模型: {', '.join(provider_models[:3])}"

        return None

    # === 私有辅助方法 ===

    def _validate_agent_config(
        self,
        name: str,
        config: SubAgentConfig
    ) -> list[ValidationWarning]:
        """校验单个智能体配置"""
        warnings = []

        # 校验 workspace_dir
        if config.workspace_dir:
            ws_path = Path(config.workspace_dir).expanduser()
            if not ws_path.exists():
                warnings.append(ValidationWarning(
                    field=f"agents.{name}.workspace_dir",
                    message=f"工作区目录不存在: {ws_path}",
                    suggestion="目录将在首次使用时自动创建"
                ))

        # 校验 model 覆盖配置
        if config.model:
            if "provider" in config.model and "model_id" not in config.model:
                warnings.append(ValidationWarning(
                    field=f"agents.{name}.model",
                    message="指定了 provider 但未指定 model_id",
                    suggestion="添加 model_id 字段或移除 provider"
                ))

        return warnings

    def _is_valid_url(self, url: str) -> bool:
        """检查 URL 格式是否合法"""
        try:
            result = urlparse(url)
            return all([result.scheme in ("http", "https"), result.netloc])
        except Exception:
            return False

    def _get_api_key_format_hint(self, provider: str) -> str:
        """获取 API Key 格式提示"""
        hints = {
            "openai": "OpenAI API Key 应该以 'sk-' 开头，长度约 51 字符",
            "anthropic": "Anthropic API Key 应该以 'sk-ant-' 开头",
            "google": "Google API Key 长度约 39 字符",
        }
        return hints.get(provider, f"API Key 格式不正确 (provider: {provider})")


# === 异常和警告类型 ===

class ValidationError(Exception):
    """配置校验错误（阻断操作）"""

    def __init__(self, field: str, message: str, suggestion: str = ""):
        self.field = field
        self.message = message
        self.suggestion = suggestion
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        msg = f"[{self.field}] {self.message}"
        if self.suggestion:
            msg += f"\n建议: {self.suggestion}"
        return msg


class ValidationWarning:
    """配置校验警告（不阻断操作，但提示用户）"""

    def __init__(self, field: str, message: str, suggestion: str = ""):
        self.field = field
        self.message = message
        self.suggestion = suggestion

    def format(self) -> str:
        msg = f"⚠️  [{self.field}] {self.message}"
        if self.suggestion:
            msg += f"\n   建议: {self.suggestion}"
        return msg

    def __str__(self) -> str:
        return self.format()
```

**Step 4: 运行测试（应该通过）**

```bash
poetry run pytest tests/core/configuration/test_validation.py -v
```

Expected: All tests PASS

**Step 5: 提交**

```bash
git add basket_assistant/core/configuration/validation.py tests/core/configuration/test_validation.py
git commit -m "feat(config): implement validation logic with friendly errors"
```

---

### Task 4: 实现 loaders.py - 文件系统加载

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/core/configuration/loaders.py`
- Create: `packages/basket-assistant/tests/core/configuration/test_loaders.py`

**Step 1: 从现有代码迁移并测试**

复制 `core/agents_loader.py` 的逻辑到 `loaders.py`，调整导入路径，确保测试通过。

```bash
# 复制现有测试作为基础
cp tests/test_agents_loader.py tests/core/configuration/test_loaders.py
```

**Step 2: 更新测试导入**

修改 `tests/core/configuration/test_loaders.py`，将导入改为：

```python
from basket_assistant.core.configuration.loaders import AgentLoader
from basket_assistant.core.configuration.models import SubAgentConfig
```

**Step 3: 运行测试（应该失败）**

```bash
poetry run pytest tests/core/configuration/test_loaders.py -v
```

**Step 4: 实现 loaders.py**

将 `core/agents_loader.py` 的代码迁移到 `loaders.py`，更新导入：

```python
"""从文件系统加载智能体配置（.md 文件或目录）"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import SubAgentConfig

logger = logging.getLogger(__name__)

# OpenClaw 风格工作区标记文件
WORKSPACE_MARKER_FILES = ("AGENTS.md", "IDENTITY.md")


class AgentLoader:
    """从文件系统加载智能体配置"""

    @staticmethod
    def load_from_dirs(dirs: List[Path]) -> Dict[str, SubAgentConfig]:
        """
        从目录列表扫描并加载智能体

        支持两种格式：
        1. 目录型：包含 AGENTS.md 或 IDENTITY.md 的子目录
        2. 单文件型：*.md 文件，带 YAML frontmatter

        优先级：后面的目录覆盖前面的；同名时目录型优先于单文件型
        """
        # ... 实现（从 agents_loader.py 复制）
```

**Step 5: 运行测试（应该通过）**

```bash
poetry run pytest tests/core/configuration/test_loaders.py -v
```

**Step 6: 提交**

```bash
git add basket_assistant/core/configuration/loaders.py tests/core/configuration/test_loaders.py
git commit -m "feat(config): implement agent loader from filesystem"
```

---

## Phase 2: 核心功能 - Manager & Agents

### Task 5: 实现 manager.py - ConfigurationManager（基础）

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/core/configuration/manager.py`
- Create: `packages/basket-assistant/tests/core/configuration/test_manager.py`

**Step 1: 写测试 - 基础功能**

```python
"""测试 ConfigurationManager"""
import json
import pytest
from pathlib import Path

from basket_assistant.core.configuration import ConfigurationManager
from basket_assistant.core.configuration.models import Settings


def test_manager_init_default_path(tmp_path):
    """测试 Manager 默认路径"""
    manager = ConfigurationManager()
    assert manager.config_path is not None


def test_manager_init_custom_path(tmp_path):
    """测试 Manager 自定义路径"""
    config_path = tmp_path / "custom_settings.json"
    manager = ConfigurationManager(config_path)
    assert manager.config_path == config_path


def test_manager_exists(tmp_path):
    """测试配置文件存在性检查"""
    config_path = tmp_path / "settings.json"
    manager = ConfigurationManager(config_path)

    assert not manager.exists()

    config_path.write_text("{}")
    assert manager.exists()


def test_manager_save_and_load(tmp_path):
    """测试保存和加载配置"""
    config_path = tmp_path / "settings.json"
    manager = ConfigurationManager(config_path)

    # 保存配置
    settings = Settings(
        model={"provider": "anthropic", "model_id": "claude-sonnet-4"}
    )
    manager.save(settings)

    # 加载配置
    loaded = manager.load()
    assert loaded.model.provider == "anthropic"
    assert loaded.model.model_id == "claude-sonnet-4"


def test_manager_load_nonexistent_returns_default(tmp_path):
    """测试加载不存在的配置返回默认值"""
    config_path = tmp_path / "nonexistent.json"
    manager = ConfigurationManager(config_path)

    settings = manager.load()
    assert settings.model.provider == "openai"  # 默认值
```

**Step 2: 运行测试（应该失败）**

```bash
poetry run pytest tests/core/configuration/test_manager.py::test_manager_init_default_path -v
```

**Step 3: 实现 manager.py - 基础部分**

```python
"""ConfigurationManager - 统一配置管理入口"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Settings, AgentConfig, AgentInfo
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
        self._agent_manager: Optional[AgentManager] = None
        self._initializer: Optional[ConfigInitializer] = None

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
            warnings = self._validator.validate_settings(settings)
            for warning in warnings:
                logger.warning(warning.format())

            return settings

        except Exception as e:
            logger.error(f"加载配置失败: {e}，返回默认配置")
            return Settings()

    def save(self, settings: Settings) -> None:
        """保存配置，带校验"""
        # 校验
        warnings = self._validator.validate_settings(settings)
        for warning in warnings:
            logger.warning(warning.format())

        # 确保目录存在
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(settings.model_dump(), f, indent=2, ensure_ascii=False)

        logger.info(f"配置已保存到: {self.config_path}")

    def exists(self) -> bool:
        """检查配置文件是否存在"""
        return self.config_path.exists()
```

**Step 4: 运行测试（应该通过）**

```bash
poetry run pytest tests/core/configuration/test_manager.py -v
```

**Step 5: 提交**

```bash
git add basket_assistant/core/configuration/manager.py tests/core/configuration/test_manager.py
git commit -m "feat(config): implement ConfigurationManager basics (load/save)"
```

---

由于篇幅限制，完整的实施计划还包括：

- **Task 6-8**: AgentManager 实现（添加、删除、更新智能体）
- **Task 9-10**: ConfigInitializer 实现（6 步初始化向导）
- **Task 11-13**: 集成测试与 Manager 完整功能
- **Phase 3 (Task 14-18)**: 迁移入口文件，删除旧代码
- **Phase 4 (Task 19-21)**: 端到端测试、文档更新

完整计划约 21 个任务，每个任务 2-5 分钟。

---

## 执行说明

计划已保存。两种执行方式：

1. **Subagent-Driven（本会话）** - 我逐任务派发 subagent，任务间代码审查
2. **Parallel Session（独立会话）** - 新会话用 executing-plans skill 批量执行

选哪种？

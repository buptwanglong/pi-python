# Assistant 配置功能重构设计

**日期：** 2026-03-14
**类型：** 重构 + 优化
**范围：** basket-assistant 配置模块

---

## 一、背景与目标

### 问题现状

当前配置功能分散在多个文件中：
- `init_guided.py` - 初始化向导（347 行）
- `core/settings_full.py` - 配置模型与加载（431 行）
- `core/agent_config.py` - 智能体配置（61 行）
- `agent_cli.py` - CLI 命令（132 行）
- `core/agents_loader.py` - 文件系统加载（147 行）

**主要痛点：**
1. **代码分散**：5 个文件，职责不清晰，难以维护
2. **初始化体验**：6 步流程基本合理，但错误提示不够友好，缺少智能默认值

### 重构目标

1. **统一入口**：创建 `ConfigurationManager` 作为所有配置操作的单一入口
2. **清晰职责**：每个模块专注一个领域（模型、初始化、管理、校验、加载）
3. **优化体验**：改进初始化向导的默认值、验证提示、配置预览
4. **不可变性**：所有配置修改返回新对象，避免副作用
5. **直接替换**：不保留兼容层，彻底重构

---

## 二、整体架构

### 目录结构

```
basket_assistant/core/
├── configuration/
│   ├── __init__.py              # 统一导出接口
│   ├── manager.py               # ConfigurationManager 主类
│   ├── models.py                # Pydantic 数据模型
│   ├── initialization.py        # 初始化向导逻辑
│   ├── agents.py                # 子智能体管理操作
│   ├── validation.py            # 配置校验与错误处理
│   └── loaders.py               # 从文件系统加载智能体
```

### 架构原则

1. **单一入口**：`ConfigurationManager` 是所有配置操作的统一接口
2. **不可变性**：所有配置修改返回新的 Settings 对象，不直接修改
3. **职责分离**：每个模块专注一个领域
4. **组合优于继承**：Manager 组合各个子组件
5. **类型安全**：全面使用 Pydantic 和类型注解

### 文件迁移计划

**删除的文件：**
- `basket_assistant/init_guided.py` → 合并到 `configuration/initialization.py`
- `basket_assistant/core/agent_config.py` → 合并到 `configuration/models.py`
- `basket_assistant/agent_cli.py` → 合并到 `configuration/agents.py`
- `basket_assistant/core/agents_loader.py` → 移动到 `configuration/loaders.py`

**拆分的文件：**
- `basket_assistant/core/settings_full.py` → 拆分到 `configuration/models.py` 和 `configuration/manager.py`

**更新的入口：**
- `basket_assistant/main.py` → 调用 `ConfigurationManager`
- `basket_assistant/__main__.py` → 更新 CLI 命令

---

## 三、核心组件设计

### 3.1 ConfigurationManager（manager.py）

**职责：** 统一配置操作入口，协调各子模块

```python
class ConfigurationManager:
    """统一配置管理器"""

    def __init__(self, config_path: Path | str | None = None):
        self.config_path = self._resolve_path(config_path)
        self._validator = ConfigValidator()
        self._agent_manager = AgentManager(self)
        self._initializer = ConfigInitializer(self)

    # === 配置加载与保存 ===
    def load(self) -> Settings:
        """加载配置，带完整校验"""

    def save(self, settings: Settings) -> None:
        """保存配置，带校验"""

    def exists(self) -> bool:
        """检查配置文件是否存在"""

    # === 初始化 ===
    def run_guided_init(self, force: bool = False) -> Settings:
        """运行交互式初始化向导"""

    # === 智能体管理 ===
    def list_agents(self) -> list[AgentInfo]:
        """列出所有子智能体"""

    def add_agent(...) -> Settings:
        """添加子智能体，返回更新后的配置"""

    def remove_agent(name: str) -> Settings:
        """删除子智能体，返回更新后的配置"""

    def update_agent(...) -> Settings:
        """更新子智能体配置"""

    # === 配置查询 ===
    def get_agent_config(name: str | None) -> AgentConfig:
        """获取指定智能体的配置"""

    def get_model_config(agent_name: str | None) -> dict:
        """获取模型配置"""
```

**设计要点：**
- 组合而非继承：Manager 组合 Validator、AgentManager、Initializer
- 不可变操作：add/remove/update 返回新的 Settings
- 延迟加载：内部组件按需创建
- 统一错误处理：所有方法抛出 ConfigurationError

---

### 3.2 数据模型（models.py）

**职责：** Pydantic 模型定义，类型安全与校验

```python
# 基础模型
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
    model: Optional[Dict[str, Any]] = None
    tools: Optional[Dict[str, bool]] = None
    agent_dir: Optional[str] = None
    workspace_dir: Optional[str] = None

# 主配置模型
class Settings(BaseModel):
    """全局配置（从 settings.json 加载）"""
    model: ModelSettings = Field(default_factory=ModelSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    permissions: PermissionsSettings = Field(default_factory=PermissionsSettings)
    api_keys: Dict[str, str] = Field(default_factory=dict)
    sessions_dir: str = "~/.basket/sessions"
    trajectory_dir: Optional[str] = "~/.basket/trajectories"
    skills_dirs: List[str] = Field(default_factory=list)
    agents: Dict[str, SubAgentConfig] = Field(default_factory=dict)
    default_agent: Optional[str] = None
    workspace_dir: Optional[str] = None
    # ... 其他字段

    @model_validator(mode="after")
    def _validate_agents(self) -> "Settings":
        """校验 agents 和 default_agent 的一致性"""
        if self.default_agent and self.default_agent not in self.agents:
            raise ValueError(f"default_agent '{self.default_agent}' 不在 agents 中")
        return self

# 运行时模型
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

**设计要点：**
- 清晰分层：基础配置 → 主配置 → 运行时配置
- 校验前置：Pydantic validator 做一致性检查
- 类型安全：所有字段明确类型
- 展示模型：AgentInfo 专门用于 CLI 展示

---

### 3.3 初始化向导（initialization.py）

**职责：** 交互式配置初始化（6 步流程）

```python
class ConfigInitializer:
    """配置初始化向导"""

    def run(self, force: bool = False) -> Settings:
        """
        运行 6 步初始化流程：
        1. Provider 选择
        2. API Key 输入（脱敏）
        3. Model 选择
        4. Base URL（可选）
        5. Workspace 目录（可选）
        6. Web 搜索配置
        """
        # Step 0: 检查覆盖确认
        # Step 1-6: 各步骤收集
        # 预览配置
        # 保存
```

**优化改进：**

1. **智能默认值**
   - 自动检测环境变量中的 API Key
   - 根据 provider 建议常用模型
   - Base URL 格式自动检查

2. **友好验证**
   - API Key 格式实时校验，给出提示
   - URL 格式检查，不阻断但警告
   - Model ID 拼写检查（与已知模型对比）

3. **配置预览**
   - 保存前展示最终配置（脱敏）
   - 允许用户最后确认

4. **错误恢复**
   - 记录步骤历史（未来支持返回上一步）
   - 初始化失败时保留进度

**Step 示例：**

```python
def _step_api_key(self, provider_info: tuple) -> str:
    """Step 2/6: 输入 API Key"""
    _, _, _, env_var = provider_info

    # 智能检测环境变量
    env_value = os.environ.get(env_var, "")
    if env_value:
        hint = f"检测到环境变量 {env_var}，直接回车使用"
    else:
        hint = f"留空则从环境变量 {env_var} 读取"

    # 脱敏输入
    api_key = self._prompt_password(f"2/6 API Key", hint)

    # 格式验证
    if api_key and not self._validate_api_key(api_key, provider_info[0]):
        self._print_warning("API Key 格式可能不正确，但仍将继续")

    return api_key or env_value
```

---

### 3.4 智能体管理（agents.py）

**职责：** 子智能体的添加、删除、更新、列表

```python
class AgentManager:
    """子智能体管理器"""

    def list_agents(self) -> list[AgentInfo]:
        """列出所有子智能体"""

    def add_agent(
        name: str,
        workspace_dir: Optional[str] = None,
        model: Optional[Dict[str, Any]] = None,
        tools: Optional[Dict[str, bool]] = None,
        force: bool = False
    ) -> Settings:
        """添加子智能体，返回更新后的配置"""
        # 1. 验证名称格式
        # 2. 检查是否已存在
        # 3. 创建 workspace 并填充默认文件
        # 4. 构建新配置（不可变更新）
        # 5. 保存并返回

    def remove_agent(name: str) -> Settings:
        """删除子智能体"""
        # 校验：不能删除 default_agent

    def update_agent(...) -> Settings:
        """更新子智能体配置"""
```

**设计要点：**
- 不可变操作：返回新的 Settings，不修改原对象
- 完善校验：名称格式、存在性、default_agent 保护
- 自动创建：添加时自动创建 workspace 并填充默认文件
- 清晰异常：AgentExistsError、AgentNotFoundError、CannotRemoveDefaultAgentError

---

### 3.5 配置校验（validation.py）

**职责：** 配置格式检查、一致性验证、友好错误提示

```python
class ConfigValidator:
    """配置验证器"""

    # 命名规范
    AGENT_NAME_PATTERN = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')

    # API Key 格式
    API_KEY_PATTERNS = {
        "openai": re.compile(r'^sk-[A-Za-z0-9]{48}$'),
        "anthropic": re.compile(r'^sk-ant-[A-Za-z0-9\-_]{95,}$'),
        "google": re.compile(r'^[A-Za-z0-9_\-]{39}$'),
    }

    def validate_settings(self, settings: Settings) -> list[ValidationWarning]:
        """全面校验配置，返回警告列表（不阻断保存）"""

    def validate_agent_name(self, name: str) -> None:
        """校验智能体名称格式（抛出 ValidationError）"""

    def validate_api_key(self, key: str, provider: str) -> Optional[str]:
        """校验 API Key 格式，返回错误消息"""

    def validate_model_id(self, model_id: str, provider: str) -> Optional[str]:
        """校验模型 ID，返回警告消息"""
```

**错误分级：**
- `ValidationError`：阻断操作（如名称格式错误）
- `ValidationWarning`：不阻断但提示（如路径不存在、模型 ID 未知）

**友好提示示例：**
```
[agent_name] 智能体名称格式不正确: 'My_Agent'
建议: 只能包含小写字母、数字和连字符，且不能以连字符开头或结尾。例如: my-agent, agent-v2
```

---

### 3.6 文件加载器（loaders.py）

**职责：** 从文件系统扫描并加载智能体

```python
class AgentLoader:
    """从文件系统加载智能体配置"""

    @staticmethod
    def load_from_dirs(dirs: List[Path]) -> Dict[str, SubAgentConfig]:
        """
        扫描目录并加载智能体

        支持两种格式：
        1. 目录型：包含 AGENTS.md 或 IDENTITY.md 的子目录
        2. 单文件型：*.md 文件，带 YAML frontmatter

        优先级：后面的目录覆盖前面的；同名时目录型优先于单文件型
        """
```

**功能保持不变，代码更清晰：**
- 统一的 frontmatter 解析
- 明确的错误日志
- 支持 workspace/ 子目录优先

---

## 四、使用示例

### 4.1 初始化配置

```python
from basket_assistant.core.configuration import ConfigurationManager

# 创建管理器
manager = ConfigurationManager()

# 运行交互式初始化
settings = manager.run_guided_init(force=False)
```

### 4.2 加载配置

```python
# 加载配置（带校验）
settings = manager.load()

# 获取模型配置
model_config = manager.get_model_config(agent_name="my-agent")
```

### 4.3 管理智能体

```python
# 列出智能体
agents = manager.list_agents()
for agent in agents:
    print(f"{agent.name}: {agent.workspace_dir}")

# 添加智能体
settings = manager.add_agent(
    name="my-agent",
    model={"provider": "anthropic", "model_id": "claude-sonnet-4"},
    tools={"read": True, "write": False}
)

# 更新智能体
settings = manager.update_agent(
    name="my-agent",
    model={"model_id": "claude-3-5-sonnet"}
)

# 删除智能体
settings = manager.remove_agent("my-agent")
```

### 4.4 CLI 命令

```bash
# 初始化
basket init
basket init --force

# 智能体管理
basket agent list
basket agent add my-agent
basket agent remove my-agent
```

---

## 五、实现计划

### Phase 1: 创建新模块（2-3 天）

1. 创建 `configuration/` 目录结构
2. 实现 `models.py`（数据模型）
3. 实现 `validation.py`（校验逻辑）
4. 实现 `loaders.py`（文件加载）
5. 单元测试

### Phase 2: 核心功能（3-4 天）

1. 实现 `manager.py`（ConfigurationManager）
2. 实现 `agents.py`（AgentManager）
3. 实现 `initialization.py`（ConfigInitializer）
4. 集成测试

### Phase 3: 迁移与删除（1-2 天）

1. 更新 `main.py` 和 `__main__.py` 使用新 Manager
2. 更新所有导入路径
3. 删除旧文件：
   - `init_guided.py`
   - `core/agent_config.py`
   - `agent_cli.py`
   - `core/agents_loader.py`
   - `core/settings_full.py`（部分保留到迁移完成）
4. 更新测试文件

### Phase 4: 验证与优化（1 天）

1. 端到端测试
2. 文档更新（CONFIG.md, CONFIG_MULTI_AGENT.md）
3. 性能测试
4. 错误提示优化

**总计：7-10 天**

---

## 六、风险与应对

### 风险 1：导入路径大规模变更

**应对：**
- 先创建新模块，保持旧文件运行
- 逐步迁移各个使用点
- 全量测试通过后再删除旧文件

### 风险 2：初始化体验改动影响用户

**应对：**
- 保持 6 步流程不变
- 改进是增强而非重构（更好的默认值、提示）
- 充分测试 TTY 和非 TTY 模式

### 风险 3：不可变操作可能影响性能

**应对：**
- Pydantic 的 model_copy 性能很好
- 配置操作不频繁，性能影响可忽略
- 必要时添加缓存层

---

## 七、成功标准

1. ✅ 所有配置操作通过 `ConfigurationManager` 单一入口
2. ✅ 旧文件完全删除，无残留代码
3. ✅ 所有现有测试通过
4. ✅ 初始化体验改进：智能默认值、友好错误提示、配置预览
5. ✅ 代码覆盖率保持 80%+
6. ✅ 文档完整更新

---

## 八、后续优化方向

1. **配置模板**：预设常用配置（研究型、生产型等）
2. **配置迁移**：自动检测旧版本配置并迁移
3. **智能体克隆**：从现有智能体复制配置
4. **交互式编辑**：在 TUI 中编辑配置
5. **配置验证 CLI**：`basket config validate` 检查配置正确性

---

## 总结

这次重构通过创建 `ConfigurationManager` 统一入口，将分散的配置代码整合到清晰的模块结构中，同时优化初始化体验。设计遵循不可变性、职责分离、类型安全等原则，为未来扩展奠定良好基础。

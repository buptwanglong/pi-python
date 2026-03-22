# 清理 `typing.Any` 方案（强类型版，不用 JSON 别名）

## 与上一版差异

- **不再引入** `JSONValue` / `JSONObject` / 「JSON 形状」一类递归别名作为主力替换手段。
- **目标**：用 **TypedDict**、**Pydantic `BaseModel`**、**Protocol**、**TypeVar/泛型**、**显式 `Union`** 表达结构；仅在真无法表达时用 **`object` + 收窄** 或 **极薄适配层**（带注释），避免 `Any`。

## 现状（量级不变）

- 全仓库约 **517 处 `\bAny\b` / 110 个 `*.py` 文件**；仍按包分批推进（assistant / basket-ai / tui 等）。

## 分域策略（强类型）

### 1. 配置与动态 settings（如 `settings_full.py`）

- 将「一团 `dict[str, Any]`」拆成 **嵌套 Pydantic 模型**（与现有 `Field` 用法一致）：每个有稳定结构的区块单独 `BaseModel`。
- 对 **键集合开放、结构不稳定** 的扩展区：用 **`extra="allow"` 的 Pydantic 模型** + **已知字段显式声明**，而不是 `Dict[str, Any]`；若必须保留扩展 dict，类型上可用 **`Mapping[str, object]`** 并在读取点用 validator/TypedDict 收窄（仍优于 `Any`）。

### 2. 钩子 / 网关 / WebSocket 载荷（如 `hook_runner.py`、`gateway.py`）

- 为每种 hook 输入输出定义 **`TypedDict` 或小型 `BaseModel`**（例如 `HookRunInput`, `HookRunResult`）。
- 多事件共通道时： **`TypedDict` + `Literal` 判别字段** 或 **封闭 `Union[EventA, EventB, ...]`**，避免 `Dict[str, Any]`。

### 3. Agent / 工具（`basket_agent/types.py` 等）

- **`parameters`**：`Union[type[BaseModel], <参数 Schema 的 TypedDict>]`；若各工具 schema 不同，可 **`Protocol`（有 `model_json_schema`）** + 对 dict 分支用 **具体 TypedDict**。
- **`arguments`**：与工具参数模型一致 → **`BaseModel` 实例** 或 **该工具对应的 `TypedDict`**；跨工具边界可用 **泛型 `ToolCallSpec[TParams]`** 或 **`Mapping[str, object]`** + 各工具入口校验。
- **`ToolExecutor.execute` 返回值**：**`TypeVar("R")`** 或对内置工具定义 **`ToolResult` 联合类型**（`str | Path | ...`），避免 `-> Any`。
- **`result: Any`（事件里）**：改为 **与 `format_observation` 契约一致** 的联合或 **泛型事件**，必要时 `object` + 格式化前 `isinstance`。

### 4. basket-ai Providers（`openai_completions.py`、`anthropic.py`、`google.py` 等）

- **请求/响应片段**：按官方 API 稳定字段建 **`TypedDict`**（可分包：`basket_ai/providers/openai_typing.py` 等），列表用 `list[OpenAIMessageDict]` 这类具体类型。
- **流式 `delta`**：拆成 **`Union[TextDelta, ToolDelta, ...]`**（与现有分支逻辑对齐），或 **Protocol + isinstance**；避免长期 `delta: Any`。
- **与 SDK 类型对齐**：若已有官方/社区 stub，优先 **标注为 SDK 类型**；无 stub 时对「未建模字段」用 **带 `total=False` 的 TypedDict 扩展段** 而非 `Any`。

### 5. TUI / memory / eval

- UI 状态、消息 payload：**`dataclass` / `TypedDict` / 小型 `BaseModel`**，按模块内聚定义。
- 评估 schema：已有 [basket_eval/schema.py](packages/basket-eval/basket_eval/schema.py) 方向——**继续用 Pydantic/TypedDict 收紧**，去掉 `Any` 字段。

### 6. 测试

- Mock 使用 **具体 fake 类型** 或 **`cast(ConcreteType, ...)`**；避免大面积 `MagicMock` 无注解；必要时 **单测专用 TypedDict**。

## 分阶段落地（建议 PR 粒度）

| 阶段 | 范围 | 要点 |
|------|------|------|
| A | 约定与目录 | 每包或每域新增 `*_types.py` / `typing_*.py` 放 TypedDict 与联合类型；禁止新增 `Any`。 |
| B | basket-assistant 配置 + hooks + gateway | Pydantic 嵌套模型 + hook/gateway 事件 TypedDict。 |
| C | basket-agent | Tool/ToolCall/Executor 泛型或联合；事件 payload 模型化。 |
| D | basket-ai（按 provider 拆 PR） | 每 provider 一套 TypedDict（或共享消息 TypedDict）；流式 Union。 |
| E | tui / memory / eval / 余量 + tests | 收尾；规则示例与代码一致。 |

## 门禁

- 每阶段：**basedpyright `--level error`**（或项目约定）+ 受影响包 **`pytest`**。
- Provider 阶段：对应 provider 单测与一轮集成冒烟。

## 与 Cursor 规则对齐

- 更新 [.cursor/rules/no-weak-any.mdc](.cursor/rules/no-weak-any.mdc) 中示例：去掉「JSONScalar / JSON」式表述，改为 **TypedDict / Pydantic** 示例，与「强类型、不用 JSON 别名」一致。

## 风险

- **工作量高于 JSON 别名方案**：Provider 与 settings 需持续与上游 API 对齐维护。
- **缓解**：按 **API 边界文件**切片；**先覆盖读写路径上的热字段**，其余用 `total=False` 可选键渐进补全。

## Todos（执行时用）

- [ ] 阶段 A：确定 TypedDict/Pydantic 模块布局与命名规范
- [ ] 阶段 B：settings + hooks + gateway 强类型化
- [ ] 阶段 C：basket-agent 工具与事件类型
- [ ] 阶段 D：basket-ai 分 provider TypedDict/Union
- [ ] 阶段 E：其余包 + tests；更新 `no-weak-any.mdc` 示例

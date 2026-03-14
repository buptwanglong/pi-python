# Multi-agent configuration

配置源为 **单一** `settings.json`（与 [CONFIG.md](CONFIG.md) 一致）。主 Agent 与子 Agent（Task 工具用）均由此配置解析。子智能体的增删改可通过 **`basket agent list` / `basket agent add` / `basket agent remove`** 或程序内 **`ConfigurationManager.list_agents()` / `add_agent()` / `remove_agent()` / `update_agent()`** 完成。

- **主 Agent**：
  - **default_agent**（可选）：主 Agent 名称。为 `null` 或未设置时，主 Agent 使用顶层 `model`。
  - 当 `default_agent` 非空且 `agents[default_agent]` 存在且其 `model` 为非空对象时，主 Agent 的 LLM 使用该 `model`（provider、model_id、context_window、max_tokens 等）；否则使用顶层 `model`。
  - **Workspace**：主 Agent 的 base prompt 来自 workspace；若 `agents[default_agent].workspace_dir` 存在则优先使用，否则全局 `workspace_dir` 或默认 `~/.basket/workspace`（未配置时创建并默认填充）。
- **agents**：字典，键为 Agent 名称，值为 SubAgentConfig（`description`、`prompt`、可选 `model`、`tools`、`workspace_dir`）。若某条目同时作为主 Agent（即名为 `default_agent`），其 `model`/`workspace_dir` 用于主 Agent；该条目不会出现在 Task 的「可用子 Agent」列表中。SubAgent 未配 `workspace_dir` 时默认 `~/.basket/agents/<name>/` 并默认填充。
- **CLI**：`basket --agent <名称>` 或 `basket --agent=名称` 会设置环境变量 `BASKET_AGENT`，进程内创建 AssistantAgent 时传入 `agent_name=BASKET_AGENT`，主 Agent 优先使用 `agents[名称].model`（若存在）。
- **环境变量**：`BASKET_AGENT` 由 CLI 在启动时设置；未传 `--agent` 时主 Agent 使用 `default_agent` 或顶层 `model`。

#### TUI 指定 Agent

- **用法**：`basket tui --agent <name>` 启动 TUI 并指定与名为 `<name>` 的主 Agent 通信。`<name>` 需为 `settings.json` 中 `agents` 里已配置的名称（或与 `default_agent` 一致）；未配置时行为与「未指定 agent」一致（使用 default 或顶层 model）。不传 `--agent` 时，TUI 使用默认主 Agent（与当前 `basket tui` 行为一致）。
- **行为**：连接建立时通过 WebSocket URL 查询参数将 `agent` 传给 resident gateway；该连接整个生命周期内固定使用该 Agent，会话与模型/workspace 均按该 Agent 配置。当前版本不在 TUI 内提供切换 Agent 的命令。
- **与现有配置的关系**：未传 `--agent` 时等价于使用 `default_agent`（若已配置）或顶层 `model`。与 `basket --agent <name>` 共用同一套 `agents` 与 `default_agent`；TUI 通过 `--agent` 在启动时指定，非 TUI 交互模式通过 `basket --agent <name>` 指定。Task 工具中的「子 Agent」列表不包含主 Agent；TUI 的 `--agent` 指定的是「当前对话的主 Agent」，不是 Task 委派目标。
- **错误与边界**：若 `<name>` 不在 `agents` 中，gateway 仍会创建 Agent（使用该名称解析 model/workspace，可能回退到默认）。建议先在 `settings.json` 的 `agents` 中配置对应名称，或使用 `basket agent add` 添加后再使用该名称。

# Multi-agent configuration

配置源为 **单一** `settings.json`（与 [CONFIG.md](CONFIG.md) 一致）。主 Agent 与子 Agent（Task 工具用）均由此配置解析。

- **主 Agent**：
  - **default_agent**（可选）：主 Agent 名称。为 `null` 或未设置时，主 Agent 使用顶层 `model`。
  - 当 `default_agent` 非空且 `agents[default_agent]` 存在且其 `model` 为非空对象时，主 Agent 的 LLM 使用该 `model`（provider、model_id、context_window、max_tokens 等）；否则使用顶层 `model`。
- **agents**：字典，键为 Agent 名称，值为 SubAgentConfig（`description`、`prompt`、可选 `model`、可选 `tools`）。若某条目同时作为主 Agent（即名为 `default_agent`），其 `model` 字段用于主 Agent 的 LLM；该条目不会出现在 Task 工具的「可用子 Agent」列表中。
- **CLI**：`basket --agent <名称>` 或 `basket --agent=名称` 会设置环境变量 `BASKET_AGENT`，进程内创建 AssistantAgent 时传入 `agent_name=BASKET_AGENT`，主 Agent 优先使用 `agents[名称].model`（若存在）。
- **环境变量**：`BASKET_AGENT` 由 CLI 在启动时设置；未传 `--agent` 时主 Agent 使用 `default_agent` 或顶层 `model`。

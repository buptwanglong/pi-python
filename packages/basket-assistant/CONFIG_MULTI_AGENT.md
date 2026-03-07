# Multi-agent configuration

- **主 Agent（必填）**：`default_agent` 指向主 Agent 名称；未指定 `--agent` 时使用主 Agent。
- **agents**：字典，键为 Agent 名称，值为该 Agent 的 `provider`、`base_url`、`api_key`、`model`、`temperature` 等。
- **CLI**：`python -m basket_assistant --agent coder` 或 `basket --agent coder`（若入口指向 cli），当前会话使用该 Agent 的 base_url/api_key。
- **环境变量**：`BASKET_AGENT` 可由 CLI 设置，Agent 代码通过 `get_agent_config()` 读取（未传 agent_name 时使用 BASKET_AGENT 或主 Agent）。

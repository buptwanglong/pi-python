# Pi Coding Agent 配置说明

配置文件路径：`~/.basket/settings.json`

## 与 Claude settings 的对应关系

| Claude (~/.claude/settings.json env) | Pi Coding Agent (settings.json) |
|--------------------------------------|----------------------------------|
| `ANTHROPIC_BASE_URL`                 | `model.base_url`                 |
| `ANTHROPIC_AUTH_TOKEN`               | `api_keys.ANTHROPIC_API_KEY`     |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` 等    | `model.model_id`                 |

## 可用 Provider

- **anthropic** — Claude（可配 `base_url` 用自建/内网端点）
- **openai** — GPT 系列
- **google** — Gemini

API Key 可通过 `api_keys` 写入配置，或使用环境变量：`ANTHROPIC_API_KEY`、`OPENAI_API_KEY`、`GOOGLE_API_KEY`。

## 示例（自建 Anthropic 端点）

```json
{
  "model": {
    "provider": "anthropic",
    "model_id": "claude-sonnet-4-20250514",
    "temperature": 0.7,
    "max_tokens": 4096,
    "base_url": "https://your-internal-api.example.com"
  },
  "api_keys": {
    "ANTHROPIC_API_KEY": "sk-ant-xxx"
  },
  "agent": { "max_turns": 10, "auto_save": true, "verbose": false },
  "sessions_dir": "~/.basket/sessions"
}
```

复制 `settings.json.example` 到 `~/.basket/settings.json` 后按需修改。

## Skills（技能）

采用 OpenCode/Claude 式布局：**每技能一个目录，目录内放 `SKILL.md`**。与 OpenCode、Claude Code 共用同一套目录即可复用技能。

- **布局**：在技能目录下创建子目录，子目录名即技能名（如 `git-release`），其内放 `SKILL.md`。`SKILL.md` 必须有 YAML frontmatter：`name`（与目录名一致）、`description`（1–1024 字符）；可选 `metadata`、`compatibility`、`license`。`name` 须符合 `^[a-z0-9]+(-[a-z0-9]+)*$`、长度 1–64。
- **默认搜索路径**（空配置时）：Basket（`~/.basket/skills`、`./.basket/skills`）、OpenCode（`~/.config/opencode/skills`、`./.opencode/skills`）、Claude（`~/.claude/skills`、`./.claude/skills`）、Agents（`~/.agents/skills`、`./.agents/skills`）。同技能名时后出现的覆盖先出现的。
- **发现与加载**：Agent 通过内置 `skill` 工具发现可用技能（工具描述中含 `<available_skills>` 列表），调用 `skill(name)` 即可按需加载技能全文（作为 tool result 返回）。用户也可在交互中输入 `/skill <id> [消息]` 强制本回合使用该技能。
- **配置**：`skills_dirs`（目录列表，显式配置时仅用此列表，不追加上述路径）、`skills_include`（要加载的技能名列表，空则全部）。

## 常驻助理 (basket serve)

- 端口：环境变量 `BASKET_SERVE_PORT`（默认 7682）；状态文件 `~/.basket/serve.pid`、`~/.basket/serve.port`。
- 子命令：`basket serve start` 启动、`basket serve stop` 停止、`basket serve status` 状态、`basket serve attach` 进入 TUI 交互（退出 TUI 后助理继续运行）。

### 飞书 Channel（长连接）

在 `settings.json` 中配置 `serve.feishu` 后，`basket serve start` 会启用飞书长连接，在飞书内与助理对话：

```json
"serve": {
  "feishu": {
    "app_id": "cli_xxxxxxxxxx",
    "app_secret": "xxxxxxxxxxxxxxxx"
  }
}
```

- 不配置或 `app_id`/`app_secret` 为空时，飞书 channel 不启用。
- 也可用环境变量 `FEISHU_APP_ID`、`FEISHU_APP_SECRET` 覆盖或补全（未在 settings 中填写时生效）。
- 需安装可选依赖：`pip install basket-gateway[feishu]`（即 lark-oapi）。

### 钉钉 Channel（Stream 长连接）

在 `settings.json` 中配置 `serve.dingtalk` 后，`basket serve start` 会启用钉钉 Stream 长连接，在钉钉内与助理对话（无需公网）：

```json
"serve": {
  "dingtalk": {
    "client_id": "您的应用 ClientID",
    "client_secret": "您的应用 ClientSecret"
  }
}
```

- 不配置或 `client_id`/`client_secret` 为空时，钉钉 channel 不启用。
- 也可用环境变量 `DINGTALK_CLIENT_ID`、`DINGTALK_CLIENT_SECRET` 覆盖或补全。
- 需在钉钉开放平台创建应用并开通机器人、Stream 模式能力；单聊直接发消息即可，群聊需 AT 机器人。
- 需安装可选依赖：`pip install basket-gateway[dingtalk]`（即 dingtalk-stream）。

## SubAgent 与 Task 工具

主 agent 可通过 **Task 工具**将任务委派给配置好的 SubAgent，由 SubAgent 在独立上下文中执行后返回最后一条回复文本。

### 配置来源与合并

1. **settings.json 的 `agents`**：键为 subagent 名称，值为 `SubAgentConfig` 对象。
2. **`.basket/agents/*.md` 文件**：与 OpenCode `.opencode/agents/` 对齐，每文件一个 agent，文件名 stem 即名称（如 `explore.md` → `explore`）。

合并顺序：先使用 `settings.agents`，再扫描 `agents_dirs` 中的 `*.md`，**同名时后加载的覆盖先前的**（例如先读 settings，再扫目录，目录内 agent 覆盖 settings）。目录顺序默认为先用户级 `~/.basket/agents`，再项目级 `./.basket/agents`，项目内同名会覆盖用户级。

### SubAgentConfig 字段（settings 或 .md frontmatter）

| 字段 | 必填 | 说明 |
|------|------|------|
| `description` | 是 | 简短描述，供 Task 工具列表展示 |
| `prompt` | 否* | 该 subagent 的 system prompt；\*.md 中不写时用正文 |
| `model` | 否 | 如 `{"provider": "openai", "model_id": "gpt-4o-mini"}`；不设则用主 agent 的 model |
| `tools` | 否 | 键为工具名（read/write/edit/bash/grep/skill），值为是否允许；不设则与主 agent 相同（全开） |

### settings.json 中的 agents 示例

```json
"agents": {
  "general": {
    "description": "General-purpose research and multi-step tasks",
    "prompt": "You are a thorough research assistant. Use read/grep to explore, then summarize."
  },
  "explore": {
    "description": "Fast codebase exploration",
    "prompt": "You explore codebases. Use read, grep, and list_dir. Be concise.",
    "tools": { "read": true, "grep": true, "bash": true }
  }
}
```

### .basket/agents/*.md 格式

- 仅扫描 `*.md`，文件名 stem 即 agent 名称。
- 每文件为 **YAML frontmatter + 正文**。frontmatter 必填 `description`；可选 `prompt`、`model`、`tools`。若 frontmatter 未写 `prompt`，则用**正文**作为该 agent 的 system prompt。

示例 `explore.md`：

```yaml
---
description: Fast codebase exploration
tools:
  read: true
  grep: true
  bash: true
---

You explore codebases. Use read, grep, and list_dir. Be concise.
```

### Task 工具参数与委派流程

- **参数**：`description`（3–5 词任务简述）、`prompt`（给 subagent 的完整任务描述）、`subagent_type`（subagent 名称，从可用列表选）。
- **流程**：主 agent 调用 `task(description=..., prompt=..., subagent_type=...)` → 内部根据 `subagent_type` 取配置、建 Context、创建临时 Agent、注册过滤后的工具、执行 `run()`，取最后一条 assistant 消息的文本，包装为 `task_id: none` 与 `<task_result>...</task_result>` 返回给主 agent。

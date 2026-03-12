# Pi Coding Agent 配置说明

配置文件路径：`~/.basket/settings.json`

## 首次配置

首次使用建议运行 **`basket init`** 进行引导式配置，按提示选择 Provider、填写 API Key、模型、工作区与 Web 搜索等，即可在 `~/.basket/settings.json` 生成完整配置（也可通过 `basket init --path <文件路径>` 指定输出文件，`basket init --force` 覆盖已有文件而不二次确认）。完成后运行 `basket` 即可启动；后续可按需直接编辑 `settings.json` 或使用将来的 `basket config` 子命令调整。

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

## Web Search（网页搜索）

- **默认**：使用 duckduckgo-search，无需 API key。
- **可选 Serper**：在 `settings.json` 中设置 `web_search_provider` 为 `"serper"`，并在 `api_keys` 中配置 `SERPER_API_KEY`（或环境变量 `SERPER_API_KEY`），则使用 Serper Google 搜索 API。

## 模型配置（model）

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `model.provider` | string | openai | 提供商：openai / anthropic / google |
| `model.model_id` | string | gpt-4o-mini | 模型 ID |
| `model.temperature` | number | 0.7 | 采样温度 |
| `model.max_tokens` | int | 4096 | 单轮最大输出 token 数 |
| `model.context_window` | int | 128000 | 模型上下文窗口大小（token 数） |
| `model.base_url` | string \| null | null | 自建/代理 API 地址，为空则用官方端点 |

## 示例（自建 Anthropic 端点）

```json
{
  "model": {
    "provider": "anthropic",
    "model_id": "claude-sonnet-4-20250514",
    "temperature": 0.7,
    "max_tokens": 4096,
    "context_window": 200000,
    "base_url": "https://your-internal-api.example.com"
  },
  "api_keys": {
    "ANTHROPIC_API_KEY": "sk-ant-xxx",
    "SERPER_API_KEY": ""
  },
  "web_search_provider": null,
  "agent": { "max_turns": 10, "auto_save": true, "verbose": false },
  "sessions_dir": "~/.basket/sessions"
}
```

复制 `settings.json.example` 到 `~/.basket/settings.json` 后按需修改。

## 主 Agent 与 default_agent（可选）

配置源为单一的 `settings.json`（见 [CONFIG_MULTI_AGENT.md](CONFIG_MULTI_AGENT.md) 多 Agent 说明）。

- **默认行为**：未设置 `default_agent` 时，主 Agent 使用顶层 `model` 配置。
- **多主 Agent 可选**：在 `settings.json` 中设置 `default_agent` 为某个名称，并在 `agents` 中提供同名条目且其 `model` 为非空对象时，主 Agent 将使用该条目的 `model`（provider、model_id、context_window、max_tokens 等）作为 LLM 配置。
- **CLI 切换**：运行 `basket --agent <名称>` 时，会设置环境变量 `BASKET_AGENT`，当前进程的主 Agent 将使用该名称解析 `agents[名称].model`（若存在），否则仍回退到 `default_agent` 或顶层 `model`。**TUI**：`basket tui --agent <名称>` 可在启动 TUI 时指定主 Agent，详见 [CONFIG_MULTI_AGENT.md](CONFIG_MULTI_AGENT.md) 中「TUI 指定 Agent」小节。
- **Task 工具**：Task 工具列出的「可用子 Agent」不包含 `default_agent`，主 Agent 不会被当作子 Agent 委派。

## Agent 工作区与身份文件

**Workspace 必选**：主 Agent 与 SubAgent 均使用工作区目录（OpenClaw 风格多种 md 文件）组装 system prompt。未配置 `workspace_dir` 时采用**默认路径并默认填充**（创建目录、缺失时写入最小 AGENTS.md/IDENTITY.md 模板）。

### 配置项

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `workspace_dir` | string \| null | null | 工作区根目录，如 `"~/.basket/workspace"`。为 null 或空时使用**默认路径** `~/.basket/workspace`，目录不存在则创建并默认填充。 |
| `skip_bootstrap` | boolean | false | 为 true 时不从工作区加载任何身份/行为文件，仅用内置 base prompt。 |

主 Agent 的 workspace 来源（优先级）：① `agents[default_agent].workspace_dir` 若存在则优先使用；② 否则全局 `workspace_dir` 或上述默认路径。

### 工作区文件（仿照 OpenClaw）

在工作区目录下可放置以下 Markdown 文件（UTF-8），缺失的文件会被忽略，仅存在且有内容的文件会参与组装。

| 文件 | 用途 |
|------|------|
| **IDENTITY.md** | 身份：名字、角色、风格、emoji 等。 |
| **SOUL.md** | 人设与边界：语气、价值观、不可妥协的约束。 |
| **AGENTS.md** | 操作说明与规则：优先级、工作流、如何用 memory 等。 |
| **USER.md** | 用户信息：用户是谁、如何称呼。 |
| **TOOLS.md** | （可选）本地工具与环境约定；仅作提示，不控制工具是否可用。 |
| **MEMORY.md** | （可选）长期记忆：持久事实、压缩摘要。 |
| **memory/YYYY-MM-DD.md** | （可选）按日记忆；会话启动时加载今日+昨日。 |
| **BOOTSTRAP.md** / **BOOT.md** / **HEARTBEAT.md** | （可选）与 OpenClaw 对齐的占位文件，存在则参与组装。 |

组装顺序：Identity → Soul → AGENTS → User → TOOLS → Memory（含 MEMORY.md + memory/今日+昨日）→ 可选 BOOT/HEARTBEAT → 固定工具使用说明块。

### 与 OpenClaw 的对应关系

设计参考 OpenClaw 的 agent workspace：每个 agent 可有独立 workspace。主 Agent 可使用全局 `workspace_dir` 或 `agents[default_agent].workspace_dir`；SubAgent 可使用 `agents[name].workspace_dir` 或由 `.basket/agents/<name>/` 目录型定义。

### 示例

在 `settings.json` 中设置 `"workspace_dir": "~/.basket/workspace"`（或不设，使用默认路径）。创建目录并添加 `IDENTITY.md`、`AGENTS.md` 等。设 `skip_bootstrap: true` 时不加载工作区内容，仅用内置 base prompt。

## Hooks（子进程式，语言无关）

Hooks 在工具执行前后、会话创建等节点以 **子进程** 方式运行，stdin 收一行 JSON、stdout 回一行 JSON，与实现语言无关（bash/Python/Go 等均可）。

### 配置位置与优先级

1. **独立文件**：项目 `./.basket/hooks.json`、用户 `~/.basket/hooks.json`（先项目后用户，同事件多定义按顺序执行）。
2. **settings.json**：可选 `hooks` 段（与文件合并，缺项用 settings 补）。

### hooks.json 格式

```json
{
  "version": 1,
  "hooks": {
    "tool.execute.before": [
      {
        "command": "~/.basket/hooks/block_env_read.sh",
        "timeout": 10,
        "matcher": "read"
      }
    ],
    "tool.execute.after": [
      { "command": "python ~/.basket/hooks/audit.py", "timeout": 5 }
    ],
    "session.created": [
      { "command": "~/.basket/hooks/session_init.sh", "timeout": 5 }
    ]
  }
}
```

- **command**（必填）：要执行的命令或脚本路径；路径中的 `~` 会展开。
- **timeout**（可选）：超时秒数，默认 30；超时视为拒绝（deny）。
- **matcher**（可选）：仅当匹配时执行。对 `tool.execute.before`/`after` 为工具名或正则（对 `bash` 工具还会匹配命令字符串）。

### 子进程协议

- **输入**：Runner 向 stdin 写入一行 JSON，包含 `hook_event_name`、`cwd` 及事件专属字段（如 `tool_name`、`arguments`、`session_id` 等）。
- **输出**：脚本向 stdout 写入一行 JSON。`tool.execute.before` 可返回：
  - `permission`: `"allow"` | `"deny"` | `"ask"`；
  - `reason`：拒绝时给 agent 的说明；
  - `modified_arguments`：若允许但需改参，提供新的 arguments 对象。
- **退出码**：`0` 正常；`2` 表示拒绝（等价于 `permission: "deny"`）。

详见 `docs/hooks_protocol.md`（如有）。

## Skills（技能）

采用 OpenCode/Claude 式布局：**每技能一个目录，目录内放 `SKILL.md`**。与 OpenCode、Claude Code 共用同一套目录即可复用技能。

- **布局**：在技能目录下创建子目录，子目录名即技能名（如 `git-release`），其内放 `SKILL.md`。`SKILL.md` 必须有 YAML frontmatter：`name`（与目录名一致）、`description`（1–1024 字符）；可选 `metadata`、`compatibility`、`license`。`name` 须符合 `^[a-z0-9]+(-[a-z0-9]+)*$`、长度 1–64。
- **默认搜索路径**（空配置时）：Basket（`~/.basket/skills`、`./.basket/skills`）、OpenCode（`~/.config/opencode/skills`、`./.opencode/skills`）、Claude（`~/.claude/skills`、`./.claude/skills`）、Agents（`~/.agents/skills`、`./.agents/skills`）。同技能名时后出现的覆盖先出现的。
- **发现与加载**：Agent 通过内置 `skill` 工具发现可用技能（工具描述中含 `<available_skills>` 列表），调用 `skill(name)` 即可按需加载技能全文（作为 tool result 返回）。用户也可在交互中输入 `/skill <id> [消息]` 强制本回合使用该技能。
- **配置**：`skills_dirs`（目录列表，显式配置时仅用此列表，不追加上述路径）、`skills_include`（要加载的技能名列表，空则全部）。

## 常驻助理 (basket gateway)

- 端口：环境变量 `BASKET_SERVE_PORT`（默认 7682）；状态文件 `~/.basket/serve.pid`、`~/.basket/serve.port`。
- 使用方式：运行 `basket tui` 即可（若 gateway 未运行会先后台启动再连接）；或单独 `basket gateway start` 启动、`basket gateway stop` 停止、`basket gateway status` 查看状态。

### 飞书 Channel（长连接）

在 `settings.json` 中配置 `serve.feishu` 后，`basket gateway start` 会启用飞书长连接，在飞书内与助理对话：

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

在 `settings.json` 中配置 `serve.dingtalk` 后，`basket gateway start` 会启用钉钉 Stream 长连接，在钉钉内与助理对话（无需公网）：

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

## Relay（中继，本机不开放端口）

使用自建消息中继时，可在 `settings.json` 中配置 **`relay_url`**，则运行 `basket relay` 时无需再写 URL（命令行参数仍可覆盖配置）：

```json
"relay_url": "wss://your-vps:7683/relay/agent"
```

- 不配置或为空时，需执行 `basket relay <relay_url>` 显式传入地址。
- 也可写在 `serve.relay_url`，与顶层 `relay_url` 二选一即可。

## SubAgent 与 Task 工具

主 agent 可通过 **Task 工具**将任务委派给配置好的 SubAgent，由 SubAgent 在独立上下文中执行后返回最后一条回复文本。

### 配置来源与合并

1. **settings.json 的 `agents`**：键为 subagent 名称，值为 `SubAgentConfig` 对象。
2. **`.basket/agents/*.md` 文件**：单文件型，文件名 stem 即名称（如 `explore.md` → `explore`），frontmatter + 正文。
3. **`.basket/agents/<name>/` 目录**：目录型（OpenClaw 式），目录内放 AGENTS.md、IDENTITY.md、SOUL.md 等；同一名称下**目录优先于同名的 .md 文件**。

合并顺序：先 `settings.agents`，再扫描 `agents_dirs`（先用户级 `~/.basket/agents`，再项目级 `./.basket/agents`）；同名时后加载的覆盖先前的。SubAgent 的 system prompt 由该 agent 的 **workspace 目录**（多种 md 文件）组装；未配置 `workspace_dir` 时使用默认路径 `~/.basket/agents/<name>/` 并默认填充。

### SubAgentConfig 字段（settings 或 .md frontmatter）

| 字段 | 必填 | 说明 |
|------|------|------|
| `description` | 是 | 简短描述，供 Task 工具列表展示 |
| `prompt` | 否 | 可作追加段；当有 workspace_dir 时以 workspace 组装为主 |
| `model` | 否 | 如 `{"provider": "openai", "model_id": "gpt-4o-mini"}`；不设则用主 agent 的 model |
| `tools` | 否 | 键为工具名（read/write/edit/bash/grep/skill），值为是否允许；不设则与主 agent 相同（全开） |
| `workspace_dir` | 否 | 该 agent 的工作区目录；未设时默认 `~/.basket/agents/<name>/` 并默认填充 |

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

### .basket/agents 两种定义方式

- **单文件型**：`<name>.md`，文件名 stem 即 agent 名称。YAML frontmatter 必填 `description`；可选 `prompt`、`model`、`tools`、`workspace_dir`。若未写 `prompt` 则用正文。未配 `workspace_dir` 时运行时使用默认 `~/.basket/agents/<name>/` 并默认填充。
- **目录型**：`<name>/` 子目录，其内包含 AGENTS.md 或 IDENTITY.md 等 workspace 文件；该目录即该 agent 的 workspace_dir，description 取自 AGENTS.md 首段。同一 name 下目录优先于 .md 文件。

示例单文件 `explore.md`：

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
- **流程**：主 agent 调用 `task(description=..., prompt=..., subagent_type=...)` → 内部生成唯一 `task_id`、根据 `subagent_type` 取配置、建 Context、创建临时 Agent、注册过滤后的工具、执行 `run()`，取最后一条 assistant 消息的文本，包装为 `task_id: <uuid>` 与 `<task_result>...</task_result>` 返回给主 agent。主 agent 可在上下文中看到可追溯的 task_id。
- **Todo / Trajectory 归属**：Todo 仅属于主 Agent 的当前 Session（`todo_write` 读写当前 session 的 todo 列表）；子 Agent 不共享、不写入主 Session 的 todo。Trajectory 默认仅主 Agent 记录；子 Agent 的调用不单独落盘 trajectory，除非后续扩展。

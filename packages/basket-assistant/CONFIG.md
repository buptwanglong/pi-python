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

- **目录**：`~/.basket/skills/`、`./.basket/skills/`（同 id 时项目覆盖用户）。
- **文件**：每个技能一个 `{id}.md`；可选 YAML frontmatter 写 `description: 一句话描述`，其余为正文。主链路只带「索引」（名称+描述），用 `/skill <id>` 时本回合注入该技能全量。
- **配置**：`skills_dirs`（目录列表，空则用上述默认）、`skills_include`（要加载的 id 列表，空则全部）。

## 常驻助理 (basket serve)

- 端口：环境变量 `BASKET_SERVE_PORT`（默认 7682）；状态文件 `~/.basket/serve.pid`、`~/.basket/serve.port`。
- 子命令：`basket serve start` 启动、`basket serve stop` 停止、`basket serve status` 状态、`basket serve attach` 进入 TUI 交互（退出 TUI 后助理继续运行）。

# Pi Coding Agent 配置说明

配置文件路径：`~/.pi-coding-agent/settings.json`

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
  "sessions_dir": "~/.pi-coding-agent/sessions"
}
```

复制 `settings.json.example` 到 `~/.pi-coding-agent/settings.json` 后按需修改。

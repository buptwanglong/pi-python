# basket-gateway

Gateway and channels for the resident assistant. Provides:

- **AgentGateway**: runs agent per session (single default session or per-session for multi-user).
- **Channels**: WebSocket (`/ws`), Feishu (long-connection via lark-oapi).

The assistant depends on this package and calls `run_gateway(agent_factory=..., channel_config=...)`.

## Installation

```bash
# Without Feishu (default)
pip install basket-gateway

# With Feishu channel (lark-oapi)
pip install basket-gateway[feishu]
```

## Usage

Typically used by `basket serve start` from basket-assistant. Standalone:

```python
from basket_gateway import run_gateway

async def main():
    await run_gateway(
        host="127.0.0.1",
        port=7682,
        agent_factory=lambda: YourCodingAgent(),
        channel_config={"websocket": True, "feishu": None},
    )
```

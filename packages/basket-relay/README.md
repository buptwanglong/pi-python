# basket-relay

Message relay server for basket assistant. Enables **outbound-only** agent connection: the local machine does not open any port; it connects to this relay. Phones/browsers connect to the relay and attach to the same session.

Deploy on a VPS (e.g. domestic), then run `basket relay wss://your-relay-host:7683/relay/agent` on your machine.

## Run

```bash
# Install (from repo root: poetry in basket-relay dir, or pip install -e packages/basket-relay)
cd packages/basket-relay && poetry install

# Start relay (default 0.0.0.0:7683)
poetry run python -m basket_relay --port 7683
```

## Endpoints

- `WS /relay/agent` — Local agent connects here (outbound). Receives `{ "type": "registered", "session_id", "client_url" }`. Then receives `{ "type": "message", "content": "..." }` from clients; sends events (text_delta, tool_call_*, etc.) back.
- `WS /relay/client?session_id=xxx` — Phone/browser connects here. Sends `{ "type": "message", "content": "..." }`; receives same events as attach to local gateway.

Protocol is compatible with basket attach (gateway WebSocket): same message and event types.

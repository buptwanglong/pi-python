# basket-memory

Pluggable memory backends for AI assistants. Integrate with basket-assistant via settings and optional `basket-memory` dependencies (see this package’s Usage section).

## Installation

```bash
# Core only (basket local SQLite + noop; no extra deps for lexical)
pip install basket-memory

# With Mem0
pip install basket-memory[mem0]
```

## Usage

```python
from basket_memory import MemoryManager, create_backends_from_config

# Default local backend (basket: SQLite + FTS5)
config = [{"provider": "basket", "db_path": "~/.basket/memory/basket.sqlite", "mode": "lexical"}]
backends = create_backends_from_config(config)
manager = MemoryManager(backends)

# Add a conversation turn
await manager.add("user-1", [{"role": "user", "content": "I use Python 3.12"}, {"role": "assistant", "content": "Noted."}])

# Search
items = await manager.search("user-1", "What Python version?", limit=5)
```

## Configuration (unified backends)

All backends use the same config shape: `custom["memory"]["backends"]` is a list; each item is `{ "provider": "<name>", ... provider-specific options }`. You can enable multiple backends at once (e.g. basket local + mem0 cloud).

| provider     | description        | typical options |
| ------------ | ------------------ | --------------- |
| `basket`     | Local SQLite + FTS5 (default); optional hybrid with embeddings | `db_path`, `mode` ("lexical" \| "hybrid"), `embedding_provider` ("off" \| "ollama" \| "openai"), `embedding_model`, `ollama_base_url`, `semantic_weight` |
| `openclaw`   | Alias for `basket` | same as basket  |
| `noop`       | No-op (testing)    | none            |
| `mem0`       | Mem0 cloud         | `api_key`, `api_key_env` |

**Examples**

- Only local (basket): `"backends": [{ "provider": "basket", "db_path": "~/.basket/memory/basket.sqlite", "mode": "lexical" }]`
- Basket + mem0: add both objects to `backends`; add/search run against all.
- Basket hybrid (FTS + embeddings): `"provider": "basket", "mode": "hybrid", "embedding_provider": "ollama", "embedding_model": "nomic-embed-text"` (requires httpx for HTTP calls).

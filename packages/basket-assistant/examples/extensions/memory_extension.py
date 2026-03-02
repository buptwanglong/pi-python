"""
Memory extension: pluggable long-term memory via basket-memory.

Reads config from settings.custom["memory"] and registers before_run (search + inject)
and turn_done (add). Requires: pip install basket-memory (and optionally [mem0]).

Memory is not isolated by session: all conversations share the same namespace by default
("default"). Optionally set "memory_namespace" to use a custom namespace.

Config example in settings.json:
  "custom": {
    "memory": {
      "memory_namespace": "default",
      "backends": [{"provider": "noop"}],
      "max_search_results": 10
    }
  }
"""

import logging

logger = logging.getLogger(__name__)


def setup(basket):
    """
    Extension setup: create MemoryManager from custom["memory"] and register before_run/turn_done.
    """
    try:
        from basket_memory import MemoryManager, create_backends_from_config
    except ImportError:
        logger.info("basket-memory not installed; memory extension disabled")
        return

    config = (basket.get_settings().custom or {}).get("memory")
    if not config or not isinstance(config, dict):
        return
    backends_config = config.get("backends")
    if not backends_config or not isinstance(backends_config, list):
        return
    backends = create_backends_from_config(backends_config)
    if not backends:
        return
    memory_manager = MemoryManager(backends)
    max_search_results = int(config.get("max_search_results") or 10)
    namespace = (config.get("memory_namespace") or "").strip() or "default"

    @basket.on("before_run")
    async def on_before_run(event):
        logger.info(
            "memory: before_run event keys=%s namespace=%s",
            list(event.keys()) if isinstance(event, dict) else type(event).__name__,
            namespace,
        )
        context = event.get("context")
        if context is None:
            logger.info("memory: before_run skip context is None")
            return
        query = ""
        for msg in reversed(getattr(context, "messages", []) or []):
            if getattr(msg, "role", None) == "user":
                c = getattr(msg, "content", "")
                query = c if isinstance(c, str) else str(c)
                break
        if not query.strip():
            logger.info("memory: before_run skip query empty")
            return
        try:
            items = await memory_manager.search(
                namespace, query.strip(), limit=max_search_results
            ) 
            if not items:
                logger.info("memory: before_run search namespace=%s results=0", namespace)
                return
            logger.info(
                "memory: before_run search namespace=%s query_len=%d results=%d",
                namespace,
                len(query.strip()),
                len(items),
            )
            lines = ["## Relevant memory\n"]
            for item in items:
                lines.append("- " + (item.content or "").replace("\n", " ").strip())
            snippet = "\n".join(lines).strip()
            if snippet:
                context.system_prompt = (context.system_prompt or "") + "\n\n" + snippet
        except Exception as e:
            logger.warning("Memory search failed: %s", e, exc_info=True)

    @basket.on("turn_done")
    async def on_turn_done(event):
        logger.info("memory: on_turn_done entered (module __name__=%s)", __name__)
        new_messages = event.get("new_messages") or []
        logger.info(
            "memory: turn_done event keys=%s namespace=%s new_messages=%d",
            list(event.keys()) if isinstance(event, dict) else type(event).__name__,
            namespace,
            len(new_messages),
        )
        if not new_messages:
            logger.info("memory: turn_done skip new_messages empty")
            return
        try:
            await memory_manager.add(namespace, new_messages)
            logger.info(
                "memory: turn_done add namespace=%s messages=%d",
                namespace,
                len(new_messages),
            )
        except Exception as e:
            logger.warning("Memory add failed: %s", e, exc_info=True)

    logger.info(
        "Memory extension loaded: backends=%d, namespace=%s, max_search_results=%d",
        len(backends),
        namespace,
        max_search_results,
    )

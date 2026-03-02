"""Create backends from config (e.g. settings.custom["memory"]["backends"])."""

import logging
from typing import Any, Dict, List

from .backends.base import MemoryBackend
from .backends.noop import NoopBackend

logger = logging.getLogger(__name__)


def create_backends_from_config(config: List[Dict[str, Any]]) -> List[MemoryBackend]:
    """
    Build a list of MemoryBackend from config list.
    Each item should have "provider" (e.g. "noop", "mem0", "basket") and provider-specific options.
    Skips or logs for unknown provider or missing optional deps.
    """
    backends: List[MemoryBackend] = []
    for i, entry in enumerate(config):
        if not isinstance(entry, dict):
            logger.warning("memory backends[%s] is not a dict, skipping", i)
            continue
        provider = (entry.get("provider") or "").strip().lower()
        if provider == "noop":
            backends.append(NoopBackend())
            continue
        if provider in ("basket", "openclaw"):
            from .backends.basket_backend import BasketBackend
            backends.append(BasketBackend(**{k: v for k, v in entry.items() if k != "provider"}))
            continue
        if provider == "mem0":
            try:
                from .backends.mem0_backend import Mem0Backend
                backends.append(Mem0Backend(**{k: v for k, v in entry.items() if k != "provider"}))
            except ImportError as e:
                logger.warning("mem0 backend skipped (install basket-memory[mem0]): %s", e)
            continue
        logger.warning("unknown memory provider %r, skipping", provider)
    return backends

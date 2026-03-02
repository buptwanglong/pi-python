"""Tests for basket_memory."""

import tempfile
from pathlib import Path

import pytest

from basket_memory import (
    MemoryManager,
    NoopBackend,
    create_backends_from_config,
    messages_to_dicts,
)
from basket_memory.types import MemoryItem


@pytest.mark.asyncio
async def test_noop_backend_add_search():
    backend = NoopBackend()
    await backend.add("u1", [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}])
    results = await backend.search("u1", "hi", limit=5)
    assert results == []


@pytest.mark.asyncio
async def test_manager_add_search_noop():
    manager = MemoryManager([NoopBackend()])
    await manager.add("u1", [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}])
    results = await manager.search("u1", "x", limit=5)
    assert results == []


@pytest.mark.asyncio
async def test_manager_messages_to_dicts():
    """Manager normalizes message-like objects to dicts."""
    class FakeUser:
        role = "user"
        content = "hello"
    class FakeAssistant:
        role = "assistant"
        content = [type("B", (), {"text": "hi"})()]
    manager = MemoryManager([NoopBackend()])
    dicts = messages_to_dicts([FakeUser(), FakeAssistant()])
    assert len(dicts) == 2
    assert dicts[0] == {"role": "user", "content": "hello"}
    assert dicts[1] == {"role": "assistant", "content": "hi"}


def test_create_backends_from_config_noop():
    backends = create_backends_from_config([{"provider": "noop"}])
    assert len(backends) == 1
    assert isinstance(backends[0], NoopBackend)


def test_create_backends_from_config_unknown_provider():
    backends = create_backends_from_config([{"provider": "unknown"}])
    assert len(backends) == 0


def test_create_backends_from_config_mem0_skipped_without_extra():
    """Without mem0ai installed, mem0 provider is skipped."""
    backends = create_backends_from_config([{"provider": "mem0"}])
    # May be 0 if ImportError, or 1 if mem0ai happens to be installed
    assert all(hasattr(b, "add") for b in backends)


def test_create_backends_from_config_basket_and_openclaw():
    """basket and openclaw provider create BasketBackend."""
    from basket_memory.backends.basket_backend import BasketBackend
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "basket.sqlite"
        for provider in ("basket", "openclaw"):
            backends = create_backends_from_config([
                {"provider": provider, "db_path": str(db), "mode": "lexical"}
            ])
            assert len(backends) == 1
            assert isinstance(backends[0], BasketBackend)


@pytest.mark.asyncio
async def test_basket_backend_add_and_search():
    """BasketBackend: add messages then search returns stored content."""
    from basket_memory.backends.basket_backend import BasketBackend
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.sqlite"
        backend = BasketBackend(db_path=str(db), mode="lexical")
        await backend.add("user1", [
            {"role": "user", "content": "I use Python 3.12"},
            {"role": "assistant", "content": "Noted."},
        ])
        results = await backend.search("user1", "Python", limit=5)
        assert len(results) >= 1
        assert any("Python" in (r.content or "") for r in results)
        assert all(isinstance(r, MemoryItem) for r in results)


@pytest.mark.asyncio
async def test_basket_backend_search_empty_query_returns_empty():
    """BasketBackend: empty query returns []."""
    from basket_memory.backends.basket_backend import BasketBackend
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.sqlite"
        backend = BasketBackend(db_path=str(db), mode="lexical")
        await backend.add("user1", [{"role": "user", "content": "hi"}])
        assert await backend.search("user1", "", limit=5) == []
        assert await backend.search("user1", "   ", limit=5) == []

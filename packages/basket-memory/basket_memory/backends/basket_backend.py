"""
Basket memory backend: local SQLite + FTS5, optional hybrid (FTS + embedding).
Provider name: "basket" (default) or alias "openclaw". No extra deps for lexical mode.
"""

import asyncio
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..types import MemoryItem
from .base import MemoryBackend

logger = logging.getLogger(__name__)


def _run_sync(fn):
    """Run sync SQLite/embedding call in thread."""
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(None, fn)


class BasketBackend(MemoryBackend):
    """Local SQLite + FTS5 backend; optional embedding for hybrid search."""

    def __init__(
        self,
        db_path: str,
        mode: str = "lexical",
        embedding_provider: str = "off",
        embedding_model: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        openai_base_url: Optional[str] = None,
        ollama_base_url: Optional[str] = "http://127.0.0.1:11434",
        semantic_weight: float = 0.7,
        **kwargs: Any,
    ):
        self._db_path = Path(db_path).expanduser()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._mode = mode if mode in ("lexical", "hybrid") else "lexical"
        self._embedding_provider = embedding_provider if embedding_provider in ("off", "openai", "ollama") else "off"
        self._embedding_model = embedding_model
        self._openai_api_key = openai_api_key
        self._openai_base_url = openai_base_url or "https://api.openai.com/v1"
        self._ollama_base_url = (ollama_base_url or "http://127.0.0.1:11434").rstrip("/")
        self._semantic_weight = max(0.0, min(1.0, semantic_weight))
        self._httpx_available: Optional[bool] = None
        self._ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    def _ensure_schema(self) -> None:
        conn = self._conn()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    metadata_json TEXT
                )
                """
            )
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(content)"
            )
            if self._mode == "hybrid" and self._embedding_provider != "off":
                try:
                    conn.execute("ALTER TABLE memories ADD COLUMN embedding_blob BLOB")
                except sqlite3.OperationalError:
                    pass  # column exists
            conn.commit()
        finally:
            conn.close()

    def _add_impl(
        self,
        user_id: str,
        messages: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        content = "\n".join(
            f"{m.get('role', '')}: {m.get('content', '')}" for m in messages if m.get("content")
        ).strip()
        if not content:
            return
        created_at = int(time.time())
        meta_json = json.dumps(metadata or {}, ensure_ascii=False) if metadata else None
        conn = self._conn()
        try:
            cursor = conn.execute(
                "INSERT INTO memories (user_id, content, created_at, metadata_json) VALUES (?, ?, ?, ?)",
                (user_id, content, created_at, meta_json),
            )
            rowid = cursor.lastrowid
            conn.execute("INSERT INTO memories_fts (rowid, content) VALUES (?, ?)", (rowid, content))
            if self._mode == "hybrid" and self._embedding_provider != "off":
                emb = self._get_embedding_sync(content)
                if emb is not None:
                    import struct
                    blob = struct.pack(f"{len(emb)}f", *emb)
                    conn.execute("UPDATE memories SET embedding_blob = ? WHERE id = ?", (blob, rowid))
            conn.commit()
        finally:
            conn.close()

    def _get_embedding_sync(self, text: str) -> Optional[List[float]]:
        """Sync embedding; returns None on failure (caller may skip blob)."""
        if self._embedding_provider == "off":
            return None
        if self._httpx_available is False:
            return None
        try:
            import httpx
        except ImportError:
            self._httpx_available = False
            logger.warning("httpx not installed; basket hybrid falls back to lexical")
            return None
        self._httpx_available = True
        text = (text or "")[:8192].strip()
        if not text:
            return None
        if self._embedding_provider == "ollama":
            return self._embed_ollama_sync(httpx, text)
        if self._embedding_provider == "openai":
            return self._embed_openai_sync(httpx, text)
        return None

    def _embed_ollama_sync(self, httpx: Any, text: str) -> Optional[List[float]]:
        model = self._embedding_model or "nomic-embed-text"
        try:
            r = httpx.post(
                f"{self._ollama_base_url}/api/embeddings",
                json={"model": model, "input": text},
                timeout=30.0,
            )
            r.raise_for_status()
            data = r.json()
            emb = data.get("embedding")
            return emb if isinstance(emb, list) else None
        except Exception as e:
            logger.debug("Ollama embedding failed: %s", e)
            return None

    def _embed_openai_sync(self, httpx: Any, text: str) -> Optional[List[float]]:
        import os
        key = self._openai_api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            logger.warning("OpenAI API key not set; basket hybrid embedding skipped")
            return None
        model = self._embedding_model or "text-embedding-3-small"
        try:
            r = httpx.post(
                f"{self._openai_base_url}/embeddings",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "input": text},
                timeout=30.0,
            )
            r.raise_for_status()
            data = r.json()
            emb_list = data.get("data") or []
            if emb_list and isinstance(emb_list[0].get("embedding"), list):
                return emb_list[0]["embedding"]
            return None
        except Exception as e:
            logger.debug("OpenAI embedding failed: %s", e)
            return None

    async def add(
        self,
        user_id: str,
        messages: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        await _run_sync(lambda: self._add_impl(user_id, messages, metadata))

    def _search_lexical_impl(
        self, user_id: str, query: str, limit: int
    ) -> List[MemoryItem]:
        conn = self._conn()
        try:
            query_escaped = query.replace('"', '""')
            cursor = conn.execute(
                """
                SELECT m.id, m.content, m.metadata_json, f.rank
                FROM memories m
                INNER JOIN (
                    SELECT rowid, bm25(memories_fts) AS rank
                    FROM memories_fts
                    WHERE memories_fts MATCH ?
                    ORDER BY rank
                    LIMIT 50
                ) f ON m.id = f.rowid
                WHERE m.user_id = ?
                ORDER BY f.rank
                LIMIT ?
                """,
                (f'"{query_escaped}"', user_id, limit),
            )
            rows = cursor.fetchall()
            items = []
            for row in rows:
                mem_id, content, meta_json, rank = row
                meta = {}
                if meta_json:
                    try:
                        meta = json.loads(meta_json)
                    except Exception:
                        pass
                score = -float(rank) if rank is not None else None
                items.append(MemoryItem(content=content or "", score=score, metadata=meta, id=str(mem_id)))
            return items
        except sqlite3.OperationalError as e:
            if "MATCH" in str(e) or "fts5" in str(e).lower():
                return self._search_lexical_fallback(conn, user_id, query, limit)
            raise
        finally:
            conn.close()

    def _search_lexical_fallback(
        self, conn: sqlite3.Connection, user_id: str, query: str, limit: int
    ) -> List[MemoryItem]:
        """Fallback when FTS MATCH fails (e.g. special chars): filter by user_id only."""
        cursor = conn.execute(
            "SELECT id, content, metadata_json FROM memories WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        items = []
        for row in cursor.fetchall():
            mem_id, content, meta_json = row
            meta = json.loads(meta_json) if meta_json else {}
            items.append(MemoryItem(content=content or "", score=None, metadata=meta, id=str(mem_id)))
        return items

    def _search_impl(
        self,
        user_id: str,
        query: str,
        limit: int,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryItem]:
        if not (query or "").strip():
            return []
        if self._mode != "hybrid" or self._embedding_provider == "off":
            return self._search_lexical_impl(user_id, query, limit)
        return self._search_hybrid_impl(user_id, query, limit, metadata_filter)

    def _search_hybrid_impl(
        self,
        user_id: str,
        query: str,
        limit: int,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryItem]:
        conn = self._conn()
        try:
            query_escaped = query.replace('"', '""')
            cursor = conn.execute(
                """
                SELECT m.id, m.content, m.metadata_json, m.embedding_blob, f.rank
                FROM memories m
                INNER JOIN (
                    SELECT rowid, bm25(memories_fts) AS rank
                    FROM memories_fts
                    WHERE memories_fts MATCH ?
                    ORDER BY rank
                    LIMIT 50
                ) f ON m.id = f.rowid
                WHERE m.user_id = ?
                ORDER BY f.rank
                LIMIT 50
                """,
                (f'"{query_escaped}"', user_id),
            )
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            cursor = conn.execute(
                "SELECT id, content, metadata_json, embedding_blob FROM memories WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
                (user_id,),
            )
            rows = [(r[0], r[1], r[2], r[3], None) for r in cursor.fetchall()]
        finally:
            conn.close()

        if not rows:
            return []
        query_emb = self._get_embedding_sync(query)
        if query_emb is None:
            return [
                MemoryItem(
                    content=row[1] or "",
                    score=-float(row[4]) if row[4] is not None else None,
                    metadata=json.loads(row[2]) if row[2] else {},
                    id=str(row[0]),
                )
                for row in rows[:limit]
            ]
        import struct
        scored = []
        for row in rows:
            mem_id, content, meta_json, blob, fts_rank = row
            meta = json.loads(meta_json) if meta_json else {}
            sim = 0.0
            if blob and len(blob) >= 4:
                try:
                    emb = list(struct.unpack(f"{len(blob)//4}f", blob))
                    sim = self._cosine_sim(query_emb, emb)
                except Exception:
                    pass
            fts_norm = -float(fts_rank) / 10.0 if fts_rank is not None else 0.0
            if fts_norm > 1:
                fts_norm = 1.0
            if fts_norm < 0:
                fts_norm = 0.0
            combined = self._semantic_weight * sim + (1.0 - self._semantic_weight) * fts_norm
            scored.append((combined, MemoryItem(content=content or "", score=combined, metadata=meta, id=str(mem_id))))
        scored.sort(key=lambda x: -x[0])
        return [item for _, item in scored[:limit]]

    @staticmethod
    def _cosine_sim(a: List[float], b: List[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    async def search(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryItem]:
        return await _run_sync(lambda: self._search_impl(user_id, query, limit, metadata_filter))

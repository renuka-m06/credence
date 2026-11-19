"""SQLite cache-first store and transparent search ledger for academic retrieval.

Rules (AGENTS.md):
- No HTTP call bypasses resolve/cache.py (cache-first) with timeout + retry/backoff.
- "Not found in databases" != fabricated. Report what was searched and where.
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import settings


def get_db_path(custom_path: Optional[Path | str] = None) -> Path:
    """Return database path ensuring parent directory exists."""
    if custom_path:
        p = Path(custom_path)
    else:
        p = settings.db_path
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def get_connection(db_path: Optional[Path | str] = None) -> sqlite3.Connection:
    """Open an SQLite connection with WAL mode and row factory."""
    path = get_db_path(db_path)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_cache(db_path: Optional[Path | str] = None) -> None:
    """Initialize database tables for payload cache and search ledger."""
    with get_connection(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS retrieval_cache (
                source TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                http_status INTEGER NOT NULL DEFAULT 200,
                created_at REAL NOT NULL,
                expires_at REAL,
                PRIMARY KEY (source, cache_key)
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS search_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference_raw TEXT NOT NULL,
                source_queried TEXT NOT NULL,
                query_string TEXT,
                status TEXT NOT NULL,  -- 'hit', 'miss', 'not_found', 'error', 'cached'
                details_json TEXT,
                timestamp TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_ref ON search_ledger(reference_raw);")
        conn.commit()


class CacheStore:
    """Cache-first interface for retrieval queries."""

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = get_db_path(db_path)
        init_cache(self.db_path)

    def get(self, source: str, key: str) -> Optional[dict[str, Any]]:
        """Retrieve payload from cache if present and not expired."""
        now = time.time()
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT payload_json, expires_at 
                FROM retrieval_cache 
                WHERE source = ? AND cache_key = ?
                """,
                (source.lower(), key.strip())
            )
            row = cursor.fetchone()
            if not row:
                return None

            payload_json, expires_at = row["payload_json"], row["expires_at"]
            if expires_at and expires_at < now:
                # Expired
                conn.execute(
                    "DELETE FROM retrieval_cache WHERE source = ? AND cache_key = ?",
                    (source.lower(), key.strip())
                )
                conn.commit()
                return None

            try:
                return json.loads(payload_json)
            except Exception:
                return None

    def set(
        self,
        source: str,
        key: str,
        payload: Any,
        http_status: int = 200,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Store payload in cache."""
        now = time.time()
        expires_at = (now + ttl_seconds) if ttl_seconds else None
        payload_str = json.dumps(payload, default=str)

        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO retrieval_cache (source, cache_key, payload_json, http_status, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, cache_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    http_status = excluded.http_status,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at
                """,
                (source.lower(), key.strip(), payload_str, http_status, now, expires_at)
            )
            conn.commit()

    def log_search(
        self,
        reference_raw: str,
        source: str,
        status: str,
        query_string: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record search attempt in transparent ledger."""
        ts = datetime.now(timezone.utc).isoformat()
        details_str = json.dumps(details or {}, default=str)
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO search_ledger (reference_raw, source_queried, query_string, status, details_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (reference_raw.strip(), source.lower(), query_string or "", status, details_str, ts)
            )
            conn.commit()

    def get_search_logs(self, reference_raw: Optional[str] = None) -> list[dict[str, Any]]:
        """Retrieve audit history of searches for human-reviewable reports."""
        with get_connection(self.db_path) as conn:
            if reference_raw:
                cursor = conn.execute(
                    """
                    SELECT id, reference_raw, source_queried, query_string, status, details_json, timestamp
                    FROM search_ledger
                    WHERE reference_raw = ?
                    ORDER BY id ASC
                    """,
                    (reference_raw.strip(),)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT id, reference_raw, source_queried, query_string, status, details_json, timestamp
                    FROM search_ledger
                    ORDER BY id ASC
                    """
                )
            rows = cursor.fetchall()
            logs = []
            for r in rows:
                details = {}
                try:
                    if r["details_json"]:
                        details = json.loads(r["details_json"])
                except Exception:
                    pass
                logs.append({
                    "id": r["id"],
                    "reference_raw": r["reference_raw"],
                    "source": r["source_queried"],
                    "query": r["query_string"],
                    "status": r["status"],
                    "details": details,
                    "timestamp": r["timestamp"],
                })
            return logs


# Default global cache instance
cache_store = CacheStore()

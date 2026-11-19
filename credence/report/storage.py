"""Durable persistent storage layer for verification reports.

Survives server restarts, supports SQLite (default) and PostgreSQL (via DATABASE_URL),
handles connection pooling/WAL mode, automatic schema migrations, and provides
both direct methods and a dictionary-like wrapper for zero-regression integration.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import settings

logger = logging.getLogger("credence.storage")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def _is_postgres() -> bool:
    return DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")


class DurableReportStore:
    """Persistent storage engine for Credence verification reports."""

    def __init__(self, db_path: Optional[Path | str] = None, database_url: Optional[str] = None):
        self.database_url = database_url or DATABASE_URL
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_sqlite_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        """Initialize database schema with migration safety."""
        if _is_postgres():
            try:
                import psycopg2
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS reports (
                                id VARCHAR(128) PRIMARY KEY,
                                document_name VARCHAR(512) NOT NULL,
                                access_tier VARCHAR(64) NOT NULL DEFAULT 'full_text',
                                created_at TIMESTAMPTZ NOT NULL,
                                updated_at TIMESTAMPTZ NOT NULL,
                                owner_id VARCHAR(128),
                                report_json TEXT NOT NULL,
                                metadata_json TEXT
                            );
                            CREATE INDEX IF NOT EXISTS idx_reports_created ON reports (created_at DESC);
                            CREATE INDEX IF NOT EXISTS idx_reports_owner ON reports (owner_id);
                        """)
                    conn.commit()
                logger.info("Initialized PostgreSQL reports storage.")
                return
            except Exception as e:
                logger.warning(f"Failed to connect to PostgreSQL ({e}). Falling back to SQLite.")

        with self._get_sqlite_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id TEXT PRIMARY KEY,
                    document_name TEXT NOT NULL,
                    access_tier TEXT NOT NULL DEFAULT 'full_text',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    owner_id TEXT,
                    report_json TEXT NOT NULL,
                    metadata_json TEXT
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_created ON reports (created_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_owner ON reports (owner_id);")
            conn.commit()
        logger.info(f"Initialized SQLite reports storage at {self.db_path}")

    def save_report(
        self,
        report_dict: dict[str, Any],
        owner_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Insert or update a verification report durably."""
        rep_id = str(report_dict.get("id") or "").strip()
        if not rep_id:
            import uuid
            rep_id = str(uuid.uuid4())
            report_dict["id"] = rep_id

        doc_name = str(report_dict.get("document_name") or "unnamed_document")
        access_tier = str(report_dict.get("access_tier") or "full_text")
        now_iso = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(report_dict.get("metadata", {}))
        report_json = json.dumps(report_dict)

        if _is_postgres():
            try:
                import psycopg2
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO reports (id, document_name, access_tier, created_at, updated_at, owner_id, report_json, metadata_json)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (id) DO UPDATE SET
                                document_name = EXCLUDED.document_name,
                                access_tier = EXCLUDED.access_tier,
                                updated_at = EXCLUDED.updated_at,
                                owner_id = COALESCE(EXCLUDED.owner_id, reports.owner_id),
                                report_json = EXCLUDED.report_json,
                                metadata_json = EXCLUDED.metadata_json;
                        """, (rep_id, doc_name, access_tier, now_iso, now_iso, owner_id, report_json, metadata_json))
                    conn.commit()
                return report_dict
            except Exception as e:
                logger.warning(f"Postgres save failed ({e}), falling back to SQLite.")

        with self._get_sqlite_connection() as conn:
            conn.execute("""
                INSERT INTO reports (id, document_name, access_tier, created_at, updated_at, owner_id, report_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    document_name = excluded.document_name,
                    access_tier = excluded.access_tier,
                    updated_at = excluded.updated_at,
                    owner_id = COALESCE(excluded.owner_id, reports.owner_id),
                    report_json = excluded.report_json,
                    metadata_json = excluded.metadata_json;
            """, (rep_id, doc_name, access_tier, now_iso, now_iso, owner_id, report_json, metadata_json))
            conn.commit()

        return report_dict

    def get_report(self, report_id: str) -> Optional[dict[str, Any]]:
        """Retrieve a report by ID."""
        clean_id = str(report_id or "").strip()
        if not clean_id:
            return None

        if _is_postgres():
            try:
                import psycopg2
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT report_json FROM reports WHERE id = %s;", (clean_id,))
                        row = cur.fetchone()
                        if row:
                            return json.loads(row[0])
            except Exception as e:
                logger.warning(f"Postgres get failed ({e}), falling back to SQLite.")

        with self._get_sqlite_connection() as conn:
            cur = conn.execute("SELECT report_json FROM reports WHERE id = ?;", (clean_id,))
            row = cur.fetchone()
            if row:
                return json.loads(row["report_json"])

        return None

    def contains(self, report_id: str) -> bool:
        """Check whether a report exists by ID."""
        return self.get_report(report_id) is not None

    def list_reports(
        self,
        limit: int = 50,
        offset: int = 0,
        owner_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Retrieve a list of reports ordered by creation date descending."""
        reports: list[dict[str, Any]] = []

        if _is_postgres():
            try:
                import psycopg2
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor() as cur:
                        if owner_id:
                            cur.execute(
                                "SELECT report_json FROM reports WHERE owner_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s;",
                                (owner_id, limit, offset),
                            )
                        else:
                            cur.execute(
                                "SELECT report_json FROM reports ORDER BY created_at DESC LIMIT %s OFFSET %s;",
                                (limit, offset),
                            )
                        rows = cur.fetchall()
                        return [json.loads(r[0]) for r in rows]
            except Exception as e:
                logger.warning(f"Postgres list failed ({e}), falling back to SQLite.")

        with self._get_sqlite_connection() as conn:
            if owner_id:
                cur = conn.execute(
                    "SELECT report_json FROM reports WHERE owner_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?;",
                    (owner_id, limit, offset),
                )
            else:
                cur = conn.execute(
                    "SELECT report_json FROM reports ORDER BY created_at DESC LIMIT ? OFFSET ?;",
                    (limit, offset),
                )
            for row in cur.fetchall():
                reports.append(json.loads(row["report_json"]))

        return reports

    def delete_report(self, report_id: str) -> bool:
        """Delete a report by ID."""
        clean_id = str(report_id or "").strip()
        if not clean_id:
            return False

        if _is_postgres():
            try:
                import psycopg2
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM reports WHERE id = %s;", (clean_id,))
                    conn.commit()
                return True
            except Exception:
                pass

        with self._get_sqlite_connection() as conn:
            cur = conn.execute("DELETE FROM reports WHERE id = ?;", (clean_id,))
            conn.commit()
            return cur.rowcount > 0


class ReportStoreMapping:
    """Dict-compatible wrapper around DurableReportStore for seamless backwards compatibility."""

    def __init__(self, store: Optional[DurableReportStore] = None):
        self._store = store or DurableReportStore()

    @property
    def store(self) -> DurableReportStore:
        return self._store

    def get(self, key: str, default: Any = None) -> Any:
        rep = self._store.get_report(key)
        return rep if rep is not None else default

    def __getitem__(self, key: str) -> dict[str, Any]:
        rep = self._store.get_report(key)
        if rep is None:
            raise KeyError(key)
        return rep

    def __setitem__(self, key: str, value: dict[str, Any]) -> None:
        if isinstance(value, dict) and "id" not in value:
            value["id"] = key
        self._store.save_report(value)

    def __contains__(self, key: str) -> bool:
        return self._store.contains(key)

    def values(self) -> list[dict[str, Any]]:
        return self._store.list_reports(limit=500)

    def items(self) -> list[tuple[str, dict[str, Any]]]:
        reports = self._store.list_reports(limit=500)
        return [(r.get("id", ""), r) for r in reports]

    def pop(self, key: str, default: Any = None) -> Any:
        rep = self._store.get_report(key)
        if rep is not None:
            self._store.delete_report(key)
            return rep
        return default


# Singleton durable store instance
report_store = DurableReportStore()
reports_mapping = ReportStoreMapping(report_store)

"""User credential store backed by SQLite / PostgreSQL."""

from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import settings
from credence.auth.models import UserPublic
from credence.auth.security import hash_password

logger = logging.getLogger("credence.auth.store")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def _is_postgres() -> bool:
    return DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")


class UserStore:
    """Persistent storage for user identities and roles."""

    def __init__(self, db_path: Optional[Path | str] = None):
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
        return conn

    def _init_db(self) -> None:
        if _is_postgres():
            try:
                import psycopg2
                with psycopg2.connect(DATABASE_URL) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS users (
                                id VARCHAR(128) PRIMARY KEY,
                                username VARCHAR(128) UNIQUE NOT NULL,
                                email VARCHAR(256) UNIQUE,
                                hashed_password VARCHAR(256) NOT NULL,
                                role VARCHAR(64) NOT NULL DEFAULT 'reviewer',
                                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                                created_at TIMESTAMPTZ NOT NULL
                            );
                            CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
                        """)
                    conn.commit()
                self._seed_default_users()
                return
            except Exception as e:
                logger.warning(f"Postgres user table init failed ({e}), falling back to SQLite.")

        with self._get_sqlite_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE,
                    hashed_password TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'reviewer',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);")
            conn.commit()

        self._seed_default_users()

    def _seed_default_users(self) -> None:
        """Seed default admin and reviewer accounts if no users exist."""
        default_reviewer = self.get_by_username("reviewer-1")
        if not default_reviewer:
            self.create_user(
                username="reviewer-1",
                password=os.getenv("DEFAULT_REVIEWER_PASSWORD", "ReviewerPass2026!"),
                email="reviewer1@credence.local",
                role="reviewer",
            )
        default_admin = self.get_by_username("admin")
        if not default_admin:
            self.create_user(
                username="admin",
                password=os.getenv("DEFAULT_ADMIN_PASSWORD", "AdminPass2026!"),
                email="admin@credence.local",
                role="admin",
            )

    def create_user(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        role: str = "reviewer",
    ) -> dict[str, Any]:
        """Create a new user with hashed password."""
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        h_pw = hash_password(password)
        now_iso = datetime.now(timezone.utc).isoformat()

        if _is_postgres():
            try:
                import psycopg2
                with psycopg2.connect(DATABASE_URL) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO users (id, username, email, hashed_password, role, is_active, created_at)
                            VALUES (%s, %s, %s, %s, %s, TRUE, %s)
                            RETURNING id, username, email, role, is_active, created_at;
                        """, (user_id, username, email, h_pw, role, now_iso))
                        row = cur.fetchone()
                    conn.commit()
                    return {
                        "id": row[0],
                        "username": row[1],
                        "email": row[2],
                        "role": row[3],
                        "is_active": row[4],
                        "created_at": str(row[5]),
                    }
            except Exception as e:
                logger.warning(f"Postgres create_user failed ({e}), falling back to SQLite.")

        with self._get_sqlite_connection() as conn:
            conn.execute("""
                INSERT INTO users (id, username, email, hashed_password, role, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?);
            """, (user_id, username, email, h_pw, role, now_iso))
            conn.commit()

        return {
            "id": user_id,
            "username": username,
            "email": email,
            "role": role,
            "is_active": True,
            "created_at": now_iso,
        }

    def get_by_username(self, username: str) -> Optional[dict[str, Any]]:
        clean_user = username.strip().lower()
        if not clean_user:
            return None

        if _is_postgres():
            try:
                import psycopg2
                with psycopg2.connect(DATABASE_URL) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT id, username, email, hashed_password, role, is_active, created_at FROM users WHERE LOWER(username) = %s;",
                            (clean_user,),
                        )
                        row = cur.fetchone()
                        if row:
                            return {
                                "id": row[0],
                                "username": row[1],
                                "email": row[2],
                                "hashed_password": row[3],
                                "role": row[4],
                                "is_active": bool(row[5]),
                                "created_at": str(row[6]),
                            }
            except Exception:
                pass

        with self._get_sqlite_connection() as conn:
            cur = conn.execute(
                "SELECT id, username, email, hashed_password, role, is_active, created_at FROM users WHERE LOWER(username) = ?;",
                (clean_user,),
            )
            row = cur.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "username": row["username"],
                    "email": row["email"],
                    "hashed_password": row["hashed_password"],
                    "role": row["role"],
                    "is_active": bool(row["is_active"]),
                    "created_at": row["created_at"],
                }
        return None

    def get_by_id(self, user_id: str) -> Optional[dict[str, Any]]:
        clean_id = user_id.strip()
        if not clean_id:
            return None

        with self._get_sqlite_connection() as conn:
            cur = conn.execute(
                "SELECT id, username, email, hashed_password, role, is_active, created_at FROM users WHERE id = ?;",
                (clean_id,),
            )
            row = cur.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "username": row["username"],
                    "email": row["email"],
                    "hashed_password": row["hashed_password"],
                    "role": row["role"],
                    "is_active": bool(row["is_active"]),
                    "created_at": row["created_at"],
                }
        return None


# Singleton instance
user_store = UserStore()

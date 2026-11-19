"""Append-only SQLite review ledger for human-in-the-loop auditability.

Golden Rules (AGENTS.md):
- Core principle: EVERY VERDICT CARRIES PROOF. Never present a result as a final academic judgment — it's a triage aid, open to human review.
- Default stance = human review. No silent auto-decisions.
- Append-only ledger: Every review action (accept, override, comment) is permanently recorded and never deleted or overwritten.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import settings


def get_db_path(custom_path: Optional[Path | str] = None) -> Path:
    """Return SQLite database path, ensuring parent directory exists."""
    if custom_path:
        p = Path(custom_path)
    else:
        p = settings.db_path
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def get_connection(db_path: Optional[Path | str] = None) -> sqlite3.Connection:
    """Open an SQLite connection configured with WAL mode and dict-like row factory."""
    path = get_db_path(db_path)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_ledger(db_path: Optional[Path | str] = None) -> None:
    """Initialize the append-only review_ledger table and indexes."""
    with get_connection(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS review_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id TEXT UNIQUE NOT NULL,
                claim_id TEXT NOT NULL,
                action TEXT NOT NULL,
                override_verdict TEXT,
                comment TEXT,
                reviewer_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_claim_id ON review_ledger (claim_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_created_at ON review_ledger (created_at);")
        conn.commit()


# Auto-initialize ledger on module import
init_ledger()


def record_review(
    claim_id: str,
    action: str,
    override_verdict: Optional[str] = None,
    comment: Optional[str] = None,
    reviewer_id: str = "reviewer-1",
    db_path: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Append a human review action to the immutable SQLite ledger.

    Supported actions:
      - 'accept': Reviewer affirms the algorithmic verdict based on proof.
      - 'override': Reviewer changes the verdict (e.g. 'supported', 'contradictory').
      - 'comment': Reviewer annotates claim with academic commentary.
    """
    clean_action = str(action).strip().lower()
    if clean_action not in ("accept", "override", "comment"):
        raise ValueError(f"Invalid review action '{action}'. Must be 'accept', 'override', or 'comment'.")

    clean_verdict = None
    if clean_action == "override":
        if not override_verdict:
            raise ValueError("Override action requires an 'override_verdict'.")
        clean_verdict = str(override_verdict).strip().lower()

    review_id = f"rev-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO review_ledger (
                review_id, claim_id, action, override_verdict, comment, reviewer_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                review_id,
                str(claim_id),
                clean_action,
                clean_verdict,
                comment.strip() if comment else None,
                str(reviewer_id or "reviewer-1"),
                now_iso,
            ),
        )
        conn.commit()

    return {
        "review_id": review_id,
        "claim_id": str(claim_id),
        "action": clean_action,
        "override_verdict": clean_verdict,
        "comment": comment.strip() if comment else None,
        "reviewer_id": str(reviewer_id or "reviewer-1"),
        "created_at": now_iso,
    }


def get_reviews_for_claim(claim_id: str, db_path: Optional[Path | str] = None) -> list[dict[str, Any]]:
    """Retrieve all review events for a given claim in chronological order."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT review_id, claim_id, action, override_verdict, comment, reviewer_id, created_at
            FROM review_ledger
            WHERE claim_id = ?
            ORDER BY id ASC;
            """,
            (str(claim_id),),
        ).fetchall()

    return [dict(r) for r in rows]


def get_latest_override(claim_id: str, db_path: Optional[Path | str] = None) -> Optional[dict[str, Any]]:
    """Retrieve the most recent override review for a claim, if any."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT review_id, claim_id, action, override_verdict, comment, reviewer_id, created_at
            FROM review_ledger
            WHERE claim_id = ? AND action = 'override'
            ORDER BY id DESC
            LIMIT 1;
            """,
            (str(claim_id),),
        ).fetchone()

    return dict(row) if row else None


def get_audit_log(limit: int = 100, db_path: Optional[Path | str] = None) -> list[dict[str, Any]]:
    """Retrieve the global chronological audit log across all claims (newest first)."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT review_id, claim_id, action, override_verdict, comment, reviewer_id, created_at
            FROM review_ledger
            ORDER BY id DESC
            LIMIT ?;
            """,
            (max(1, int(limit)),),
        ).fetchall()

    return [dict(r) for r in rows]


def apply_ledger_to_claim(claim_data: dict[str, Any], db_path: Optional[Path | str] = None) -> dict[str, Any]:
    """Apply ledger history and latest active override to a serialized claim dictionary.

    Ensures overrides persist across page reload and API queries.
    """
    claim_id = str(claim_data.get("id", ""))
    if not claim_id:
        return claim_data

    reviews = get_reviews_for_claim(claim_id, db_path=db_path)
    claim_data["reviews"] = reviews

    latest_ov = get_latest_override(claim_id, db_path=db_path)
    if latest_ov and latest_ov.get("override_verdict"):
        new_v = latest_ov["override_verdict"]
        verdict_obj = claim_data.get("verdict")
        if isinstance(verdict_obj, dict):
            verdict_obj["verdict"] = new_v
            verdict_obj["display_verdict"] = f"{new_v.capitalize()} (Overridden)"
            verdict_obj["needs_review"] = (new_v == "needs review")
            verdict_obj["override_info"] = latest_ov

    return claim_data


def apply_ledger_to_report(report_data: dict[str, Any], db_path: Optional[Path | str] = None) -> dict[str, Any]:
    """Apply ledger history to all claims in a report and recalculate summary counters."""
    claims = report_data.get("claims", [])
    updated_claims = []
    overrides_count = 0

    for c in claims:
        c_dict = apply_ledger_to_claim(c, db_path=db_path)
        if c_dict.get("verdict", {}).get("override_info"):
            overrides_count += 1
        updated_claims.append(c_dict)

    report_data["claims"] = updated_claims

    # Recalculate summary counts based on effective verdicts
    supported_cnt = 0
    partial_cnt = 0
    unsupported_cnt = 0
    contradictory_cnt = 0
    review_cnt = 0

    for c in updated_claims:
        v_str = (c.get("verdict", {}).get("verdict") or "").lower()
        if "partially" in v_str or "partial" in v_str:
            partial_cnt += 1
        elif "contradict" in v_str:
            contradictory_cnt += 1
        elif "unsupport" in v_str:
            unsupported_cnt += 1
        elif "support" in v_str:
            supported_cnt += 1
        else:
            review_cnt += 1

    summary = report_data.get("summary", {})
    summary["supported"] = supported_cnt
    summary["partially_supported"] = partial_cnt
    summary["unsupported"] = unsupported_cnt
    summary["contradictory"] = contradictory_cnt
    summary["needs_review"] = review_cnt
    summary["human_overrides"] = overrides_count
    summary["human_review_required"] = review_cnt > 0 or partial_cnt > 0 or contradictory_cnt > 0
    report_data["summary"] = summary

    return report_data

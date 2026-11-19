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


VALID_ACTIONS = {"accept", "override", "comment"}
VALID_VERDICTS = {
    "supported",
    "partially supported",
    "unsupported",
    "contradictory",
    "needs review",
    "potentially outdated",
}


def init_ledger(db_path: Optional[Path | str] = None) -> None:
    """Initialize the append-only review_ledger table and indexes with migration support."""
    with get_connection(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS review_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id TEXT UNIQUE NOT NULL,
                claim_id TEXT NOT NULL,
                action TEXT NOT NULL,
                original_verdict TEXT,
                override_verdict TEXT,
                explanation TEXT,
                comment TEXT,
                reviewer_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        # Backward-compatible migrations for existing databases
        for col in ("original_verdict", "explanation"):
            try:
                conn.execute(f"ALTER TABLE review_ledger ADD COLUMN {col} TEXT;")
            except sqlite3.OperationalError:
                pass

        conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_claim_id ON review_ledger (claim_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_created_at ON review_ledger (created_at);")
        conn.commit()


# Auto-initialize ledger on module import
init_ledger()


def record_review(
    claim_id: str,
    action: str,
    override_verdict: Optional[str] = None,
    explanation: Optional[str] = None,
    comment: Optional[str] = None,
    original_verdict: Optional[str] = None,
    reviewer_id: str = "reviewer-1",
    db_path: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Append a human review action to the immutable SQLite ledger.

    Supported actions:
      - 'accept': Reviewer affirms the algorithmic verdict based on proof.
      - 'override': Reviewer changes the verdict (requires mandatory explanation).
      - 'comment': Reviewer annotates claim with academic commentary.
    """
    clean_claim_id = str(claim_id or "").strip()
    if not clean_claim_id or clean_claim_id.lower() in ("undefined", "null", "none"):
        raise ValueError("Invalid claim ID provided.")

    clean_action = str(action).strip().lower()
    if clean_action not in VALID_ACTIONS:
        raise ValueError(f"Invalid review action '{action}'. Must be 'accept', 'override', or 'comment'.")

    # Resolve explanation / comment
    clean_expl = (explanation if explanation is not None else comment or "").strip()
    clean_comment = (comment if comment is not None else explanation or "").strip()

    clean_verdict = None
    if clean_action == "override":
        if not override_verdict or not str(override_verdict).strip():
            raise ValueError("Override action requires an 'override_verdict'.")
        clean_verdict = str(override_verdict).strip().lower()
        if clean_verdict not in VALID_VERDICTS:
            raise ValueError(
                f"Invalid override verdict '{override_verdict}'. Must be one of: "
                f"{', '.join(sorted(VALID_VERDICTS))}."
            )
        if not clean_expl:
            raise ValueError("Action 'override' requires a mandatory explanation.")

    clean_orig_verdict = str(original_verdict).strip().lower() if original_verdict else None

    review_id = f"rev-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO review_ledger (
                review_id, claim_id, action, original_verdict, override_verdict,
                explanation, comment, reviewer_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                review_id,
                clean_claim_id,
                clean_action,
                clean_orig_verdict,
                clean_verdict,
                clean_expl if clean_expl else None,
                clean_comment if clean_comment else None,
                str(reviewer_id or "reviewer-1"),
                now_iso,
            ),
        )
        conn.commit()

    return {
        "review_id": review_id,
        "claim_id": clean_claim_id,
        "action": clean_action,
        "original_verdict": clean_orig_verdict,
        "override_verdict": clean_verdict,
        "explanation": clean_expl if clean_expl else None,
        "comment": clean_comment if clean_comment else None,
        "reviewer_id": str(reviewer_id or "reviewer-1"),
        "created_at": now_iso,
    }


def _hydrate_review_dict(r: sqlite3.Row) -> dict[str, Any]:
    """Helper to convert row to dictionary ensuring both explanation and comment keys exist."""
    d = dict(r)
    expl = d.get("explanation") or d.get("comment") or ""
    d["explanation"] = expl
    d["comment"] = d.get("comment") or expl
    return d


def get_reviews_for_claim(claim_id: str, db_path: Optional[Path | str] = None) -> list[dict[str, Any]]:
    """Retrieve all review events for a given claim in chronological order."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT review_id, claim_id, action, original_verdict, override_verdict,
                   explanation, comment, reviewer_id, created_at
            FROM review_ledger
            WHERE claim_id = ?
            ORDER BY id ASC;
            """,
            (str(claim_id),),
        ).fetchall()

    return [_hydrate_review_dict(r) for r in rows]


def get_latest_override(claim_id: str, db_path: Optional[Path | str] = None) -> Optional[dict[str, Any]]:
    """Retrieve the most recent override review for a claim, if any."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT review_id, claim_id, action, original_verdict, override_verdict,
                   explanation, comment, reviewer_id, created_at
            FROM review_ledger
            WHERE claim_id = ? AND action = 'override'
            ORDER BY id DESC
            LIMIT 1;
            """,
            (str(claim_id),),
        ).fetchone()

    return _hydrate_review_dict(row) if row else None


def get_audit_log(limit: int = 100, db_path: Optional[Path | str] = None) -> list[dict[str, Any]]:
    """Retrieve the global chronological audit log across all claims (newest first)."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT review_id, claim_id, action, original_verdict, override_verdict,
                   explanation, comment, reviewer_id, created_at
            FROM review_ledger
            ORDER BY id DESC
            LIMIT ?;
            """,
            (max(1, int(limit)),),
        ).fetchall()

    return [_hydrate_review_dict(r) for r in rows]


def apply_ledger_to_claim(claim_data: dict[str, Any], db_path: Optional[Path | str] = None) -> dict[str, Any]:
    """Apply ledger history and latest active override to a serialized claim dictionary.

    Ensures overrides persist across page reload and API queries while preserving
    the original automated verdict.
    """
    claim_id = str(claim_data.get("id", ""))
    if not claim_id:
        return claim_data

    reviews = get_reviews_for_claim(claim_id, db_path=db_path)
    claim_data["reviews"] = reviews

    verdict_obj = claim_data.get("verdict")
    if isinstance(verdict_obj, dict):
        # Preserve original automated verdict permanently
        if "original_verdict" not in verdict_obj or not verdict_obj["original_verdict"]:
            verdict_obj["original_verdict"] = verdict_obj.get("verdict")

        latest_ov = get_latest_override(claim_id, db_path=db_path)
        if latest_ov and latest_ov.get("override_verdict"):
            new_v = latest_ov["override_verdict"]
            verdict_obj["verdict"] = new_v
            verdict_obj["display_verdict"] = f"{new_v.capitalize()} (Overridden)"
            verdict_obj["needs_review"] = (new_v == "needs review")
            verdict_obj["override_info"] = latest_ov

    return claim_data

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

"""FastAPI router for human review ledger endpoints.

Endpoints:
- POST /claims/{claim_id}/review: Record human action (accept | override | comment) in SQLite ledger
- GET /claims/{claim_id}/reviews: Retrieve past actions for a claim
- GET /audit: Retrieve global chronological audit ledger
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from credence.report.ledger import (
    get_audit_log,
    get_latest_override,
    get_reviews_for_claim,
    record_review,
)

router = APIRouter(tags=["review"])


class ReviewRequest(BaseModel):
    action: str = Field(..., description="Action: 'accept', 'override', or 'comment'")
    override_verdict: Optional[str] = Field(None, description="Target verdict if action is 'override'")
    comment: Optional[str] = Field(None, description="Reviewer commentary or rationale")
    reviewer_id: Optional[str] = Field("reviewer-1", description="Identifier of the human reviewer")


@router.post("/claims/{claim_id}/review")
def review_claim_endpoint(claim_id: str, payload: ReviewRequest) -> dict[str, Any]:
    """Append a human review action (accept, override, comment) to the immutable SQLite ledger."""
    action = payload.action.strip().lower()
    if action not in ("accept", "override", "comment"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action '{payload.action}'. Expected 'accept', 'override', or 'comment'.",
        )

    if action == "override" and not payload.override_verdict:
        raise HTTPException(
            status_code=400,
            detail="Action 'override' requires 'override_verdict' to be provided.",
        )

    try:
        entry = record_review(
            claim_id=claim_id,
            action=action,
            override_verdict=payload.override_verdict,
            comment=payload.comment,
            reviewer_id=payload.reviewer_id or "reviewer-1",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "status": "ok",
        "claim_id": claim_id,
        "review": entry,
    }


@router.get("/claims/{claim_id}/reviews")
def get_claim_reviews_endpoint(claim_id: str) -> dict[str, Any]:
    """Retrieve all chronological review actions for a specific claim."""
    reviews = get_reviews_for_claim(claim_id)
    latest_override = get_latest_override(claim_id)
    return {
        "status": "ok",
        "claim_id": claim_id,
        "reviews": reviews,
        "latest_override": latest_override,
        "total_reviews": len(reviews),
    }


@router.get("/audit")
def get_audit_log_endpoint(limit: int = Query(100, ge=1, le=1000)) -> dict[str, Any]:
    """Retrieve the global audit log across all reviewed claims."""
    audit_entries = get_audit_log(limit=limit)
    return {
        "status": "ok",
        "audit_log": audit_entries,
        "reviews": audit_entries,
        "count": len(audit_entries),
    }

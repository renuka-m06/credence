"""FastAPI router for human review ledger endpoints.

Endpoints:
- POST /claims/{claim_id}/review: Record human action (accept | override | comment) in SQLite ledger
- GET /claims/{claim_id}/reviews: Retrieve past actions for a claim
- GET /audit: Retrieve global chronological audit ledger
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from credence.api.export import (
    generate_html_export,
    generate_json_export,
    generate_markdown_export,
)
from credence.report.ledger import (
    apply_ledger_to_report,
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


@router.get("/benchmark")
def get_benchmark_endpoint() -> dict[str, Any]:
    """Retrieve real gold-standard evaluation benchmark numbers from Member 1's score module."""
    bench_file = Path("data/benchmark_results.json")
    if bench_file.exists():
        with open(bench_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # Dynamic fallback to evaluate gold_set.jsonl if results JSON not pre-saved
    from credence.benchmark.score import evaluate_benchmark
    rep = evaluate_benchmark("gold_set.jsonl")
    return rep.to_dict()


@router.get("/report/{report_id}/export")
def export_report_endpoint(
    report_id: str,
    format: str = Query("html", description="Export format: 'html', 'markdown', 'md', or 'json'"),
) -> Response:
    """Export a verified academic claim report as a downloadable file (HTML, Markdown, or JSON)."""
    import credence.server as srv

    rep: Optional[dict[str, Any]] = None
    if report_id in ("demo-report-1", "demo", "sample", "default"):
        rep = srv.REPORTS_STORE.get("demo-report-1") or srv._generate_demo_report()
    else:
        rep = srv.REPORTS_STORE.get(report_id)

    if not rep:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found for export.")

    # Apply SQLite human review ledger overrides before exporting
    rep_with_ledger = apply_ledger_to_report(dict(rep))
    clean_fmt = format.strip().lower()
    doc_slug = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(rep.get("document_name", "report")))

    if clean_fmt in ("html", "pdf"):
        content = generate_html_export(rep_with_ledger)
        return Response(
            content=content,
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename=credence_{doc_slug}_export.html"},
        )
    elif clean_fmt in ("markdown", "md"):
        content = generate_markdown_export(rep_with_ledger)
        return Response(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=credence_{doc_slug}_export.md"},
        )
    elif clean_fmt == "json":
        content = generate_json_export(rep_with_ledger)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=credence_{doc_slug}_export.json"},
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported export format '{format}'. Supported formats: html, markdown, md, json.",
        )

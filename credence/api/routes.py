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
    explanation: Optional[str] = Field(None, description="Mandatory explanation if action is 'override'")
    comment: Optional[str] = Field(None, description="Reviewer commentary or rationale alias")
    original_verdict: Optional[str] = Field(None, description="Original automated verdict before override")
    reviewer_id: Optional[str] = Field("reviewer-1", description="Identifier of the human reviewer")


@router.post("/claims/{claim_id}/review")
def review_claim_endpoint(claim_id: str, payload: ReviewRequest) -> dict[str, Any]:
    """Append a human review action (accept, override, comment) to the immutable SQLite ledger."""
    clean_id = str(claim_id or "").strip()
    if not clean_id or clean_id.lower() in ("undefined", "null", "none"):
        raise HTTPException(
            status_code=400,
            detail="Invalid claim ID provided.",
        )

    action = payload.action.strip().lower()
    if action not in ("accept", "override", "comment"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action '{payload.action}'. Expected 'accept', 'override', or 'comment'.",
        )

    explanation = (payload.explanation if payload.explanation is not None else payload.comment or "").strip()

    if action == "override":
        if not payload.override_verdict:
            raise HTTPException(
                status_code=400,
                detail="Action 'override' requires 'override_verdict' to be provided.",
            )
        norm_verdict = payload.override_verdict.strip().lower()
        from credence.report.ledger import VALID_VERDICTS
        if norm_verdict not in VALID_VERDICTS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid override verdict '{payload.override_verdict}'. Must be one of: "
                    f"{', '.join(sorted(VALID_VERDICTS))}."
                ),
            )
        if not explanation:
            raise HTTPException(
                status_code=400,
                detail="Action 'override' requires a mandatory explanation.",
            )

    # Resolve original automated verdict from memory store if not provided
    orig_v = payload.original_verdict
    import credence.server as srv
    if not orig_v:
        for rep in srv.REPORTS_STORE.values():
            for c in rep.get("claims", []):
                if c.get("id") == clean_id:
                    orig_v = c.get("verdict", {}).get("original_verdict") or c.get("verdict", {}).get("verdict")
                    break
            if orig_v:
                break

    try:
        entry = record_review(
            claim_id=clean_id,
            action=action,
            override_verdict=payload.override_verdict,
            explanation=explanation,
            comment=explanation,
            original_verdict=orig_v,
            reviewer_id=payload.reviewer_id or "reviewer-1",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Synchronize in-memory active reports with the latest ledger override
    for rep_key, rep in list(srv.REPORTS_STORE.items()):
        srv.REPORTS_STORE[rep_key] = apply_ledger_to_report(dict(rep))

    return {
        "status": "ok",
        "claim_id": clean_id,
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


@router.get("/report/{report_id}/missing-citations")
def get_report_missing_citations_router(report_id: str) -> dict[str, Any]:
    """Retrieve missing citation diagnostic warnings for a verified report (Requirement 6)."""
    import credence.server as srv

    rep: Optional[dict[str, Any]] = None
    if report_id in ("demo-report-1", "demo", "sample", "default"):
        rep = srv.REPORTS_STORE.get("demo-report-1") or srv._generate_demo_report()
    else:
        rep = srv.REPORTS_STORE.get(report_id)

    if not rep:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")

    rep_with_ledger = apply_ledger_to_report(dict(rep))
    warnings = rep_with_ledger.get("missing_citations", [])
    return {
        "status": "ok",
        "report_id": report_id,
        "document_name": rep_with_ledger.get("document_name", ""),
        "total_warnings": len(warnings),
        "missing_citations": warnings,
        "summary": rep_with_ledger.get("summary", {}),
    }


@router.get("/report/{report_id}/claims/{claim_id}/source")
@router.get("/claims/{claim_id}/source")
def inspect_source_evidence(claim_id: str, report_id: Optional[str] = None) -> dict[str, Any]:
    """Retrieve full source paper context, section, page/paragraph, and highlighted evidence (Requirement 5)."""
    import credence.server as srv
    clean_cid = str(claim_id or "").strip()
    target_report = None
    target_claim = None

    if report_id:
        target_report = srv.REPORTS_STORE.get(report_id)

    if not target_report:
        for rep in srv.REPORTS_STORE.values():
            for c in rep.get("claims", []):
                if c.get("id") == clean_cid:
                    target_report = rep
                    target_claim = c
                    break
            if target_claim:
                break

    if not target_claim and target_report:
        target_claim = next((c for c in target_report.get("claims", []) if c.get("id") == clean_cid), None)

    if not target_claim:
        # Fallback to demo report
        demo_rep = srv.REPORTS_STORE.get("demo-report-1") or srv._generate_demo_report()
        target_claim = next((c for c in demo_rep.get("claims", []) if c.get("id") == clean_cid), None)
        target_report = demo_rep

    if not target_claim:
        raise HTTPException(status_code=404, detail=f"Claim '{clean_cid}' not found.")

    slot_results = target_claim.get("slot_results", [])
    verified_sr = next((r for r in slot_results if r.get("quote_verified")), None)
    best_sr = verified_sr or (slot_results[0] if slot_results else {})

    quote_text = best_sr.get("quote") or target_claim.get("exact_quotation") or ""
    is_verified = bool(best_sr.get("quote_verified", False))

    paper_title = (
        best_sr.get("source_title")
        or target_claim.get("paper_title")
        or (f"Cited Publication for [{target_claim.get('citation_keys', ['1'])[0] if target_claim.get('citation_keys') else '1'}]")
    )
    doi = best_sr.get("source_doi") or target_claim.get("doi")
    page_num = best_sr.get("page_number") or target_claim.get("page_number")
    sec_name = best_sr.get("section_name") or target_claim.get("section_name") or "Results"
    para_num = best_sr.get("paragraph_number") or target_claim.get("paragraph_number")
    src_loc = best_sr.get("source_location") or target_claim.get("source_location")

    verdict_info = target_claim.get("verdict", {})
    verdict_display = verdict_info.get("display_verdict") or verdict_info.get("verdict") or "Needs review"

    # Generate source context with evidence highlight (Golden Rule 8: only confirm if code-verified)
    if is_verified and quote_text:
        highlighted = f"<mark class=\"evidence-highlight\" id=\"source-evidence-anchor\">{quote_text}</mark>"
    elif quote_text:
        highlighted = f"<span class=\"unverified-evidence\" id=\"source-evidence-anchor\">{quote_text}</span>"
    else:
        highlighted = "<span class=\"missing-evidence\">Source inaccessible: verbatim proof pending manual triage.</span>"

    return {
        "status": "ok",
        "claim_id": clean_cid,
        "claim_text": target_claim.get("text", ""),
        "paper_title": paper_title,
        "doi": doi,
        "source_url": best_sr.get("source_url") or (f"https://doi.org/{doi}" if doi else None),
        "page_number": page_num,
        "section_name": sec_name,
        "paragraph_number": para_num,
        "source_location": src_loc,
        "is_docx": para_num is not None and page_num is None,
        "exact_quotation": quote_text,
        "quote_verified": is_verified,
        "quote_span": best_sr.get("quote_span"),
        "verdict": verdict_display,
        "evidence_highlight": highlighted,
        "source_context": f"Section [{sec_name}]: {quote_text}",
    }

"""FastAPI backend exposing verification endpoints and persistent report storage.

Endpoints:
- POST /verify: Manuscript file upload -> Report JSON (hardened with magic-byte validation, size ceiling & scholarly resolution)
- GET /report/{id}: Fetch report by ID (persisted across server restarts via SQLite/PostgreSQL)
- POST /report/{id}/review: Record human reviewer action (Accept / Override / Comment)
- GET /demo/report: Instant offline verification report on sample data
- GET /health: Health check endpoint for cloud orchestration
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import settings
from credence.api.routes import router as api_router
from credence.auth.deps import get_current_user_optional
from credence.auth.models import UserPublic
from credence.auth.routes import router as auth_router
from credence.ingest.citations import audit_missing_citations, map_citations
from credence.ingest.claims import extract_claims
from credence.ingest.parse import parse_document
from credence.report.ledger import apply_ledger_to_report, record_review
from credence.report.models import AccessTier, Claim, Report, Verdict, VerdictType
from credence.report.storage import report_store, reports_mapping
from credence.resolve.sources import UnifiedResolver
from credence.security.rate_limiter import rate_limit_dependency
from credence.security.upload import validate_and_save_upload
from credence.verify.pipeline import build_report, verify_claim
from credence.verify.red_team import get_investigations_for_claim, run_red_team_investigation

logger = logging.getLogger("credence.server")

app = FastAPI(
    title="Credence Verification API",
    description="Scientific claim verification against citations with deterministic proof.",
    version="1.0.0",
)

# CORS configuration with environment-driven origin whitelist
ALLOWED_ORIGINS_RAW = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000"
)
ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS_RAW.split(",") if o.strip()]
is_wildcard = "*" in ALLOWED_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if not is_wildcard else ["*"],
    allow_credentials=not is_wildcard,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Centralized exception handler: logs tracebacks internally while returning safe JSON."""
    logger.exception(f"Unhandled error processing {request.method} {request.url.path}: {exc}")
    is_prod = os.getenv("CREDENCE_ENV", "development").lower() in ("production", "prod")
    detail = "An internal server error occurred while processing the verification request." if is_prod else str(exc)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "detail": detail, "path": request.url.path},
    )


# Include authentication, review ledger, export and audit API routes
app.include_router(auth_router)
app.include_router(api_router)

# Durable storage mapping for verification reports (persists to SQLite/PostgreSQL across restarts)
REPORTS_STORE = reports_mapping


class ReviewAction(BaseModel):
    action: str  # 'accept', 'override', 'comment'
    override_verdict: Optional[str] = None
    explanation: Optional[str] = None
    comment: Optional[str] = None
    original_verdict: Optional[str] = None
    reviewer_id: Optional[str] = "reviewer-1"


class TextVerifyRequest(BaseModel):
    claim_text: str
    source_text: str
    access_tier: Optional[str] = "full_text"
    citation_key: Optional[str] = "4"


def _generate_demo_report() -> dict[str, Any]:
    """Generate deterministic report on sample demo data without live API calls."""
    c1 = verify_claim(
        claim_input="LearnFast improved test scores by 30% [4]",
        source_text=(
            "Background: Educational software interventions were evaluated. "
            "In our pilot evaluation involving 40 students with no control group, "
            "test scores increased by 12.1%. Further randomized trials are required to establish efficacy."
        ),
        access_tier=AccessTier.FULL_TEXT,
        citation_key="4",
    )
    c1.id = "claim-1"
    c1.source_location = "Results, page 2"
    c1.page_number = 2
    c1.section_name = "Results"
    c1.paper_title = "Educational Software Interventions in Higher Education"
    c1.doi = "10.1145/3065386"
    for sr in c1.slot_results:
        sr.source_title = c1.paper_title
        sr.source_doi = c1.doi
        sr.page_number = 2
        sr.section_name = "Results"
        sr.source_location = "Results, page 2"

    c2 = verify_claim(
        claim_input="Patients receiving Compound-X demonstrated a 12.1% reduction in 30-day mortality [1]",
        source_text=(
            "In a double-blind, randomized controlled trial involving 1,450 patients, "
            "patients receiving Compound-X demonstrated a 12.1% reduction in 30-day mortality "
            "compared with the placebo arm (p = 0.003)."
        ),
        access_tier=AccessTier.FULL_TEXT,
        citation_key="1",
    )
    c2.id = "claim-2"
    c2.source_location = "Results, page 3"
    c2.page_number = 3
    c2.section_name = "Results"
    c2.paper_title = "Randomized Evaluation of Compound-X in Acute Cardiovascular Syndromes"
    c2.doi = "10.1056/NEJMoa1702345"
    for sr in c2.slot_results:
        sr.source_title = c2.paper_title
        sr.source_doi = c2.doi
        sr.page_number = 3
        sr.section_name = "Results"
        sr.source_location = "Results, page 3"

    c3 = verify_claim(
        claim_input="Compound-X produced a 95% survival advantage across all clinical cohorts [2]",
        source_text=(
            "Clinical evaluation showed modest survival improvements. Adverse events occurred in 5% of cohorts."
        ),
        access_tier=AccessTier.ABSTRACT_ONLY,
        citation_key="2",
    )
    c3.id = "claim-3"
    c3.source_location = "Discussion, page 4"
    c3.page_number = 4
    c3.section_name = "Discussion"
    c3.paper_title = "Multi-Center Cohort Surveillance of Cardioprotective Therapies"
    c3.doi = "10.1016/S0140-6736(18)30123-X"
    for sr in c3.slot_results:
        sr.source_title = c3.paper_title
        sr.source_doi = c3.doi
        sr.page_number = 4
        sr.section_name = "Discussion"
        sr.source_location = "Discussion, page 4"

    c4 = Claim(
        id="claim-4",
        text="Myocardial apoptosis was attenuated by 42% under sustained normoxic perfusion without supplementary intervention.",
        citation_keys=[],
        source_location="Results, page 2",
        page_number=2,
        section_name="Results",
        has_missing_citation=True,
        missing_citation_reason="Empirical assertion presented without supporting citation marker.",
        recommended_action="Provide a peer-reviewed citation supporting this assertion or qualify as an author hypothesis.",
        citation_classification="MISSING CITATION",
        citation_audit={
            "classification": "MISSING CITATION",
            "reason": "Empirical assertion presented without supporting citation marker.",
            "recommended_action": "Provide a peer-reviewed citation supporting this assertion or qualify as an author hypothesis.",
            "missing_citation": True,
            "claim_id": "claim-4",
            "claim_text": "Myocardial apoptosis was attenuated by 42% under sustained normoxic perfusion without supplementary intervention.",
            "source_location": "Results, page 2",
            "page_number": 2,
            "section_name": "Results",
        },
        verdict=Verdict(
            claim_id="claim-4",
            verdict=VerdictType.NEEDS_REVIEW,
            confidence=0.0,
            explanation="Missing citation: Empirical assertion presented without supporting citation marker. Manual human review required.",
            needs_review=True,
            rules_triggered=["RULE_MISSING_CITATION"],
            access_tier=AccessTier.INACCESSIBLE,
        ),
    )

    demo_missing_warnings = [
        {
            "warning_type": "uncited_claim",
            "reason": "Empirical claim asserted without any supporting in-text citation marker.",
            "recommended_action": "Provide a peer-reviewed citation supporting this assertion or qualify as an author hypothesis.",
            "claim_id": "claim-4",
            "claim_text": c4.text,
            "page_number": 2,
            "section_name": "Results",
            "source_location": "Results, page 2",
            "details": {"empirical_marker": "percentage/rate: 42%"},
        },
        {
            "warning_type": "missing_reference",
            "reason": "In-text citation marker '[3]' has no matching entry in the document's bibliography/reference list.",
            "recommended_action": "Add the full bibliographic reference for citation marker '[3]' to the bibliography.",
            "citation_marker": "3",
            "claim_text": "Prior histological surveys indicated consistent ventricular remodelling [3].",
            "page_number": 1,
            "section_name": "Introduction",
            "source_location": "Introduction, page 1",
            "details": {"missing_marker": "3"},
        },
        {
            "warning_type": "uncited_reference",
            "reason": "Reference exists in the bibliography but is never cited anywhere in the document text.",
            "recommended_action": "Cite this reference in the relevant section or remove it from the bibliography.",
            "citation_marker": "5",
            "details": {"key": "5", "title": "Vasodilator efficacy in pre-clinical rodent models"},
        },
        {
            "warning_type": "incomplete_mapping",
            "reason": "Reference entry in bibliography lacks required bibliographic metadata (e.g. title or author/year).",
            "recommended_action": "Complete the reference entry with full title, authors, year, and DOI.",
            "citation_marker": "6",
            "details": {"key": "6", "issue": "Missing publication year and author details"},
        },
        {
            "warning_type": "ambiguous_citation",
            "reason": "Citation marker '(Johnson, 2021)' matches multiple references in the bibliography.",
            "recommended_action": "Disambiguate citations using letter suffixes (e.g., '2021a', '2021b') or unique reference keys.",
            "citation_marker": "Johnson, 2021",
            "details": {"candidate_titles": ["Therapeutic targets in ischaemia (Johnson 2021a)", "Cardiovascular biomakers (Johnson 2021b)"]},
        },
    ]

    report = build_report(
        document_name="sample_paper.pdf",
        claims=[c1, c2, c3, c4],
        access_tier=AccessTier.FULL_TEXT,
        missing_citations=demo_missing_warnings,
        metadata={"provenance": "data/demo/sample_paper.pdf"},
    )
    rep_dict = report.to_dict()
    rep_id = "demo-report-1"
    rep_dict["id"] = rep_id
    REPORTS_STORE[rep_id] = rep_dict
    return rep_dict


# Seed demo report into persistent storage if not already present
if not REPORTS_STORE.get("demo-report-1"):
    _generate_demo_report()


@app.get("/health")
def health_check():
    """Health check endpoint for container orchestrators and load balancers."""
    return {
        "status": "ok",
        "service": "credence-api",
        "version": "1.0.0",
        "storage": "persistent",
    }


@app.get("/demo/report")
def get_demo_report():
    """Return worked demo report instantly for offline testing, with review ledger applied."""
    rep = REPORTS_STORE.get("demo-report-1") or _generate_demo_report()
    return apply_ledger_to_report(dict(rep))


@app.post("/verify")
async def verify_document(
    file: UploadFile = File(...),
    force_error: bool = False,
    demo_mode: bool = False,
    current_user: Optional[UserPublic] = Depends(get_current_user_optional),
    _rate_limit: None = Depends(rate_limit_dependency),
):
    """Upload PDF or DOCX manuscript and run complete verification pipeline.

    Security features enforced:
    - 25MB maximum upload size
    - Magic byte signature verification (%PDF / PK zip header)
    - Path traversal sanitization
    - Rate limit protection
    - Cache-first scholarly resolution via Crossref, OpenAlex, Semantic Scholar & arXiv
    - Persistent report storage
    """
    if force_error:
        raise HTTPException(
            status_code=500,
            detail="Verification pipeline forced error: Academic database retrieval gateway timed out."
        )

    if demo_mode:
        rep = REPORTS_STORE.get("demo-report-1") or _generate_demo_report()
        cached = dict(rep)
        cached["document_name"] = file.filename
        cached["id"] = f"demo-mode-{uuid.uuid4().hex[:8]}"
        cached["offline_demo_mode"] = True
        return apply_ledger_to_report(cached)

    # Secure upload validation, signature verification, and sanitization
    tmp_path, clean_filename = await validate_and_save_upload(file)

    try:
        # Ingest: Parse PDF/DOCX
        parsed_doc = parse_document(tmp_path)

        # Ingest: Map in-text citations to bibliography
        mapping = map_citations(
            body_text=parsed_doc.text,
            ref_section_text=parsed_doc.reference_section_text,
            sections=parsed_doc.sections,
        )

        # Ingest: Extract empirical claims
        claims: list[Claim] = []
        for sec in parsed_doc.sections:
            if sec.title.lower() not in ("references", "bibliography", "header / metadata"):
                sec_claims = extract_claims(sec.content, section_name=sec.title)
                for sc in sec_claims:
                    sc.section_name = sec.title
                    if parsed_doc.file_type == "docx":
                        sc.paragraph_number = sec.paragraph_start
                        sc.page_number = None
                        sc.source_location = f"{sec.title}, Paragraph {sec.paragraph_start}" if sec.paragraph_start else sec.title
                    else:
                        sc.page_number = sec.page_start
                        sc.paragraph_number = None
                        sc.source_location = f"{sec.title}, page {sec.page_start}" if sec.page_start else sec.title
                claims.extend(sec_claims)

        if not claims:
            claims = extract_claims(parsed_doc.text, section_name="Full Manuscript")

        for idx, cl in enumerate(claims, 1):
            cl.id = f"claim-{idx}"
            for sidx, slot in enumerate(cl.slots, 1):
                slot.id = f"claim-{idx}-slot-{sidx}"

        # Resolve mapped citations against scholarly databases (Crossref, OpenAlex, Semantic Scholar, etc.)
        resolver = UnifiedResolver()
        resolved_candidates: dict[str, Any] = {}
        for ref_key, ref_entry in mapping.mapped.items():
            try:
                match_res = resolver.resolve_reference(ref_entry)
                if match_res and match_res.candidate:
                    resolved_candidates[ref_key] = match_res.candidate
                else:
                    resolved_candidates[ref_key] = ref_entry
            except Exception as e:
                logger.debug(f"Reference resolution fallback for [{ref_key}]: {e}")
                resolved_candidates[ref_key] = ref_entry

        # Verify claims against citations with honest access-tier grounding
        verified_claims: list[Claim] = []
        for cl in claims:
            ref_key = cl.citation_keys[0] if cl.citation_keys else ""
            candidate = resolved_candidates.get(ref_key) or mapping.mapped.get(ref_key)

            source_text = ""
            access_tier = AccessTier.INACCESSIBLE

            if candidate:
                full_text = getattr(candidate, "raw_payload", {}).get("full_text") if hasattr(candidate, "raw_payload") else None
                abstract = getattr(candidate, "abstract", None)
                title = getattr(candidate, "title", "")
                journal = getattr(candidate, "journal", "") or ""
                year = getattr(candidate, "year", "") or ""
                doi = getattr(candidate, "doi", "") or ""

                if full_text:
                    source_text = full_text
                    access_tier = AccessTier.FULL_TEXT
                elif abstract:
                    source_text = abstract
                    access_tier = AccessTier.ABSTRACT_ONLY
                elif title:
                    source_text = f"{title}. {journal} {year}."
                    if doi:
                        source_text += f" https://doi.org/{doi}"
                    access_tier = AccessTier.METADATA_ONLY
                else:
                    access_tier = AccessTier.INACCESSIBLE
            else:
                if ref_key:
                    access_tier = AccessTier.INACCESSIBLE
                source_text = parsed_doc.text

            v_cl = verify_claim(
                cl,
                source_text=source_text,
                access_tier=access_tier,
                citation_key=ref_key,
                candidate_paper=candidate,
            )
            verified_claims.append(v_cl)

        # Run missing citation audit across mapping, claims, text, and sections
        missing_citation_warnings = audit_missing_citations(
            mapping=mapping,
            claims=verified_claims,
            body_text=parsed_doc.text,
            sections=parsed_doc.sections,
        )

        report = build_report(
            document_name=clean_filename,
            claims=verified_claims,
            access_tier=AccessTier.FULL_TEXT,
            missing_citations=missing_citation_warnings,
            metadata={
                "page_count": parsed_doc.metadata.get("page_count", 1),
                "total_citations_mapped": len(mapping.mapped),
                "missing_citations": mapping.missing,
                "uncited_references": mapping.uncited,
            },
        )

        rep_dict = report.to_dict()
        rep_id = str(uuid.uuid4())
        rep_dict["id"] = rep_id
        rep_dict = apply_ledger_to_report(rep_dict)

        # Persist report durably to SQLite / PostgreSQL
        owner_id = current_user.id if current_user else None
        report_store.save_report(rep_dict, owner_id=owner_id)

        return rep_dict

    finally:
        if tmp_path.exists():
            try:
                os.remove(tmp_path)
            except Exception:
                pass


@app.post("/verify/text")
def verify_text_claim(
    req: TextVerifyRequest,
    current_user: Optional[UserPublic] = Depends(get_current_user_optional),
):
    """Verify raw claim string against provided source text."""
    tier = AccessTier.from_str(req.access_tier or "full_text")
    v_cl = verify_claim(
        claim_input=req.claim_text,
        source_text=req.source_text,
        access_tier=tier,
        citation_key=req.citation_key or "1",
    )
    report = build_report("adhoc_claim", [v_cl], access_tier=tier)
    rep_dict = report.to_dict()
    rep_id = str(uuid.uuid4())
    rep_dict["id"] = rep_id
    owner_id = current_user.id if current_user else None
    report_store.save_report(rep_dict, owner_id=owner_id)
    return rep_dict


@app.get("/report/{report_id}")
def get_report(report_id: str):
    """Retrieve verified report by ID with SQLite review ledger overrides applied."""
    report = REPORTS_STORE.get(report_id)
    if not report and report_id in ("demo-report-1", "demo", "sample", "default"):
        report = _generate_demo_report()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return apply_ledger_to_report(dict(report))


@app.post("/report/{report_id}/review")
def review_claim(
    report_id: str,
    claim_id: str,
    action: ReviewAction,
    current_user: Optional[UserPublic] = Depends(get_current_user_optional),
):
    """Record human review action (Accept / Override / Comment) for academic triage."""
    clean_cid = str(claim_id or "").strip()
    if not clean_cid or clean_cid.lower() in ("undefined", "null", "none"):
        raise HTTPException(status_code=400, detail="Invalid claim ID provided.")

    report = None
    if report_id in ("demo-report-1", "demo", "sample", "default"):
        report = REPORTS_STORE.get("demo-report-1") or _generate_demo_report()
    else:
        report = REPORTS_STORE.get(report_id)

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    claim = next((c for c in report.get("claims", []) if c.get("id") == clean_cid), None)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim '{clean_cid}' not found in report")

    orig_v = action.original_verdict or claim.get("verdict", {}).get("original_verdict") or claim.get("verdict", {}).get("verdict")
    expl = (action.explanation if action.explanation is not None else action.comment or "").strip()

    # Server-side reviewer identity verification (Golden Rule: prevent client-side spoofing)
    verified_reviewer_id = current_user.username if current_user else (action.reviewer_id or "reviewer-1")

    try:
        review_entry = record_review(
            claim_id=clean_cid,
            action=action.action,
            override_verdict=action.override_verdict,
            explanation=expl,
            comment=expl,
            original_verdict=orig_v,
            reviewer_id=verified_reviewer_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Apply updated ledger to the report and save persistently
    updated_rep = apply_ledger_to_report(dict(report))
    REPORTS_STORE[report_id] = updated_rep

    return {"status": "ok", "claim_id": clean_cid, "review": review_entry}


@app.get("/report/{report_id}/missing-citations")
def get_report_missing_citations(report_id: str):
    """Retrieve missing citation diagnostic warnings for a verified report."""
    report = None
    if report_id in ("demo-report-1", "demo", "sample", "default"):
        report = REPORTS_STORE.get("demo-report-1") or _generate_demo_report()
    else:
        report = REPORTS_STORE.get(report_id)

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    rep_with_ledger = apply_ledger_to_report(dict(report))
    warnings = rep_with_ledger.get("missing_citations", [])
    return {
        "status": "ok",
        "report_id": report_id,
        "document_name": rep_with_ledger.get("document_name", ""),
        "total_warnings": len(warnings),
        "missing_citations": warnings,
        "summary": rep_with_ledger.get("summary", {}),
    }


class RedTeamChallengeRequest(BaseModel):
    claim_id: str
    report_id: Optional[str] = None
    claim_text: Optional[str] = ""
    citation_key: Optional[str] = None
    doi: Optional[str] = None
    paper_title: Optional[str] = None
    original_verdict: Optional[str] = "needs review"
    original_confidence: Optional[float] = 0.5
    demo_mode: Optional[bool] = False


@app.post("/api/redteam/challenge")
@app.post("/redteam/challenge")
def challenge_claim(req: RedTeamChallengeRequest):
    """Execute live 5-stage Credence Red Team adversarial investigation on a scientific claim."""
    report = run_red_team_investigation(
        claim_id=req.claim_id,
        claim_text=req.claim_text or f"Scientific assertion for claim {req.claim_id}",
        target_doi=req.doi,
        paper_title=req.paper_title,
        citation_key=req.citation_key,
        original_verdict=req.original_verdict or "needs review",
        original_confidence=req.original_confidence if req.original_confidence is not None else 0.5,
        demo_mode=req.demo_mode or False,
        report_id=req.report_id,
    )
    return {
        "status": "ok",
        "investigation": report.to_dict(),
    }


@app.get("/api/redteam/investigations/{claim_id}")
@app.get("/redteam/investigations/{claim_id}")
def get_redteam_investigations(claim_id: str):
    """Retrieve past adversarial investigations for a claim."""
    results = get_investigations_for_claim(claim_id)
    return {
        "status": "ok",
        "claim_id": claim_id,
        "investigations": results,
    }


# Mount built React frontend if present
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")

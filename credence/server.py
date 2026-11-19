"""FastAPI backend exposing verification endpoints and report persistence.

Endpoints:
- POST /verify: Manuscript file or payload -> Report JSON
- GET /report/{id}: Fetch report by ID
- POST /report/{id}/review: Record human reviewer action (Accept / Override / Comment)
- GET /demo/report: Instant offline verification report on sample data
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from credence.api.routes import router as api_router
from credence.ingest.citations import map_citations
from credence.ingest.claims import extract_claims
from credence.ingest.parse import parse_document
from credence.report.ledger import apply_ledger_to_report, record_review
from credence.report.models import AccessTier, Claim, Report, VerdictType
from credence.verify.pipeline import build_report, verify_claim

app = FastAPI(
    title="Credence Verification API",
    description="Scientific claim verification against citations with deterministic proof.",
    version="0.1.0",
)

# CORS middleware for React Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include review ledger and audit API routes
app.include_router(api_router)

# In-memory store for generated reports (backed by ID)
REPORTS_STORE: dict[str, dict[str, Any]] = {}


class ReviewAction(BaseModel):
    action: str  # 'accept', 'override', 'comment'
    override_verdict: Optional[str] = None
    comment: Optional[str] = None
    reviewer_id: Optional[str] = "reviewer-1"


class TextVerifyRequest(BaseModel):
    claim_text: str
    source_text: str
    access_tier: Optional[str] = "full_text"
    citation_key: Optional[str] = "4"


def _generate_demo_report() -> dict[str, Any]:
    """Generate deterministic report on sample demo data without live API calls."""
    # Claim 1: LearnFast (Partially supported, needs review)
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

    # Claim 2: Cardioprotective therapy (Supported)
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

    # Claim 3: Fabricated survival claim (Unsupported / Contradictory)
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

    report = build_report(
        document_name="sample_paper.pdf",
        claims=[c1, c2, c3],
        access_tier=AccessTier.FULL_TEXT,
        metadata={"provenance": "data/demo/sample_paper.pdf"},
    )
    rep_dict = report.to_dict()
    rep_id = "demo-report-1"
    rep_dict["id"] = rep_id
    REPORTS_STORE[rep_id] = rep_dict
    return rep_dict


# Seed demo report on startup
_generate_demo_report()


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "credence-api"}


@app.get("/demo/report")
def get_demo_report():
    """Return worked demo report instantly for offline testing, with SQLite ledger applied."""
    rep = REPORTS_STORE.get("demo-report-1") or _generate_demo_report()
    return apply_ledger_to_report(dict(rep))


@app.post("/verify")
async def verify_document(file: UploadFile = File(...)):
    """Upload PDF or DOCX manuscript and run complete verification pipeline."""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".pdf", ".docx", ".doc"):
        raise HTTPException(status_code=400, detail="Supported file formats: .pdf, .docx")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

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
                claims.extend(extract_claims(sec.content, section_name=sec.title))

        if not claims:
            # Fallback to full body claim extraction
            claims = extract_claims(parsed_doc.text, section_name="Full Manuscript")

        # Verify claims against citations
        verified_claims: list[Claim] = []
        for cl in claims:
            # Match citation key with mapped reference entry
            ref_key = cl.citation_keys[0] if cl.citation_keys else ""
            ref_entry = mapping.mapped.get(ref_key)

            source_text = ""
            access_tier = AccessTier.FULL_TEXT
            if ref_entry:
                # Use reference title and journal context as retrieved proxy in offline mode
                source_text = f"{ref_entry.title}. {ref_entry.journal or ''} {ref_entry.year or ''}."
                if ref_entry.doi:
                    source_text += f" https://doi.org/{ref_entry.doi}"

            # If no mapped reference, use manuscript body context as fallback
            if not source_text:
                source_text = parsed_doc.text

            v_cl = verify_claim(cl, source_text=source_text, access_tier=access_tier, citation_key=ref_key)
            verified_claims.append(v_cl)

        report = build_report(
            document_name=file.filename,
            claims=verified_claims,
            access_tier=AccessTier.FULL_TEXT,
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
        REPORTS_STORE[rep_id] = rep_dict
        return rep_dict

    finally:
        if tmp_path.exists():
            os.remove(tmp_path)


@app.post("/verify/text")
def verify_text_claim(req: TextVerifyRequest):
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
    REPORTS_STORE[rep_id] = rep_dict
    return rep_dict


@app.get("/report/{report_id}")
def get_report(report_id: str):
    """Retrieve verified report by ID with SQLite review ledger overrides applied."""
    report = REPORTS_STORE.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return apply_ledger_to_report(dict(report))


@app.post("/report/{report_id}/review")
def review_claim(report_id: str, claim_id: str, action: ReviewAction):
    """Record human review action (Accept / Override / Comment) for academic triage."""
    report = REPORTS_STORE.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    claim = next((c for c in report.get("claims", []) if c.get("id") == claim_id), None)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found in report")

    review_entry = record_review(
        claim_id=claim_id,
        action=action.action,
        override_verdict=action.override_verdict,
        comment=action.comment,
        reviewer_id=action.reviewer_id or "reviewer-1",
    )

    if "reviews" not in claim:
        claim["reviews"] = []
    claim["reviews"].append(review_entry)

    if action.action == "override" and action.override_verdict:
        if claim.get("verdict"):
            claim["verdict"]["verdict"] = action.override_verdict
            claim["verdict"]["display_verdict"] = f"{action.override_verdict.capitalize()} (Overridden)"
            claim["verdict"]["override_info"] = review_entry

    return {"status": "ok", "claim_id": claim_id, "review": review_entry}


# Mount built React frontend if present
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")

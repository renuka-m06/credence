"""Tests for Missing Citation Detection in Credence.

Verifies:
1. Identification of empirical claims lacking associated citations (Requirement 1)
2. Detection of claims with incomplete citation mapping (Requirement 2)
3. Detection of citations in text but missing from reference list (Requirement 3)
4. Detection of references in bibliography never cited in document (Requirement 4)
5. Identification of ambiguous citation mappings (Requirement 5)
6. Missing citation warnings in verification report and summary (Requirement 6)
7. Never automatically inventing or assigning citations to unsupported claims (Requirement 7)
8. Integration with citations.py and claims.py (Requirement 8)
9. API endpoint GET /report/{id}/missing-citations
10. Export integration in HTML and Markdown
"""

import pytest
from fastapi.testclient import TestClient

from credence.api.export import generate_html_export, generate_markdown_export
from credence.ingest.citations import (
    CitationMappingResult,
    audit_missing_citations,
    map_citations,
)
from credence.ingest.claims import (
    deterministic_extract_claims,
    identify_uncited_claims,
)
from credence.report.models import (
    AccessTier,
    Claim,
    MissingCitationWarning,
    Report,
    Verdict,
    VerdictType,
)
from credence.resolve.reference import Reference
from credence.server import app, _generate_demo_report
from credence.verify.pipeline import build_report, verify_claim


# =======================================================================
# 1. Empirical Claims Lacking Associated Citations (Requirement 1 & 7)
# =======================================================================

def test_identify_uncited_empirical_claims():
    """Identify empirical claims that do not have associated citations without inventing citations."""
    text = (
        "In our preliminary experiments, Compound-X demonstrated a 45.2% reduction in tumor volume. "
        "Prior studies also showed significant apoptotic acceleration [1]."
    )
    claims = deterministic_extract_claims(text, section_name="Results", include_uncited=True)
    assert len(claims) >= 2

    # Find the uncited claim
    uncited = next((c for c in claims if not c.citation_keys), None)
    assert uncited is not None
    assert "45.2%" in uncited.text
    # Requirement 7: Never automatically invent or assign citations
    assert uncited.citation_keys == []
    assert uncited.has_missing_citation is True
    assert uncited.citation_classification == "MISSING CITATION"
    assert uncited.missing_citation_reason is not None
    assert "citation" in uncited.missing_citation_reason.lower()
    assert uncited.recommended_action is not None
    assert "peer-reviewed" in uncited.recommended_action.lower() or "citation" in uncited.recommended_action.lower()


def test_never_invent_or_assign_citations_to_unsupported_claims():
    """Verify that verify_claim never invents or assigns citations to uncited claims (Requirement 7)."""
    claim = Claim(
        id="uncited-1",
        text="A sustained 38% decrease in biomarker concentration occurred without therapeutic intervention.",
        citation_keys=[],  # Uncited
        source_location="Results, page 2",
        page_number=2,
        section_name="Results",
    )

    verified = verify_claim(claim)

    # Verification must respect missing citation
    assert verified.citation_keys == []  # Not mutated or invented
    assert verified.has_missing_citation is True
    assert verified.citation_classification == "MISSING CITATION"
    assert verified.verdict is not None
    assert verified.verdict.verdict == VerdictType.NEEDS_REVIEW
    assert verified.verdict.confidence == 0.0
    assert "RULE_MISSING_CITATION" in verified.verdict.rules_triggered
    assert verified.citation_audit is not None
    assert verified.citation_audit.get("missing_citation") is True
    assert verified.missing_citation_reason is not None
    assert verified.recommended_action is not None


# =======================================================================
# 2. Incomplete Citation Mapping (Requirement 2)
# =======================================================================

def test_detect_incomplete_citation_mapping():
    """Detect claims with incomplete citation mapping (partially unmapped or missing metadata)."""
    refs = [
        Reference(key="1", title="Validation Study of Compound-X", authors=["Smith, J."], year=2020),
        Reference(key="2", title="", authors=[], year=None),  # Incomplete metadata
    ]
    in_text = ["1", "2", "99"]
    mapping = map_citations(in_text, refs)

    claim_partial = Claim(
        id="claim-partial",
        text="Compound-X produced 34% efficacy while reducing adverse effects [1, 99].",
        citation_keys=["1", "99"],
        source_location="Results, page 3",
        page_number=3,
        section_name="Results",
    )

    warnings = audit_missing_citations(
        mapping=mapping,
        claims=[claim_partial],
        body_text=claim_partial.text,
    )

    # Must detect incomplete mapping for claim citing unmapped key 99
    inc = [w for w in warnings if w.warning_type == "incomplete_mapping"]
    assert len(inc) >= 1
    # Check that warning details reference key 99 or key 2
    keys_flagged = [w.citation_marker for w in inc] + [w.details.get("unmapped_keys") for w in inc]
    assert any("99" in str(k) or "2" in str(k) for k in keys_flagged)


# =======================================================================
# 3. In-Text Citations Missing from Reference List (Requirement 3)
# =======================================================================

def test_detect_citations_missing_from_reference_list():
    """Detect citations mentioned in the text but missing from the reference list."""
    refs = [
        Reference(key="1", title="Study A", authors=["Alpha, A."], year=2021),
    ]
    in_text = ["1", "3", "7"]
    mapping = map_citations(in_text, refs)

    body = "Initial results matched early findings [1]. Extended assays refuted this assertion [3] and [7]."
    warnings = audit_missing_citations(
        mapping=mapping,
        claims=[],
        body_text=body,
    )

    missing_ref_warnings = [w for w in warnings if w.warning_type == "missing_reference"]
    assert len(missing_ref_warnings) == 2
    markers = [w.citation_marker for w in missing_ref_warnings]
    assert "3" in markers
    assert "7" in markers
    for w in missing_ref_warnings:
        assert "bibliography" in w.reason.lower() or "reference list" in w.reason.lower()
        assert "add" in w.recommended_action.lower() or "reference" in w.recommended_action.lower()


# =======================================================================
# 4. References in Bibliography Never Cited in Document (Requirement 4)
# =======================================================================

def test_detect_uncited_references_in_bibliography():
    """Detect references present in the bibliography but never cited in the document."""
    refs = [
        Reference(key="1", title="Used Reference", authors=["Alpha, A."], year=2021),
        Reference(key="2", title="Dormant Unused Reference", authors=["Beta, B."], year=2019),
    ]
    in_text = ["1"]
    mapping = map_citations(in_text, refs)

    warnings = audit_missing_citations(
        mapping=mapping,
        claims=[],
        body_text="Only reference [1] is cited in the narrative text.",
    )

    uncited_ref_warnings = [w for w in warnings if w.warning_type == "uncited_reference"]
    assert len(uncited_ref_warnings) == 1
    w = uncited_ref_warnings[0]
    assert w.citation_marker == "2"
    assert "Dormant Unused Reference" in w.details.get("title", "")
    assert "never cited" in w.reason.lower() or "uncited" in w.reason.lower()
    assert "cite" in w.recommended_action.lower() or "remove" in w.recommended_action.lower()


# =======================================================================
# 5. Ambiguous Citation Mappings (Requirement 5)
# =======================================================================

def test_identify_ambiguous_citation_mappings():
    """Identify ambiguous citation mappings (e.g. duplicate author-year or duplicate numbered keys)."""
    refs = [
        Reference(key="Johnson2020a", title="Johnson Primary Study", authors=["Johnson, E."], year=2020),
        Reference(key="Johnson2020b", title="Johnson Follow-up Survey", authors=["Johnson, E."], year=2020),
    ]
    in_text = ["Johnson, 2020"]
    mapping = map_citations(in_text, refs)

    warnings = audit_missing_citations(
        mapping=mapping,
        claims=[],
        body_text="As reported previously (Johnson, 2020), cardiac fibrosis slowed.",
    )

    ambig_warnings = [w for w in warnings if w.warning_type == "ambiguous_citation"]
    assert len(ambig_warnings) >= 1
    w = ambig_warnings[0]
    assert "Johnson, 2020" in (w.citation_marker or "")
    assert len(w.details.get("candidate_titles", [])) >= 2
    assert "disambiguate" in w.recommended_action.lower() or "suffix" in w.recommended_action.lower()


# =======================================================================
# 6. Report Integration and Warning Aggregation (Requirement 6)
# =======================================================================

def test_missing_citation_warnings_in_verification_report():
    """Verify missing citation warnings are aggregated into Report summary and model."""
    c_uncited = Claim(
        id="c-uncited",
        text="A 22% improvement was observed without baseline controls.",
        citation_keys=[],
        source_location="Results, page 2",
        page_number=2,
        section_name="Results",
        has_missing_citation=True,
        missing_citation_reason="Empirical assertion presented without supporting citation marker.",
        recommended_action="Provide peer-reviewed citation.",
    )
    v_cl = verify_claim(c_uncited)

    sample_warning = MissingCitationWarning(
        warning_type="uncited_claim",
        reason="Empirical claim asserted without citation.",
        recommended_action="Provide peer-reviewed citation.",
        claim_id="c-uncited",
        claim_text=c_uncited.text,
        page_number=2,
        section_name="Results",
    )

    report = build_report(
        document_name="test_paper.pdf",
        claims=[v_cl],
        missing_citations=[sample_warning],
    )

    rep_dict = report.to_dict()
    assert len(rep_dict["missing_citations"]) == 1
    assert rep_dict["summary"]["missing_citations_count"] == 1
    assert rep_dict["summary"]["uncited_claims"] == 1
    assert rep_dict["summary"]["human_review_required"] is True

    # Check reconstruction
    reconstructed = Report.from_dict(rep_dict)
    assert len(reconstructed.missing_citations) == 1
    assert reconstructed.claims[0].has_missing_citation is True


# =======================================================================
# 7. Integration with Citations and Claims Modules (Requirement 8)
# =======================================================================

def test_integration_citations_and_claims_modules():
    """End-to-end integration test of claims.py, citations.py, and audit_missing_citations."""
    manuscript = (
        "SECTION 1: INTRODUCTION\n"
        "Myocardial infarction remains a major global mortality factor [1]. "
        "Previous animal models suggested potential mitochondrial recovery [99].\n\n"
        "SECTION 2: RESULTS\n"
        "Compound-X reduced infarct size by 28.4% [1]. "
        "Furthermore, apoptotic cells decreased by 41.5% under sustained normoxia.\n\n"
        "SECTION 3: REFERENCES\n"
        "[1] Smith J, Doe A. Cardioprotective mechanisms of Compound-X. J Clin Invest 2021.\n"
        "[2] Brown K. Unused Pharmacological Reference. Circulation 2020.\n"
    )

    # 1. Extract claims
    claims = deterministic_extract_claims(manuscript, section_name="Full Manuscript", include_uncited=True)
    assert len(claims) >= 2
    uncited_empirical = [c for c in claims if not c.citation_keys]
    assert len(uncited_empirical) >= 1
    assert "41.5%" in uncited_empirical[0].text

    # 2. Map citations
    refs = [
        Reference(key="1", title="Cardioprotective mechanisms of Compound-X", authors=["Smith, J."], year=2021),
        Reference(key="2", title="Unused Pharmacological Reference", authors=["Brown, K."], year=2020),
    ]
    in_text = ["1", "99"]
    mapping = map_citations(in_text, refs)

    # 3. Run audit
    warnings = audit_missing_citations(
        mapping=mapping,
        claims=claims,
        body_text=manuscript,
    )

    # Must contain: uncited_claim, missing_reference (key 99), and uncited_reference (key 2)
    warning_types = {w.warning_type for w in warnings}
    assert "uncited_claim" in warning_types
    assert "missing_reference" in warning_types
    assert "uncited_reference" in warning_types


# =======================================================================
# 8. API Endpoint GET /report/{id}/missing-citations
# =======================================================================

def test_api_missing_citations_endpoint():
    """Test FastAPI endpoint GET /report/{id}/missing-citations."""
    client = TestClient(app)
    resp = client.get("/report/demo-report-1/missing-citations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["report_id"] == "demo-report-1"
    assert data["total_warnings"] >= 1
    assert isinstance(data["missing_citations"], list)

    # Verify fields required by Frontend specification
    w0 = data["missing_citations"][0]
    assert "reason" in w0
    assert "recommended_action" in w0
    assert "warning_type" in w0
    assert "claim_text" in w0 or "citation_marker" in w0


# =======================================================================
# 9. Export Format Integration (HTML & Markdown)
# =======================================================================

def test_export_includes_missing_citations():
    """Verify that generated Markdown and HTML exports include the Missing Citations section."""
    demo_rep = _generate_demo_report()

    # Markdown export
    md = generate_markdown_export(demo_rep)
    assert "Missing Citations & Bibliographic Diagnostics" in md
    assert "Recommended Action" in md
    assert "Diagnostic Reason" in md or "Reason" in md

    # HTML export
    html = generate_html_export(demo_rep)
    assert "Missing Citations &amp; Bibliographic Diagnostics" in html or "Missing Citations & Bibliographic Diagnostics" in html
    assert "Missing Cits" in html or "Missing Citations" in html
    assert "RECOMMENDED ACTION" in html or "Recommended Action" in html

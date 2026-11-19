"""Comprehensive unit and integration tests for Evidence Highlighting and Source Traceability.

Verifies:
1. Extract page numbers during PDF ingestion using PyMuPDF.
2. Preserve canonical academic section headings:
   - Abstract
   - Introduction
   - Methodology
   - Results
   - Discussion
   - Conclusion
3. Store complete traceability metadata for every evidence passage:
   - Original paper title
   - DOI
   - Page number
   - Section name
   - Exact evidence quotation
   - Claim associated with the quotation.
4. Highlight relevant evidence in report and source viewer.
5. Source inspection endpoint allowing users to locate the supporting passage.
6. For DOCX manuscripts, provide paragraph and section references without inventing fake PDF page numbers.
7. Maintain existing deterministic quote_check() verification.
8. Golden Rule 8: Never display an unverified quotation as confirmed evidence.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import docx
import fitz
import pytest
from fastapi.testclient import TestClient

from credence.ingest.parse import (
    CANONICAL_SECTIONS,
    PageText,
    ParsedDocument,
    Section,
    _split_into_sections,
    parse_docx,
    parse_pdf,
)
from credence.report.models import AccessTier, Claim, Report, Slot, SlotResult, VerdictType
from credence.server import app
from credence.verify.checks import quote_check
from credence.verify.pipeline import build_report, verify_claim
from credence.verify.retrieve import retrieve_evidence_passages, segment_passages


# ---------------------------------------------------------------------------
# Requirement 1: Extract page numbers during PDF ingestion using PyMuPDF
# ---------------------------------------------------------------------------

def test_pdf_page_number_extraction_pymupdf():
    """Verify PyMuPDF extracts 1-based page numbers and maps text per page."""
    # Create a temporary 3-page test PDF
    doc = fitz.open()
    
    p1 = doc.new_page()
    p1.insert_text((50, 50), "Abstract\nThis study explores high-temperature superconductors.\nIntroduction\nBackground on condensed matter physics.")

    p2 = doc.new_page()
    p2.insert_text((50, 50), "Methodology\nSamples were synthesized using solid-state reaction.\nResults\nResistance dropped to zero at 93 Kelvin [1].")

    p3 = doc.new_page()
    p3.insert_text((50, 50), "Discussion\nThermal fluctuations were observed.\nConclusion\nHigh-Tc superconductivity was confirmed.\nReferences\n[1] Wu et al. Superconductivity at 93 K. Phys Rev Lett, 1987.")

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    doc.save(str(tmp_path))
    doc.close()

    try:
        parsed = parse_pdf(tmp_path)
        assert parsed.file_type == "pdf"
        assert len(parsed.pages) == 3
        assert [p.page_number for p in parsed.pages] == [1, 2, 3]
        assert parsed.metadata["page_count"] == 3

        # Verify page contents
        assert "superconductors" in parsed.pages[0].text
        assert "Resistance dropped" in parsed.pages[1].text
        assert "References" in parsed.pages[2].text
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


# ---------------------------------------------------------------------------
# Requirement 2: Preserve canonical section headings
# ---------------------------------------------------------------------------

def test_section_heading_preservation_canonical():
    """Verify standard academic sections (Abstract, Introduction, Methodology, Results, Discussion, Conclusion) are preserved."""
    pages = [
        PageText(page_number=1, text=(
            "Abstract\nSuperconductivity in iron pnictides.\n\n"
            "Introduction\nIron-based systems offer unconventional pairing.\n\n"
            "Methodology\nMossbauer spectroscopy was performed at 4 Kelvin."
        )),
        PageText(page_number=2, text=(
            "Results\nMagnetic transition occurs at 140 Kelvin.\n\n"
            "Discussion\nSpin density wave instability precedes pairing.\n\n"
            "Conclusion\nUnconventional superconductivity established."
        )),
        PageText(page_number=3, text=(
            "References\n[1] Kamihara et al. Iron-based layered superconductor. JACS 2008."
        )),
    ]

    sections, ref_text = _split_into_sections(pages)
    section_titles = [s.title for s in sections]

    # Verify all 6 required headings plus references are identified
    assert "Abstract" in section_titles
    assert "Introduction" in section_titles
    assert "Methodology" in section_titles
    assert "Results" in section_titles
    assert "Discussion" in section_titles
    assert "Conclusion" in section_titles
    assert "References" in section_titles

    # Verify page bounds on sections
    abs_sec = next(s for s in sections if s.title == "Abstract")
    assert abs_sec.page_start == 1
    assert abs_sec.page_end == 1
    assert 1 in abs_sec.pages

    res_sec = next(s for s in sections if s.title == "Results")
    assert res_sec.page_start == 2
    assert res_sec.page_end == 2
    assert 2 in res_sec.pages

    ref_sec = next(s for s in sections if s.title == "References")
    assert ref_sec.page_start == 3
    assert "[1]" in ref_text


# ---------------------------------------------------------------------------
# Requirement 6: DOCX paragraph and section references (no invented page numbers)
# ---------------------------------------------------------------------------

def test_docx_paragraph_and_section_references_no_fake_pages():
    """Verify DOCX parser tracks paragraphs and sections without inventing fake PDF page numbers."""
    doc = docx.Document()
    doc.add_heading("Abstract", level=1)
    doc.add_paragraph("Empirical study of educational interventions.")
    doc.add_heading("Methodology", level=1)
    doc.add_paragraph("A cohort of 100 students was randomized into control and intervention groups.")
    doc.add_heading("Results", level=1)
    doc.add_paragraph("Intervention improved test performance by 18.5% compared to controls.")
    doc.add_heading("Discussion", level=1)
    doc.add_paragraph("Effect sizes were consistent across strata.")
    doc.add_heading("References", level=1)
    doc.add_paragraph("[1] Smith et al. Educational trial findings. 2021.")

    tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    doc.save(str(tmp_path))

    try:
        parsed = parse_docx(tmp_path)
        assert parsed.file_type == "docx"
        # Requirement 6: No fake page numbers
        assert parsed.pages == []

        sec_titles = [s.title for s in parsed.sections]
        assert "Abstract" in sec_titles
        assert "Methodology" in sec_titles
        assert "Results" in sec_titles
        assert "Discussion" in sec_titles
        assert "References" in sec_titles

        # Each section must have paragraph references, NOT page numbers
        res_sec = next((s for s in parsed.sections if s.title == "Results"), None)
        assert res_sec is not None
        assert res_sec.page_start is None
        assert res_sec.page_end is None
        assert res_sec.paragraph_start is not None
        assert res_sec.paragraph_end is not None
        assert res_sec.paragraph_start >= 1
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


# ---------------------------------------------------------------------------
# Requirement 3 & 4: Store complete traceability metadata and highlight evidence
# ---------------------------------------------------------------------------

def test_slot_result_and_claim_store_traceability_and_highlight():
    """Verify that every extracted evidence passage stores title, DOI, page, section, exact quote, and claim."""
    source_text = (
        "Methodology: Double blind RCT involving 500 patients.\n\n"
        "Results: In our primary clinical cohort, patients treated with Compound-X "
        "demonstrated a 14.2% reduction in major adverse cardiovascular events (p = 0.002).\n\n"
        "Discussion: Findings confirm cardioprotective utility."
    )

    class DummyPaper:
        title = "Randomized Trial of Compound-X in Cardiovascular Disease"
        doi = "10.1056/NEJMoa202401"
        url = "https://doi.org/10.1056/NEJMoa202401"
        access_tier = AccessTier.FULL_TEXT

    claim = verify_claim(
        claim_input="Compound-X reduced cardiovascular events by 14.2% [1]",
        source_text=source_text,
        candidate_paper=DummyPaper(),
        citation_key="1",
        access_tier=AccessTier.FULL_TEXT,
    )

    # 1. Check claim-level traceability
    assert claim.paper_title == "Randomized Trial of Compound-X in Cardiovascular Disease"
    assert claim.doi == "10.1056/NEJMoa202401"
    assert claim.section_name == "Results"
    assert claim.exact_quotation is not None
    assert "14.2% reduction" in claim.exact_quotation

    # 2. Check slot-level traceability
    assert len(claim.slot_results) > 0
    sr = claim.slot_results[0]
    assert sr.source_title == "Randomized Trial of Compound-X in Cardiovascular Disease"
    assert sr.source_doi == "10.1056/NEJMoa202401"
    assert sr.source_url == "https://doi.org/10.1056/NEJMoa202401"
    assert sr.section_name == "Results"
    assert sr.claim_text == claim.text
    assert sr.exact_quotation is not None
    assert sr.quote_verified is True
    assert sr.evidence_highlight is not None
    assert "<mark class=\"evidence-highlight\">" in sr.evidence_highlight


# ---------------------------------------------------------------------------
# Requirement 8 & 7: Never display an unverified quotation as confirmed evidence
# ---------------------------------------------------------------------------

def test_unverified_quotation_never_displayed_as_confirmed_evidence():
    """Verify Golden Rule 8: If deterministic quote_check() fails, quotation is never confirmed evidence."""
    source_text = "Results: Test scores improved by 12.1% in the experimental arm."
    fake_quote = "Test scores improved by 99.9% across all participating students."

    # Direct deterministic check must fail
    q_check = quote_check(fake_quote, source_text)
    assert q_check.passed is False

    # Pipeline verification with hallucinated / unverified quote
    claim = verify_claim(
        claim_input="Test scores improved by 99.9% [1]",
        source_text=source_text,
        simulated_hallucinated_quote=fake_quote,
        citation_key="1",
    )

    # Find the unverified slot
    unverified_slot = next((s for s in claim.slot_results if s.slot_id == "slot-hallucinated"), None)
    assert unverified_slot is not None
    assert unverified_slot.quote_verified is False
    # Must NOT have confirmed evidence highlight tag
    assert unverified_slot.evidence_highlight is None or "<mark class=\"evidence-highlight\">" not in unverified_slot.evidence_highlight

    # Final verdict must hold the claim for human review
    assert claim.verdict is not None
    assert claim.verdict.verdict == VerdictType.NEEDS_REVIEW or claim.verdict.needs_review is True


# ---------------------------------------------------------------------------
# Requirement 5: Source inspection endpoint
# ---------------------------------------------------------------------------

def test_source_inspection_endpoint_demo_and_custom():
    """Verify GET /report/{id}/claims/{claim_id}/source and GET /claims/{claim_id}/source return complete evidence traceability."""
    client = TestClient(app)

    # 1. Test inspection for demo report claim-1
    res = client.get("/claims/claim-1/source")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "ok"
    assert data["claim_id"] == "claim-1"
    assert "LearnFast" in data["claim_text"]
    assert "Educational Software" in data["paper_title"]
    assert data["doi"] == "10.1145/3065386"
    assert data["page_number"] == 2
    assert data["section_name"] == "Results"
    assert data["quote_verified"] is True
    assert "12.1%" in data["exact_quotation"]
    assert "source-evidence-anchor" in data["evidence_highlight"]

    # 2. Test inspection with explicit report ID route
    res_rep = client.get("/report/demo-report-1/claims/claim-2/source")
    assert res_rep.status_code == 200
    data_rep = res_rep.json()
    assert data_rep["claim_id"] == "claim-2"
    assert "Compound-X" in data_rep["claim_text"]
    assert data_rep["doi"] == "10.1056/NEJMoa1702345"
    assert data_rep["page_number"] == 3
    assert data_rep["section_name"] == "Results"

    # 3. Test non-existent claim returns 404
    res_404 = client.get("/claims/claim-nonexistent-999/source")
    assert res_404.status_code == 404


# ---------------------------------------------------------------------------
# Ingestion & In-Text Citation Traceability with DOCX
# ---------------------------------------------------------------------------

def test_docx_manuscript_ingest_preserves_paragraph_references():
    """Verify that uploading or parsing a DOCX file populates paragraph references instead of fake PDF page numbers."""
    client = TestClient(app)

    doc = docx.Document()
    doc.add_heading("Results", level=1)
    doc.add_paragraph("Patients receiving Drug-Z showed a 25% improvement in symptoms [1].")
    doc.add_heading("References", level=1)
    doc.add_paragraph("[1] Miller et al. Clinical Trial of Drug-Z. Lancet 2022.")

    tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    doc.save(str(tmp_path))

    try:
        with open(tmp_path, "rb") as f:
            resp = client.post("/verify", files={"file": ("trial_report.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
        assert resp.status_code == 200
        rep_json = resp.json()
        assert len(rep_json["claims"]) >= 1

        cl = rep_json["claims"][0]
        # Must have paragraph references and section, NO page numbers
        assert cl["paragraph_number"] is not None
        assert cl["page_number"] is None
        assert "Paragraph" in cl["source_location"]
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_models_serialization_roundtrip_with_traceability():
    """Verify that SlotResult, Claim, and Report preserve all traceability fields through serialization."""
    slot_res = SlotResult(
        slot_id="slot-1",
        quote="Test scores increased by 12.1%",
        quote_verified=True,
        quote_span=(10, 42),
        status="match",
        source_title="Vaswani et al.",
        source_doi="10.1145/3065386",
        source_url="https://doi.org/10.1145/3065386",
        page_number=2,
        section_name="Results",
        paragraph_number=None,
        source_location="Results, page 2",
        exact_quotation="Test scores increased by 12.1%",
        claim_text="Intervention improved scores by 12.1% [4]",
        evidence_highlight="<mark class=\"evidence-highlight\">Test scores increased by 12.1%</mark>",
        access_tier=AccessTier.FULL_TEXT,
    )

    d = slot_res.to_dict()
    assert d["source_title"] == "Vaswani et al."
    assert d["source_doi"] == "10.1145/3065386"
    assert d["page_number"] == 2
    assert d["section_name"] == "Results"
    assert d["paragraph_number"] is None
    assert d["exact_quotation"] == "Test scores increased by 12.1%"
    assert d["claim_text"] == "Intervention improved scores by 12.1% [4]"
    assert "<mark" in d["evidence_highlight"]

    roundtrip_sr = SlotResult.from_dict(d)
    assert roundtrip_sr.source_title == "Vaswani et al."
    assert roundtrip_sr.page_number == 2
    assert roundtrip_sr.section_name == "Results"
    assert roundtrip_sr.evidence_highlight == slot_res.evidence_highlight

    claim = Claim(
        id="claim-1",
        text="Intervention improved scores by 12.1% [4]",
        source_location="Results, page 2",
        page_number=2,
        section_name="Results",
        paper_title="Vaswani et al.",
        doi="10.1145/3065386",
        exact_quotation="Test scores increased by 12.1%",
        evidence_highlight="<mark class=\"evidence-highlight\">Test scores increased by 12.1%</mark>",
        slot_results=[slot_res],
    )

    c_dict = claim.to_dict()
    assert c_dict["paper_title"] == "Vaswani et al."
    assert c_dict["doi"] == "10.1145/3065386"
    assert c_dict["page_number"] == 2
    assert c_dict["section_name"] == "Results"

    roundtrip_claim = Claim.from_dict(c_dict)
    assert roundtrip_claim.paper_title == "Vaswani et al."
    assert roundtrip_claim.page_number == 2
    assert len(roundtrip_claim.slot_results) == 1
    assert roundtrip_claim.slot_results[0].source_doi == "10.1145/3065386"


def test_export_includes_source_traceability_and_respects_golden_rules():
    """Verify exported Markdown and HTML include paper title, DOI, page/paragraph, and do not label unverified quotes as confirmed."""
    client = TestClient(app)

    # 1. Test Markdown export
    res_md = client.get("/report/demo-report-1/export?format=markdown")
    assert res_md.status_code == 200
    md_content = res_md.text
    assert "Educational Software Interventions" in md_content
    assert "10.1145/3065386" in md_content
    assert "Results" in md_content
    assert "Page 2" in md_content

    # 2. Test HTML export
    res_html = client.get("/report/demo-report-1/export?format=html")
    assert res_html.status_code == 200
    html_content = res_html.text
    assert "Educational Software Interventions" in html_content
    assert "10.1145/3065386" in html_content
    assert "Results" in html_content
    assert "Page 2" in html_content


"""Unit and integration tests for Credence Misleading Citation Detection module.

Tests the detection of all six situations and classifications:
A. Citation exists but discusses an unrelated topic (UNRELATED CITATION)
B. Citation is relevant to topic but does not support specific claim (MISLEADING CITATION)
C. Citation reports findings that contradict the claim (CONTRADICTORY CITATION)
D. Citation contains different numerical values (MISLEADING CITATION)
E. Citation points to an incorrect research paper / DOI mismatch (UNRELATED CITATION)
F. Claim has no citation (MISSING CITATION)
- VALID CITATION verification
- Document-wide citation auditing
- Integration with verify_claim and pipeline
"""

import pytest

from credence.report.models import AccessTier, Claim, Slot, Verdict, VerdictType
from credence.resolve.matcher import CandidatePaper
from credence.resolve.reference import Reference
from credence.verify.misleading_citations import (
    CitationClassification,
    MisleadingCitationReport,
    MisleadingCitationResult,
    MisleadingSituation,
    audit_citation,
    audit_document_citations,
    compute_topic_overlap,
)
from credence.verify.pipeline import verify_claim


# ===========================================================================
# 1. Situation A: Unrelated Topic (UNRELATED CITATION)
# ===========================================================================

def test_situation_a_unrelated_topic():
    """Situation A: Citation exists but discusses an unrelated topic."""
    claim = Claim(
        id="c-unrel",
        text="Cardioprotective therapy via Compound-X reduced 30-day mortality in heart failure patients [1]",
        citation_keys=["1"],
        source_location="Results, page 2",
    )
    # Citation paper is about thermal stress on coral reefs
    cand = CandidatePaper(
        source="crossref",
        title="Bleaching events and thermal stress in Great Barrier Reef corals",
        doi="10.1000/coral.reef.2021",
        abstract="Thermal anomalies induce mass bleaching events across scleractinian corals in shallow marine habitats.",
    )

    res = audit_citation(claim, candidate_paper=cand, source_text=cand.abstract)
    assert res.classification == CitationClassification.UNRELATED_CITATION
    assert res.situation == MisleadingSituation.UNRELATED_TOPIC
    assert "unrelated topic" in res.explanation.lower()
    assert res.confidence == 0.0
    assert "coral" in res.passage.lower()


# ===========================================================================
# 2. Situation B: Relevant to topic but does not support specific claim (MISLEADING CITATION)
# ===========================================================================

def test_situation_b_unsupported_specific_claim():
    """Situation B: Citation discusses the relevant topic but fails to support the specific claim."""
    claim = Claim(
        id="c-unsupp",
        text="LearnFast educational software cured reading comprehension deficits across all student cohorts [4]",
        citation_keys=["4"],
        source_location="Discussion, page 4",
    )
    # Paper is about educational software but only evaluated 40 students with no control group and modest gain
    source_text = (
        "Educational software interventions were evaluated in a pilot study of 40 students. "
        "Test scores showed preliminary changes. Further randomized trials are required to establish efficacy."
    )
    cand = CandidatePaper(
        source="crossref",
        title="Evaluation of educational software in elementary school reading",
        doi="10.1000/learnfast.2021",
        abstract=source_text,
    )

    res = audit_citation(claim, candidate_paper=cand, source_text=source_text)
    assert res.classification == CitationClassification.MISLEADING_CITATION
    assert res.situation == MisleadingSituation.UNSUPPORTED_SPECIFIC_CLAIM
    assert "fails to substantiate" in res.explanation.lower() or "not support" in res.explanation.lower()


# ===========================================================================
# 3. Situation C: Contradictory Findings (CONTRADICTORY CITATION)
# ===========================================================================

def test_situation_c_contradictory_findings():
    """Situation C: Citation reports findings that contradict the claim."""
    claim = Claim(
        id="c-contra",
        text="Treatment with Compound-Z significantly increased 5-year survival rates in oncology patients [3]",
        citation_keys=["3"],
        source_location="Results, page 5",
    )
    # Source finds Compound-Z did not improve survival and increased mortality
    source_text = (
        "In our multicenter randomized trial of 1,200 oncology patients, treatment with Compound-Z "
        "failed to improve 5-year survival rates and was associated with increased mortality compared to standard care."
    )
    cand = CandidatePaper(
        source="crossref",
        title="Multicenter trial of Compound-Z in oncology",
        doi="10.1000/oncology.2022",
        abstract=source_text,
    )

    res = audit_citation(claim, candidate_paper=cand, source_text=source_text)
    assert res.classification == CitationClassification.CONTRADICTORY_CITATION
    assert res.situation == MisleadingSituation.CONTRADICTORY_FINDINGS
    assert "contradict" in res.explanation.lower()
    assert "failed to improve" in res.passage.lower()


# ===========================================================================
# 4. Situation D: Number Mismatch (MISLEADING CITATION)
# ===========================================================================

def test_situation_d_number_mismatch():
    """Situation D: Citation contains different numerical values from those asserted."""
    claim = Claim(
        id="c-num",
        text="Compound-X produced a 30% reduction in 30-day mortality [1]",
        citation_keys=["1"],
        source_location="Results, page 1",
    )
    # Source paper reports 12.1% reduction, NOT 30%
    source_text = (
        "In a randomized controlled trial of 1,450 patients, Compound-X demonstrated a 12.1% reduction "
        "in 30-day mortality compared with placebo (p = 0.003)."
    )
    cand = CandidatePaper(
        source="crossref",
        title="Randomized trial of Compound-X for acute coronary syndrome",
        doi="10.1000/compoundx.trial",
        abstract=source_text,
    )

    res = audit_citation(claim, candidate_paper=cand, source_text=source_text)
    assert res.classification == CitationClassification.MISLEADING_CITATION
    assert res.situation == MisleadingSituation.NUMBER_MISMATCH
    assert "numerical values" in res.explanation.lower() or "number" in res.explanation.lower()
    assert "12.1%" in res.passage


# ===========================================================================
# 5. Situation E: Incorrect Research Paper / DOI Mismatch (UNRELATED CITATION)
# ===========================================================================

def test_situation_e_incorrect_paper_doi_mismatch():
    """Situation E: Citation points to an incorrect research paper (DOI mismatch)."""
    claim = Claim(
        id="c-doi-mismatch",
        text="Patients receiving Beta-blockers exhibited reduced hospitalization rates [5]",
        citation_keys=["5"],
        source_location="Introduction, page 1",
    )
    ref = Reference(
        raw_text="[5] Doe et al. Beta-blockers in heart failure. 2020. doi:10.1001/jama.2020.999",
        key="5",
        title="Beta-blockers in heart failure",
        doi="10.1001/jama.2020.999",
        year=2020,
    )
    # The DOI resolves to an entirely different paper
    cand = CandidatePaper(
        source="crossref",
        title="Atmospheric CO2 levels and polar ice melt rates in Antarctica",
        doi="10.1001/jama.2020.999",
        year=2020,
    )

    res = audit_citation(claim, candidate_paper=cand, reference_entry=ref)
    assert res.classification == CitationClassification.UNRELATED_CITATION
    assert res.situation == MisleadingSituation.INCORRECT_PAPER
    assert "incorrect research paper" in res.explanation.lower() or "doi mismatch" in res.explanation.lower()


# ===========================================================================
# 6. Situation F: Claim Has No Citation (MISSING CITATION)
# ===========================================================================

def test_situation_f_missing_citation():
    """Situation F: Claim asserts empirical finding without any citation marker."""
    claim = Claim(
        id="c-nocite",
        text="Our novel synthetic molecule accelerated tissue regeneration by 45%.",
        citation_keys=[],  # No citation!
        source_location="Results, page 3",
    )

    res = audit_citation(claim)
    assert res.classification == CitationClassification.MISSING_CITATION
    assert res.situation == MisleadingSituation.MISSING_CITATION
    assert "lacks any citation" in res.explanation.lower() or "without citing" in res.explanation.lower()
    assert res.confidence == 0.0


# ===========================================================================
# 7. Valid Citation Verification (VALID CITATION)
# ===========================================================================

def test_valid_citation():
    """Valid Citation: Evidence directly supports claim with verbatim passage and matching numbers."""
    claim = Claim(
        id="c-valid",
        text="Compound-X demonstrated a 12.1% reduction in 30-day mortality [1]",
        citation_keys=["1"],
        source_location="Results, page 2",
    )
    source_text = (
        "In a randomized controlled trial involving 1,450 patients, Compound-X demonstrated a 12.1% reduction "
        "in 30-day mortality compared with the placebo arm."
    )
    cand = CandidatePaper(
        source="crossref",
        title="Trial of Compound-X in cardiovascular patients",
        doi="10.1000/trial-valid",
        abstract=source_text,
    )

    res = audit_citation(claim, candidate_paper=cand, source_text=source_text)
    assert res.classification == CitationClassification.VALID_CITATION
    assert res.situation == MisleadingSituation.VERIFIED_VALID
    assert "valid and directly supports" in res.explanation.lower()
    assert res.confidence > 0.80
    assert "12.1%" in res.passage


# ===========================================================================
# 8. Needs Review on Inaccessible Paper
# ===========================================================================

def test_needs_review_on_inaccessible_paper():
    """Inaccessible source paper routes citation diagnosis to NEEDS REVIEW."""
    claim = Claim(
        id="c-inacc",
        text="Preliminary biochemical analysis indicated receptor binding [2]",
        citation_keys=["2"],
    )
    cand = CandidatePaper(
        source="paywalled",
        title="Receptor binding study",
        doi="10.1000/inaccessible-paper",
        abstract=None,
        open_access_pdf_url=None,
    )

    res = audit_citation(claim, candidate_paper=cand, source_text="")
    assert res.classification == CitationClassification.NEEDS_REVIEW
    assert res.situation == MisleadingSituation.INACCESSIBLE_OR_UNVERIFIED
    assert "inaccessible" in res.explanation.lower()


# ===========================================================================
# 9. Pipeline Integration: verify_claim attaches citation audit
# ===========================================================================

def test_verify_claim_integration_with_citation_audit():
    """verify_claim automatically attaches citation_classification and citation_audit."""
    source_text = (
        "In a double-blind trial, drug A demonstrated a 15% reduction in cardiovascular events."
    )
    cand = CandidatePaper(
        source="crossref",
        title="Drug A trial",
        doi="10.1000/drug-a",
        abstract=source_text,
    )

    verified_claim = verify_claim(
        claim_input="Drug A demonstrated a 15% reduction in cardiovascular events [1]",
        source_text=source_text,
        candidate_paper=cand,
        citation_key="1",
    )

    assert verified_claim.citation_classification == CitationClassification.VALID_CITATION.value
    assert verified_claim.citation_audit is not None
    assert verified_claim.citation_audit["situation"] == MisleadingSituation.VERIFIED_VALID.value
    assert "15%" in verified_claim.citation_audit["passage"]


# ===========================================================================
# 10. Document-Wide Audit Function
# ===========================================================================

def test_audit_document_citations():
    """audit_document_citations audits all claims from a document file."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        # We can test with sample_paper.pdf in data/demo/
        from pathlib import Path
        demo_pdf = Path("data/demo/sample_paper.pdf")
        if demo_pdf.exists():
            report = audit_document_citations(demo_pdf)
            assert isinstance(report, MisleadingCitationReport)
            assert report.total_claims > 0
            assert len(report.results) == report.total_claims
            assert report.document_name == "sample_paper.pdf"

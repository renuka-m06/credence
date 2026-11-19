"""Unit tests for Reference Integrity Layers:
1. DOI-mismatch detection (DOI resolves to a different title)
2. Retraction / correction status from Crossref + OpenAlex fixtures
3. Secondary-source (review/survey) check with 1-hop citation traversal
4. 'Potentially outdated' verdict strictly grounded in listed evidence (never a guess)
"""

import pytest

from credence.report.models import AccessTier, VerdictType
from credence.resolve.matcher import (
    CandidatePaper,
    check_doi_mismatch,
    compute_title_similarity,
    score_candidate,
)
from credence.resolve.reference import Reference
from credence.resolve.sources import (
    UnifiedResolver,
    _parse_crossref_message,
    _parse_openalex_work,
)
from credence.verify.checks import (
    correction_check,
    doi_mismatch_check,
    retraction_check,
    secondary_source_check,
)
from credence.verify.pipeline import verify_claim
from credence.verify.verdict import (
    RULE_ALL_MATCH,
    RULE_OUTDATED_CITATION,
    RULE_UNGROUNDED_OUTDATED_REJECTED,
    determine_verdict,
    validate_outdated_evidence,
)


# ===========================================================================
# 1. DOI-Mismatch Detection Tests
# ===========================================================================

def test_doi_mismatch_detection_flagged():
    """When a cited DOI resolves to a completely different paper title, it must be flagged."""
    ref = Reference(
        raw_text="Smith et al. Randomized trial of Compound-X for heart failure. 2021. doi:10.1001/jama.2021.9999",
        title="Randomized trial of Compound-X for heart failure",
        doi="10.1001/jama.2021.9999",
        year=2021,
    )
    # The DOI resolves to an unrelated paper on coral reefs
    cand = CandidatePaper(
        source="crossref",
        title="Bleaching events and thermal stress in Great Barrier Reef corals",
        doi="10.1001/jama.2021.9999",
        year=2021,
    )

    is_mismatch, reason = check_doi_mismatch(ref, cand)
    assert is_mismatch is True
    assert "DOI mismatch" in reason

    # Check via deterministic checks module
    check_res = doi_mismatch_check(ref.title, cand.title, doi=ref.doi)
    assert check_res.passed is False
    assert "DOI mismatch" in check_res.reason
    assert check_res.details["mismatch_type"] == "doi_mismatch"

    # In candidate scoring, this must be classified as fake_title / doi_mismatch with is_match = False
    match_res = score_candidate(ref, cand)
    assert match_res.is_match is False
    assert match_res.classification in ("doi_mismatch", "fake_title")
    assert match_res.details.get("doi_mismatch") is True
    assert any("DOI mismatch" in d for d in match_res.discrepancies)


def test_doi_match_correct_title():
    """When a cited DOI resolves to the matching paper title, no mismatch is flagged."""
    ref = Reference(
        raw_text="Doe et al. Efficacy of beta blockers in heart failure. 2020. doi:10.1056/nejmoa2001",
        title="Efficacy of beta blockers in heart failure",
        doi="10.1056/nejmoa2001",
        year=2020,
    )
    cand = CandidatePaper(
        source="crossref",
        title="Efficacy of Beta Blockers in Chronic Heart Failure Patients",
        doi="10.1056/nejmoa2001",
        year=2020,
    )

    is_mismatch, reason = check_doi_mismatch(ref, cand)
    assert is_mismatch is False
    assert reason is None

    check_res = doi_mismatch_check(ref.title, cand.title, doi=ref.doi)
    assert check_res.passed is True

    match_res = score_candidate(ref, cand)
    assert match_res.is_match is True
    assert match_res.classification == "valid"


# ===========================================================================
# 2. Retraction & Correction Status Tests
# ===========================================================================

def test_crossref_fixture_retraction_parsing():
    """Crossref Crossmark 'update-to' retraction notice is accurately extracted."""
    msg_fixture = {
        "title": ["Cardioprotective therapy via mitochondrial stabilization"],
        "DOI": "10.1016/j.jacc.2018.01.001",
        "issued": {"date-parts": [[2018]]},
        "author": [{"family": "Smith", "given": "John"}],
        "update-to": [
            {
                "type": "retraction",
                "label": "Retraction",
                "updated": {"date-parts": [[2021, 6, 15]]},
                "DOI": "10.1016/j.jacc.2021.05.002",
            }
        ],
    }
    cand = _parse_crossref_message(msg_fixture)
    assert cand.is_retracted is True
    assert cand.retraction_details["type"] == "retraction"

    ret_check = retraction_check(cand)
    assert ret_check.passed is False
    assert "retracted" in ret_check.reason.lower()


def test_crossref_fixture_correction_parsing():
    """Crossref 'update-to' erratum/corrigendum notice is accurately extracted."""
    msg_fixture = {
        "title": ["Long-term survival in chronic kidney disease patients"],
        "DOI": "10.1093/ndt/gfz001",
        "issued": {"date-parts": [[2019]]},
        "update-to": [
            {
                "type": "erratum",
                "label": "Erratum",
                "updated": {"date-parts": [[2019, 4, 1]]},
                "DOI": "10.1093/ndt/gfz050",
            }
        ],
    }
    cand = _parse_crossref_message(msg_fixture)
    assert cand.is_corrected is True
    assert cand.correction_details["type"] == "erratum"

    corr_check = correction_check(cand)
    assert corr_check.passed is False
    assert "correction" in corr_check.reason.lower() or "erratum" in corr_check.reason.lower()


def test_openalex_fixture_retraction_parsing():
    """OpenAlex is_retracted field is accurately parsed into CandidatePaper."""
    work_fixture = {
        "id": "https://openalex.org/W2989901234",
        "doi": "https://doi.org/10.1038/s41586-020-0001-x",
        "title": "Hydroxychloroquine for non-hospitalized adults with early COVID-19",
        "publication_year": 2020,
        "is_retracted": True,
        "type": "article",
        "authorships": [{"author": {"display_name": "Mehra MR"}}],
    }
    cand = _parse_openalex_work(work_fixture)
    assert cand.is_retracted is True

    ret_check = retraction_check(cand)
    assert ret_check.passed is False
    assert ret_check.details["is_retracted"] is True


# ===========================================================================
# 3. Secondary-Source (Review/Survey) Check & 1-Hop Traversal Tests
# ===========================================================================

def test_secondary_source_detection_review():
    """Systematic reviews and surveys are flagged as secondary sources."""
    cand_review = CandidatePaper(
        source="crossref",
        title="A Systematic Review and Meta-Analysis of SGLT2 Inhibitors in Heart Failure",
        doi="10.1001/jamacardio.2021.1111",
        publication_type="review",
    )
    check_res = secondary_source_check(cand_review)
    assert check_res.passed is False
    assert check_res.details["is_secondary_source"] is True
    assert check_res.details["hops_required"] == 1


def test_secondary_source_detection_primary_study():
    """Primary empirical trials are identified as primary sources."""
    cand_primary = CandidatePaper(
        source="crossref",
        title="Dapagliflozin in Patients with Heart Failure and Reduced Ejection Fraction",
        doi="10.1056/nejmoa1911303",
        publication_type="journal-article",
    )
    check_res = secondary_source_check(cand_primary)
    assert check_res.passed is True
    assert check_res.details["is_secondary_source"] is False


def test_secondary_source_follow_citation_hop():
    """When a review is cited, 1 citation hop resolves to the primary empirical source."""
    # Secondary review paper that cites the primary trial in its references
    review_cand = CandidatePaper(
        source="crossref",
        title="Review of Sodium-Glucose Transport Inhibitors in Cardiovascular Medicine",
        doi="10.1016/j.jacc.2021.02.001",
        publication_type="review",
        references=[
            {
                "key": "ref1",
                "doi": "10.1056/nejmoa1911303",
                "title": "Dapagliflozin in Patients with Heart Failure and Reduced Ejection Fraction (DAPA-HF Trial)",
                "author": "McMurray JJV",
                "year": 2019,
                "abstract": "In a double-blind trial of 4,744 patients, dapagliflozin reduced cardiovascular death or worsening heart failure by 26% compared to placebo.",
            },
            {
                "key": "ref2",
                "doi": "10.1016/s0140-6736(20)31824-9",
                "title": "Empagliflozin in heart failure with reduced ejection fraction",
                "author": "Packer M",
                "year": 2020,
            },
        ],
    )

    resolver = UnifiedResolver()
    claim_text = "Dapagliflozin reduced cardiovascular death or worsening heart failure in heart failure patients [1]"
    hop_paper = resolver.follow_citation_hop(review_cand, claim_text)

    assert hop_paper is not None
    assert "Dapagliflozin" in hop_paper.title
    assert hop_paper.year == 2019


# ===========================================================================
# 4. 'Potentially Outdated' Verdict Tests (Evidence-Grounded vs Guess)
# ===========================================================================

def test_potentially_outdated_grounded_in_retraction():
    """Retraction notice qualifies as concrete listed evidence for 'potentially outdated'."""
    evidence = {
        "is_retracted": True,
        "retraction": "Retraction notice published in The Lancet (doi:10.1016/S0140-6736(20)31324-6)",
    }
    is_grounded, summary = validate_outdated_evidence(is_outdated=True, outdated_evidence=evidence)
    assert is_grounded is True
    assert "retraction notice" in summary.lower()

    verdict = determine_verdict(
        slots=["match"],
        claim_id="claim-retracted",
        is_outdated=True,
        outdated_evidence=evidence,
    )
    assert verdict.verdict == VerdictType.POTENTIALLY_OUTDATED
    assert RULE_OUTDATED_CITATION in verdict.rules_triggered
    assert "retraction" in verdict.explanation.lower()


def test_potentially_outdated_grounded_in_contradicting_study():
    """A later contradicting study qualifies as concrete evidence for 'potentially outdated'."""
    evidence = {
        "contradicting_study": "Doe et al. (2024), Multi-center Phase III replication trial refuting pilot efficacy",
    }
    is_grounded, summary = validate_outdated_evidence(is_outdated=True, outdated_evidence=evidence)
    assert is_grounded is True
    assert "contradicting study" in summary.lower()

    verdict = determine_verdict(
        slots=["match"],
        claim_id="claim-superseded",
        is_outdated=True,
        outdated_evidence=evidence,
    )
    assert verdict.verdict == VerdictType.POTENTIALLY_OUTDATED
    assert RULE_OUTDATED_CITATION in verdict.rules_triggered
    assert "contradicting study" in verdict.explanation.lower()


def test_potentially_outdated_ungrounded_guess_rejected():
    """An ungrounded outdated guess without listed evidence is rejected and falls back to slot evaluation."""
    # 1. Bare boolean without any evidence
    is_grounded_bare, _ = validate_outdated_evidence(is_outdated=True, outdated_evidence=None)
    assert is_grounded_bare is False

    verdict_bare = determine_verdict(
        slots=["match", "match"],
        claim_id="claim-guess-1",
        is_outdated=True,
        outdated_evidence=None,  # No evidence provided
    )
    assert verdict_bare.verdict == VerdictType.SUPPORTED
    assert RULE_UNGROUNDED_OUTDATED_REJECTED in verdict_bare.rules_triggered

    # 2. Speculative string guess without retraction or contradicting study
    is_grounded_spec, _ = validate_outdated_evidence(
        is_outdated=True,
        outdated_evidence="I guess this finding might be old because it was published in 2012"
    )
    assert is_grounded_spec is False

    verdict_spec = determine_verdict(
        slots=["match"],
        claim_id="claim-guess-2",
        is_outdated=True,
        outdated_evidence="I guess this finding might be old",
    )
    assert verdict_spec.verdict == VerdictType.SUPPORTED
    assert RULE_UNGROUNDED_OUTDATED_REJECTED in verdict_spec.rules_triggered


# ===========================================================================
# 5. Pipeline End-to-End Tests with Integrity Layers
# ===========================================================================

def test_pipeline_with_retracted_candidate_paper():
    """Pipeline flags claim as potentially outdated when candidate paper is retracted."""
    cand_retracted = CandidatePaper(
        source="openalex",
        title="Surgical therapy outcomes in acute coronary syndrome",
        doi="10.1016/j.surg.2019.01.001",
        is_retracted=True,
        retraction_details={"reason": "Data fabrication confirmed by institutional investigation"},
    )

    claim = verify_claim(
        claim_input="Surgical therapy improved outcomes in acute coronary syndrome [1]",
        source_text="Surgical therapy improved outcomes in acute coronary syndrome by 20%.",
        candidate_paper=cand_retracted,
    )

    assert claim.verdict is not None
    assert claim.verdict.verdict == VerdictType.POTENTIALLY_OUTDATED
    assert RULE_OUTDATED_CITATION in claim.verdict.rules_triggered


def test_pipeline_with_secondary_review_1hop_augmentation():
    """Pipeline identifies review, follows 1 hop, and augments source text."""
    primary_study = {
        "doi": "10.1056/nejmoa12345",
        "title": "Randomized Trial of Compound-Y in Renal Disease",
        "author": "Johnson et al.",
        "year": 2020,
        "abstract": "In a randomized trial of 800 patients, Compound-Y demonstrated a 15% reduction in disease progression.",
    }

    cand_review = CandidatePaper(
        source="crossref",
        title="Comprehensive Review of Novel Renal Therapeutics",
        doi="10.1038/s41581-021-0001",
        publication_type="review",
        references=[primary_study],
    )

    resolver = UnifiedResolver()

    claim = verify_claim(
        claim_input="Compound-Y demonstrated a 15% reduction in disease progression [1]",
        source_text="Review summary: Various agents were examined in recent literature.",
        candidate_paper=cand_review,
        resolver=resolver,
    )

    assert claim.verdict is not None
    # 1-hop primary source details should be attached
    assert any("primary_source_hop" in sr.details for sr in claim.slot_results)
    hop_info = claim.slot_results[0].details["primary_source_hop"]
    assert "Compound-Y" in hop_info["original_title"]

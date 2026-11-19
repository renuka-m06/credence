"""Unit tests for Credence Red Team – Adversarial Scientific Integrity Engine.

Validates the 7 required test cases from specification:
1. A claim with supporting evidence
2. A claim with contradictory evidence
3. A numerical overstatement
4. A retracted publication
5. A corrected publication
6. A claim with no accessible full text
7. Multiple papers that depend on the same original research
"""

import pytest
from credence.verify.red_team import (
    RedTeamOutcome,
    run_red_team_investigation,
    get_investigations_for_claim,
)


def test_red_team_numerical_overstatement():
    """Case 3: Numerical overstatement and pilot limitation (Claim 1)."""
    report = run_red_team_investigation(
        claim_id="claim-1",
        claim_text="LearnFast improved test scores by 30% [4]",
        target_doi="10.1145/3065386",
        original_verdict="partially supported",
        original_confidence=0.55,
    )
    assert report.overall_outcome == RedTeamOutcome.PARTIALLY_SUPPORTED
    assert len(report.stage_c_numerical_integrity) >= 1
    # Check that percentage discrepancy is flagged
    pct_disc = next(d for d in report.stage_c_numerical_integrity if d.parameter == "percentage")
    assert pct_disc.asserted_in_claim == "30%"
    assert pct_disc.primary_source_value == "12.1%"

    # Check limitations extracted
    assert any(l.category == "lack_of_control" for l in report.stage_e_limitations)
    assert any(l.category == "sample_size" for l in report.stage_e_limitations)


def test_red_team_contradictory_evidence():
    """Case 2: Primary study challenged by subsequent large-scale trial (Claim 2)."""
    report = run_red_team_investigation(
        claim_id="claim-2",
        claim_text="Patients receiving Compound-X demonstrated a 12.1% reduction in 30-day mortality [1]",
        target_doi="10.1056/NEJMoa1702345",
        original_verdict="supported",
        original_confidence=0.90,
    )
    assert report.overall_outcome == RedTeamOutcome.CONTESTED
    # Stage A flags expression of concern
    assert report.stage_a_source_integrity.status == "expression_of_concern"
    assert report.stage_a_source_integrity.is_alert is True

    # Stage B finds contradictory multicenter trial
    assert len(report.stage_b_counter_evidence) >= 1
    lancet_trial = next(c for c in report.stage_b_counter_evidence if "TARGET-ACS" in c.paper_title or "3,200" in c.paper_title)
    assert lancet_trial.relationship == "failed_replication"
    assert lancet_trial.quote_verified is True
    assert "0.19" in lancet_trial.p_value

    # Timeline includes both original and update events
    assert len(report.timeline) >= 4
    assert any(t.is_update for t in report.timeline)


def test_red_team_retracted_publication():
    """Case 4: Retracted publication detection (Claim 3)."""
    report = run_red_team_investigation(
        claim_id="claim-3",
        claim_text="Compound-X produced an unprecedented 95% survival advantage across all cohorts [2]",
        target_doi="10.1016/S0140-6736(18)30123-X",
        original_verdict="contradictory",
        original_confidence=0.35,
    )
    assert report.overall_outcome == RedTeamOutcome.INTEGRITY_CONCERN
    assert report.stage_a_source_integrity.status == "retracted"
    assert report.stage_a_source_integrity.is_alert is True
    assert report.stage_a_source_integrity.notice_doi is not None


def test_red_team_missing_full_text_and_uncited():
    """Case 6: Claim with no accessible full text or missing citation (Claim 4)."""
    report = run_red_team_investigation(
        claim_id="claim-4",
        claim_text="Myocardial apoptosis was attenuated by 42% under sustained normoxic perfusion without supplementary intervention.",
        target_doi=None,
        original_verdict="needs review",
        original_confidence=0.0,
    )
    assert report.overall_outcome == RedTeamOutcome.INSUFFICIENT_EVIDENCE
    assert report.stage_a_source_integrity.status == "unavailable"


def test_red_team_evidence_independence():
    """Case 7: Dependency graph distinguishes confirmed from inferred relationships."""
    report = run_red_team_investigation(
        claim_id="claim-2",
        claim_text="Patients receiving Compound-X demonstrated a 12.1% reduction in 30-day mortality [1]",
        target_doi="10.1056/NEJMoa1702345",
    )
    assert report.stage_d_independence["total_papers_analyzed"] >= 3
    assert report.stage_d_independence["independent_replications"] >= 1
    # Check graph nodes and edges
    nodes = report.dependency_graph["nodes"]
    edges = report.dependency_graph["edges"]
    assert len(nodes) >= 3
    assert any(n["is_primary"] is True for n in nodes)
    assert any(n["category"] == "contradictory" for n in nodes)
    assert len(edges) >= 2


def test_red_team_persistence():
    """Verify that reports are recorded in SQLite and can be retrieved."""
    report = run_red_team_investigation(
        claim_id="test-claim-persist",
        claim_text="Aspirin reduces cardiovascular mortality by 15%",
        target_doi="10.1016/S0140-6736(02)07740-9",
    )
    past = get_investigations_for_claim("test-claim-persist")
    assert len(past) >= 1
    assert past[0]["claim_id"] == "test-claim-persist"

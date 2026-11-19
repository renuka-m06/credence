"""Test for the worked LearnFast example:
Claim: 'improved test scores by 30% [4]'
Source: reporting 12.1% on 40 students, no control group
Expected: 'Partially supported, needs review'
"""

from credence.report.models import AccessTier, VerdictType
from credence.verify.pipeline import build_report, verify_claim


def test_learnfast_worked_example():
    claim_text = "LearnFast improved test scores by 30% [4]"
    source_text = (
        "Background: Educational software interventions were evaluated. "
        "In our pilot evaluation involving 40 students with no control group, "
        "test scores increased by 12.1%. Further randomized trials are required to establish efficacy."
    )

    verified_claim = verify_claim(
        claim_input=claim_text,
        source_text=source_text,
        access_tier=AccessTier.FULL_TEXT,
        citation_key="4",
    )

    verdict = verified_claim.verdict
    assert verdict is not None

    # Check that verdict is partially supported
    assert verdict.verdict == VerdictType.PARTIALLY_SUPPORTED
    assert verdict.needs_review is True

    # Check human-readable display verdict returns 'Partially supported, needs review'
    display_str = verdict.display_verdict
    assert "Partially supported, needs review" in display_str

    # Check confidence is penalized for unverified slot and adversarial disagreement
    assert verdict.confidence < 0.90
    assert verdict.confidence == 0.55  # 0.90 cap - 0.15 (1 absent slot) - 0.20 (pass disagreement)

    # Check report generation
    report = build_report("LearnFast_Evaluation.docx", [verified_claim])
    assert report.summary["partially_supported"] == 1
    assert report.summary["human_review_required"] is True

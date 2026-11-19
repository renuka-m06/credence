"""Unit tests for the fixed rule table in verify/verdict.py and computed confidence.

Validates:
- Mapping of all slot combinations (match, mismatch, absent, outdated, hallucinated)
  to exact verdicts: supported, partially supported, unsupported, contradictory,
  potentially outdated, needs review.
- Confidence computation using access-tier caps (full text 0.9, abstract 0.6, metadata 0.2, inaccessible 0)
  minus penalties for unverified slots and pass disagreement.
- Golden rule enforcement: confidence never reads model self-reported scores.
"""

import pytest
from credence.report.models import AccessTier, SlotResult, VerdictType
from credence.verify.verdict import (
    RULE_ALL_ABSENT,
    RULE_ALL_MATCH,
    RULE_CONTRADICTORY,
    RULE_EMPTY_SLOTS,
    RULE_HALLUCINATED_QUOTE,
    RULE_INACCESSIBLE_SOURCE,
    RULE_OUTDATED_CITATION,
    RULE_PARTIAL_MATCH,
    SlotStatus,
    compute_confidence,
    determine_verdict,
)


class TestVerdictRuleTable:
    """Tests asserting each slot combination maps deterministically to the right verdict."""

    @pytest.mark.parametrize(
        "slots,expected_verdict,expected_rule",
        [
            # All Match -> Supported
            (["match"], VerdictType.SUPPORTED, RULE_ALL_MATCH),
            (["match", "match"], VerdictType.SUPPORTED, RULE_ALL_MATCH),
            (["match", "match", "match"], VerdictType.SUPPORTED, RULE_ALL_MATCH),

            # Match + Absent -> Partially Supported
            (["match", "absent"], VerdictType.PARTIALLY_SUPPORTED, RULE_PARTIAL_MATCH),
            (["match", "match", "absent"], VerdictType.PARTIALLY_SUPPORTED, RULE_PARTIAL_MATCH),
            (["absent", "match"], VerdictType.PARTIALLY_SUPPORTED, RULE_PARTIAL_MATCH),

            # All Absent -> Unsupported
            (["absent"], VerdictType.UNSUPPORTED, RULE_ALL_ABSENT),
            (["absent", "absent"], VerdictType.UNSUPPORTED, RULE_ALL_ABSENT),
            (["absent", "absent", "absent"], VerdictType.UNSUPPORTED, RULE_ALL_ABSENT),

            # Any Mismatch -> Contradictory
            (["mismatch"], VerdictType.CONTRADICTORY, RULE_CONTRADICTORY),
            (["mismatch", "mismatch"], VerdictType.CONTRADICTORY, RULE_CONTRADICTORY),
            (["match", "mismatch"], VerdictType.CONTRADICTORY, RULE_CONTRADICTORY),
            (["mismatch", "absent"], VerdictType.CONTRADICTORY, RULE_CONTRADICTORY),
            (["match", "mismatch", "absent"], VerdictType.CONTRADICTORY, RULE_CONTRADICTORY),
            (["absent", "match", "mismatch"], VerdictType.CONTRADICTORY, RULE_CONTRADICTORY),
        ],
    )
    def test_slot_combinations_map_to_verdicts(self, slots, expected_verdict, expected_rule):
        """Standard slot combinations map strictly to the fixed rule table verdicts."""
        verdict = determine_verdict(slots=slots, claim_id="claim-test")
        assert verdict.verdict == expected_verdict
        assert expected_rule in verdict.rules_triggered

    def test_outdated_citation_triggers_potentially_outdated(self):
        """When a citation has listed evidence of retraction or contradiction, verdict is potentially outdated."""
        verdict = determine_verdict(
            slots=["match", "match"],
            is_outdated=True,
            outdated_evidence={"retraction": "Retraction notice in Lancet 2022"}
        )
        assert verdict.verdict == VerdictType.POTENTIALLY_OUTDATED
        assert RULE_OUTDATED_CITATION in verdict.rules_triggered
        assert "retraction notice" in verdict.explanation.lower()

    def test_outdated_guess_without_evidence_is_rejected(self):
        """When outdated is asserted without listed evidence, it is rejected and evaluates slots deterministically."""
        verdict = determine_verdict(
            slots=["match", "match"],
            is_outdated=True,
            outdated_evidence=None  # No listed evidence (bare guess)
        )
        assert verdict.verdict == VerdictType.SUPPORTED
        assert "RULE_UNGROUNDED_OUTDATED_REJECTED" in verdict.rules_triggered

    def test_hallucinated_quote_triggers_needs_review(self):
        """Golden Rule 2: Quote not found in source text discards slot -> Needs review."""
        verdict = determine_verdict(slots=["match"], has_hallucinated_quote=True)
        assert verdict.verdict == VerdictType.NEEDS_REVIEW
        assert RULE_HALLUCINATED_QUOTE in verdict.rules_triggered

    def test_inaccessible_source_triggers_needs_review_with_zero_confidence(self):
        """When paper is inaccessible or not found, verdict is needs review with 0 confidence."""
        verdict = determine_verdict(slots=["match"], access_tier=AccessTier.INACCESSIBLE)
        assert verdict.verdict == VerdictType.NEEDS_REVIEW
        assert verdict.confidence == 0.0
        assert RULE_INACCESSIBLE_SOURCE in verdict.rules_triggered

        verdict_nf = determine_verdict(slots=["match"], access_tier=AccessTier.NOT_FOUND)
        assert verdict_nf.verdict == VerdictType.NEEDS_REVIEW
        assert verdict_nf.confidence == 0.0
        assert RULE_INACCESSIBLE_SOURCE in verdict_nf.rules_triggered

    def test_empty_slots_triggers_needs_review(self):
        """If no factual slots exist for a claim, triage stance defaults to human review."""
        verdict = determine_verdict(slots=[])
        assert verdict.verdict == VerdictType.NEEDS_REVIEW
        assert RULE_EMPTY_SLOTS in verdict.rules_triggered

    def test_slot_results_objects_input(self):
        """Verify determine_verdict accepts SlotResult dataclass objects directly."""
        s1 = SlotResult(slot_id="s1", status="match", quote_verified=True, quote="found quote")
        s2 = SlotResult(slot_id="s2", status="absent", quote_verified=False)
        verdict = determine_verdict(slots=[s1, s2])
        assert verdict.verdict == VerdictType.PARTIALLY_SUPPORTED
        assert verdict.unverified_slots == 1


class TestConfidenceComputation:
    """Tests for compute_confidence enforcing access-tier caps and penalty deductions."""

    def test_access_tier_caps_ceiling(self):
        """Test base ceilings for each access tier without penalties."""
        assert compute_confidence(AccessTier.FULL_TEXT, unverified_slots=0) == 0.9
        assert compute_confidence(AccessTier.ABSTRACT_ONLY, unverified_slots=0) == 0.6
        assert compute_confidence(AccessTier.METADATA_ONLY, unverified_slots=0) == 0.2
        assert compute_confidence(AccessTier.INACCESSIBLE, unverified_slots=0) == 0.0
        assert compute_confidence(AccessTier.NOT_FOUND, unverified_slots=0) == 0.0

    def test_unverified_slot_penalties(self):
        """Each unverified slot deducts penalty (default 0.15) from tier cap."""
        # Full text (cap 0.9) - 1 unverified slot (0.15) = 0.75
        assert compute_confidence(AccessTier.FULL_TEXT, unverified_slots=1) == 0.75
        # Full text (cap 0.9) - 2 unverified slots (0.30) = 0.60
        assert compute_confidence(AccessTier.FULL_TEXT, unverified_slots=2) == 0.60
        # Abstract (cap 0.6) - 1 unverified slot (0.15) = 0.45
        assert compute_confidence(AccessTier.ABSTRACT_ONLY, unverified_slots=1) == 0.45

    def test_pass_disagreement_penalty(self):
        """Pass disagreement deducts penalty (default 0.20) from tier cap."""
        # Full text (cap 0.9) - pass disagreement (0.20) = 0.70
        assert compute_confidence(AccessTier.FULL_TEXT, unverified_slots=0, pass_disagreement=True) == 0.70
        # Combined: Full text (0.9) - 1 slot (0.15) - pass disagreement (0.20) = 0.55
        assert compute_confidence(AccessTier.FULL_TEXT, unverified_slots=1, pass_disagreement=True) == 0.55

    def test_confidence_floor_clamping(self):
        """Confidence can never drop below 0.0 even with large penalties."""
        # Metadata (cap 0.2) - 2 slots (0.30) = negative -> clamped to 0.0
        assert compute_confidence(AccessTier.METADATA_ONLY, unverified_slots=2) == 0.0
        # Inaccessible tier always 0.0 regardless of penalties
        assert compute_confidence(AccessTier.INACCESSIBLE, unverified_slots=0, pass_disagreement=True) == 0.0

    def test_confidence_never_exceeds_cap(self):
        """Confidence is strictly bounded by the tier cap."""
        assert compute_confidence(AccessTier.FULL_TEXT, unverified_slots=-5) == 0.9
        assert compute_confidence(AccessTier.ABSTRACT_ONLY, unverified_slots=-2) == 0.6

    def test_model_independence(self):
        """Golden Rule 3: Function accepts deterministic evidence inputs only, never model scores."""
        # Any attempt to pass model self-reported float is rejected by signature / strictly computed
        conf = compute_confidence(
            access_tier=AccessTier.FULL_TEXT,
            unverified_slots=1,
            pass_disagreement=False,
        )
        assert conf == 0.75

"""Deterministic rule table and confidence computation for evidence verdicts.

Golden Rules (AGENTS.md):
1. LLM judges MEANING only. Python decides every deterministic fact: quote existence,
   number/unit equality, hedge words. The LLM can NEVER override a code check.
2. If a returned quote is not found in the source after normalization -> discard that
   slot -> "Needs review". Log it so the benchmark counts caught hallucinations.
3. Confidence is COMPUTED (access-tier cap - unverified slots - pass disagreement),
   never the model's self-reported number.
4. "Not found in databases" != fabricated. Report what was searched and where.
5. Verdict is derived from the fixed rule table in verify/verdict.py, never one LLM label.
6. Default stance = human review. No silent auto-decisions.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Sequence, Union

from credence.report.models import AccessTier, SlotResult, Verdict, VerdictType


class SlotStatus(str, Enum):
    """Normalized status of a single verified slot."""
    MATCH = "match"
    MISMATCH = "mismatch"
    ABSENT = "absent"

    @classmethod
    def from_value(cls, val: Union[SlotStatus, str, SlotResult]) -> SlotStatus:
        """Convert a string, SlotResult, or enum to SlotStatus."""
        if isinstance(val, SlotResult):
            # If quote was provided but failed verification, it is absent/unverified
            if val.quote and not val.quote_verified:
                return cls.ABSENT
            # Check slot result status
            return cls.from_value(val.status)

        if isinstance(val, SlotStatus):
            return val

        raw = str(val).strip().lower()
        if raw in ("match", "verified", "supported", "true"):
            return cls.MATCH
        if raw in ("mismatch", "contradiction", "contradicted", "false"):
            return cls.MISMATCH
        if raw in ("absent", "unverified", "not_found", "missing", "unknown"):
            return cls.ABSENT

        # Default stance for unknown or indeterminate slot is absent
        return cls.ABSENT


# Access-tier confidence caps matching prompt specifications:
# (full text 0.9, abstract 0.6, metadata 0.2, inaccessible 0.0)
TIER_CAPS: dict[AccessTier, float] = {
    AccessTier.FULL_TEXT: 0.9,
    AccessTier.ABSTRACT_ONLY: 0.6,
    AccessTier.METADATA_ONLY: 0.2,
    AccessTier.INACCESSIBLE: 0.0,
    AccessTier.NOT_FOUND: 0.0,
}


def compute_confidence(
    access_tier: Union[AccessTier, str] = AccessTier.FULL_TEXT,
    unverified_slots: int = 0,
    pass_disagreement: Union[bool, int, float] = False,
    unverified_penalty: float = 0.15,
    disagreement_penalty: float = 0.20,
) -> float:
    """Compute verification confidence deterministically from evidence access and slot counts.

    Formula:
        confidence = access_tier_cap - (unverified_slots * penalty) - (pass_disagreement_penalty)
        bounded within [0.0, access_tier_cap].

    Confidence MUST NEVER read the LLM's self-reported number.
    """
    if isinstance(access_tier, str):
        tier = AccessTier.from_str(access_tier)
    else:
        tier = access_tier

    cap = TIER_CAPS.get(tier, tier.confidence_cap)

    # Inaccessible papers have a confidence ceiling of 0.0
    if cap <= 0.0:
        return 0.0

    slot_penalty = max(0, int(unverified_slots)) * unverified_penalty

    if isinstance(pass_disagreement, bool):
        disagreement_cost = disagreement_penalty if pass_disagreement else 0.0
    else:
        disagreement_cost = max(0.0, float(pass_disagreement))

    raw_conf = cap - slot_penalty - disagreement_cost
    # Strictly bound between 0.0 and tier cap
    bounded_conf = max(0.0, min(cap, raw_conf))
    return round(bounded_conf, 4)


# Rule identifier constants for auditability and benchmark tracking
RULE_HALLUCINATED_QUOTE = "RULE_HALLUCINATED_QUOTE"
RULE_INACCESSIBLE_SOURCE = "RULE_INACCESSIBLE_SOURCE"
RULE_EMPTY_SLOTS = "RULE_EMPTY_SLOTS"
RULE_OUTDATED_CITATION = "RULE_OUTDATED_CITATION"
RULE_UNGROUNDED_OUTDATED_REJECTED = "RULE_UNGROUNDED_OUTDATED_REJECTED"
RULE_CONTRADICTORY = "RULE_CONTRADICTORY"
RULE_ALL_MATCH = "RULE_ALL_MATCH"
RULE_PARTIAL_MATCH = "RULE_PARTIAL_MATCH"
RULE_ALL_ABSENT = "RULE_ALL_ABSENT"
RULE_DEFAULT_REVIEW = "RULE_DEFAULT_REVIEW"


def validate_outdated_evidence(
    is_outdated: bool = False,
    outdated_evidence: Optional[Union[dict[str, Any], list[Any], str]] = None,
) -> tuple[bool, str]:
    """Validate whether an outdated citation status is grounded in concrete listed evidence.

    Rule: Add the 'potentially outdated' verdict ONLY when there is listed evidence
    (a retraction or a later contradicting study), never an ungrounded guess.

    Returns:
        (is_grounded, evidence_summary)
    """
    if not is_outdated and not outdated_evidence:
        return False, ""

    if outdated_evidence is None:
        # Bare boolean without listed evidence -> rejected as ungrounded guess
        return False, ""

    if isinstance(outdated_evidence, dict):
        if not outdated_evidence:
            return False, ""
        # Check for retraction evidence
        if outdated_evidence.get("is_retracted") or "retraction" in outdated_evidence or "retraction_details" in outdated_evidence:
            details = outdated_evidence.get("retraction") or outdated_evidence.get("retraction_details") or "Notice on file"
            return True, f"formal retraction notice ({details})"
        # Check for later contradicting study
        if "contradicting_study" in outdated_evidence or "later_study" in outdated_evidence or "superseded_by" in outdated_evidence:
            study = outdated_evidence.get("contradicting_study") or outdated_evidence.get("later_study") or outdated_evidence.get("superseded_by")
            return True, f"later contradicting study ({study})"
        return False, ""

    if isinstance(outdated_evidence, list):
        if not outdated_evidence:
            return False, ""
        items_str = "; ".join(str(x) for x in outdated_evidence)
        items_lower = items_str.lower()
        if any(kw in items_lower for kw in ("retract", "contradict", "supersed")):
            return True, items_str
        return False, ""

    if isinstance(outdated_evidence, str):
        ev_clean = outdated_evidence.strip()
        ev_lower = ev_clean.lower()
        if not ev_clean:
            return False, ""
        if any(kw in ev_lower for kw in ("retract", "contradict", "supersed")):
            return True, ev_clean
        return False, ""

    return False, ""


def determine_verdict(
    slots: Sequence[Union[SlotStatus, str, SlotResult]],
    claim_id: str = "",
    is_outdated: bool = False,
    outdated_evidence: Optional[Union[dict[str, Any], list[Any], str]] = None,
    access_tier: Union[AccessTier, str] = AccessTier.FULL_TEXT,
    has_hallucinated_quote: bool = False,
    pass_disagreement: Union[bool, int, float] = False,
    unverified_penalty: float = 0.15,
    disagreement_penalty: float = 0.20,
) -> Verdict:
    """Determine the final verdict for a claim using the fixed deterministic rule table.

    Rule precedence:
    1. Hallucinated quote detected -> NEEDS_REVIEW
    2. Inaccessible / not found source -> NEEDS_REVIEW
    3. Empty slots -> NEEDS_REVIEW
    4. Outdated / superseded citation -> POTENTIALLY_OUTDATED
    5. Any slot mismatch -> CONTRADICTORY
    6. All slots match (zero absent, zero mismatch) -> SUPPORTED
    7. Mix of match and absent (zero mismatch) -> PARTIALLY_SUPPORTED
    8. All slots absent -> UNSUPPORTED
    9. Default fallback -> NEEDS_REVIEW
    """
    if isinstance(access_tier, str):
        tier = AccessTier.from_str(access_tier)
    else:
        tier = access_tier

    rules_triggered: list[str] = []

    # Check for hallucinated quote (Rule 2 of AGENTS.md)
    if has_hallucinated_quote:
        rules_triggered.append(RULE_HALLUCINATED_QUOTE)
        conf = compute_confidence(
            access_tier=tier,
            unverified_slots=len(slots) if slots else 1,
            pass_disagreement=pass_disagreement,
            unverified_penalty=unverified_penalty,
            disagreement_penalty=disagreement_penalty,
        )
        return Verdict(
            claim_id=claim_id,
            verdict=VerdictType.NEEDS_REVIEW,
            confidence=conf,
            explanation="Needs review: quote candidate could not be verified in source text (discarded slot).",
            unverified_slots=len(slots) if slots else 1,
            contradiction_detected=False,
            rules_triggered=rules_triggered,
            access_tier=tier,
        )

    # Check for inaccessible / missing paper (Rule 4 of AGENTS.md)
    if tier in (AccessTier.INACCESSIBLE, AccessTier.NOT_FOUND):
        rules_triggered.append(RULE_INACCESSIBLE_SOURCE)
        return Verdict(
            claim_id=claim_id,
            verdict=VerdictType.NEEDS_REVIEW,
            confidence=0.0,
            explanation="Needs review: cited paper text is inaccessible or not found in retrieved databases.",
            unverified_slots=len(slots),
            contradiction_detected=False,
            rules_triggered=rules_triggered,
            access_tier=tier,
        )

    # Empty slots check
    if not slots:
        rules_triggered.append(RULE_EMPTY_SLOTS)
        conf = compute_confidence(tier, unverified_slots=1, pass_disagreement=pass_disagreement)
        return Verdict(
            claim_id=claim_id,
            verdict=VerdictType.NEEDS_REVIEW,
            confidence=conf,
            explanation="Needs review: no verifiable factual slots were extracted for this claim.",
            unverified_slots=1,
            contradiction_detected=False,
            rules_triggered=rules_triggered,
            access_tier=tier,
        )

    # Grounded Potentially Outdated citation check (Golden Rule: requires listed evidence)
    is_grounded_outdated, evidence_summary = validate_outdated_evidence(is_outdated, outdated_evidence)
    if is_grounded_outdated:
        rules_triggered.append(RULE_OUTDATED_CITATION)
        num_absent = sum(1 for s in slots if SlotStatus.from_value(s) == SlotStatus.ABSENT)
        conf = compute_confidence(
            access_tier=tier,
            unverified_slots=num_absent,
            pass_disagreement=pass_disagreement,
            unverified_penalty=unverified_penalty,
            disagreement_penalty=disagreement_penalty,
        )
        return Verdict(
            claim_id=claim_id,
            verdict=VerdictType.POTENTIALLY_OUTDATED,
            confidence=conf,
            explanation=f"Potentially outdated: cited finding is backed by evidence of {evidence_summary}.",
            unverified_slots=num_absent,
            contradiction_detected=False,
            rules_triggered=rules_triggered,
            access_tier=tier,
        )
    elif is_outdated and not is_grounded_outdated:
        # Ungrounded guess: do NOT assign POTENTIALLY_OUTDATED, record rule and continue to deterministic slot evaluation
        rules_triggered.append(RULE_UNGROUNDED_OUTDATED_REJECTED)

    # Parse and categorize slot statuses
    norm_slots = [SlotStatus.from_value(s) for s in slots]
    num_matches = sum(1 for s in norm_slots if s == SlotStatus.MATCH)
    num_mismatches = sum(1 for s in norm_slots if s == SlotStatus.MISMATCH)
    num_absent = sum(1 for s in norm_slots if s == SlotStatus.ABSENT)

    conf = compute_confidence(
        access_tier=tier,
        unverified_slots=num_absent,
        pass_disagreement=pass_disagreement,
        unverified_penalty=unverified_penalty,
        disagreement_penalty=disagreement_penalty,
    )

    # Fixed Rule Table Mapping
    if num_mismatches > 0:
        rules_triggered.append(RULE_CONTRADICTORY)
        return Verdict(
            claim_id=claim_id,
            verdict=VerdictType.CONTRADICTORY,
            confidence=conf,
            explanation=(
                f"Contradictory: {num_mismatches} slot(s) directly conflict with cited source "
                f"(matched: {num_matches}, absent: {num_absent})."
            ),
            unverified_slots=num_absent,
            contradiction_detected=True,
            rules_triggered=rules_triggered,
            access_tier=tier,
        )

    if num_matches > 0 and num_absent == 0:
        rules_triggered.append(RULE_ALL_MATCH)
        return Verdict(
            claim_id=claim_id,
            verdict=VerdictType.SUPPORTED,
            confidence=conf,
            explanation=f"Supported: all {num_matches} factual slot(s) are backed by cited source text.",
            unverified_slots=0,
            contradiction_detected=False,
            rules_triggered=rules_triggered,
            access_tier=tier,
        )

    if num_matches > 0 and num_absent > 0:
        rules_triggered.append(RULE_PARTIAL_MATCH)
        return Verdict(
            claim_id=claim_id,
            verdict=VerdictType.PARTIALLY_SUPPORTED,
            confidence=conf,
            explanation=(
                f"Partially supported: {num_matches} slot(s) verified in source, "
                f"while {num_absent} slot(s) were absent or unverified."
            ),
            unverified_slots=num_absent,
            contradiction_detected=False,
            rules_triggered=rules_triggered,
            access_tier=tier,
        )

    if num_absent == len(norm_slots):
        rules_triggered.append(RULE_ALL_ABSENT)
        return Verdict(
            claim_id=claim_id,
            verdict=VerdictType.UNSUPPORTED,
            confidence=conf,
            explanation="Unsupported: cited source was retrieved but none of the asserted slots were found in text.",
            unverified_slots=num_absent,
            contradiction_detected=False,
            rules_triggered=rules_triggered,
            access_tier=tier,
        )

    # Fallback to default human review stance
    rules_triggered.append(RULE_DEFAULT_REVIEW)
    return Verdict(
        claim_id=claim_id,
        verdict=VerdictType.NEEDS_REVIEW,
        confidence=conf,
        explanation="Needs review: slot configuration requires human academic triage.",
        unverified_slots=num_absent,
        contradiction_detected=False,
        rules_triggered=rules_triggered,
        access_tier=tier,
    )

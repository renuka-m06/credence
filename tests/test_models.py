"""Unit tests for Credence report models and access tier confidence caps."""

from credence.report.models import (
    AccessTier,
    Claim,
    Report,
    Slot,
    SlotResult,
    Verdict,
    VerdictType,
)


def test_access_tier_caps():
    """Verify access tier confidence caps strictly follow AGENTS.md rules."""
    assert AccessTier.FULL_TEXT.confidence_cap == 0.9
    assert AccessTier.ABSTRACT_ONLY.confidence_cap == 0.6
    assert AccessTier.METADATA_ONLY.confidence_cap == 0.2
    assert AccessTier.INACCESSIBLE.confidence_cap == 0.0
    assert AccessTier.NOT_FOUND.confidence_cap == 0.0


def test_models_roundtrip_serialization():
    """Verify dataclasses serialize to dict and deserialize back faithfully."""
    slot = Slot(
        id="slot-1",
        claim_id="claim-101",
        citation_key="Smith2023",
        field_type="quote",
        expected_value="12.1% reduction",
        description="Reported 30-day mortality reduction"
    )

    slot_result = SlotResult(
        slot_id="slot-1",
        quote="demonstrated a 12.1% reduction in 30-day mortality",
        quote_verified=True,
        quote_span=(100, 153),
        number_match=True,
        hedge_match=True,
        status="verified",
        source_doi="10.1000/182",
        access_tier=AccessTier.FULL_TEXT,
    )

    verdict = Verdict(
        claim_id="claim-101",
        verdict=VerdictType.SUPPORTED,
        confidence=0.95,
        explanation="Direct verbatim quote confirms claim.",
        unverified_slots=0,
        contradiction_detected=False,
        rules_triggered=["rule_exact_quote_match"],
        access_tier=AccessTier.FULL_TEXT,
    )

    claim = Claim(
        id="claim-101",
        text="Compound-X reduced 30-day mortality by 12.1%.",
        citation_keys=["Smith2023"],
        source_location="Page 4, Results",
        slots=[slot],
        slot_results=[slot_result],
        verdict=verdict,
    )

    report = Report(
        document_name="manuscript_draft.docx",
        claims=[claim],
        access_tier=AccessTier.FULL_TEXT,
        overall_confidence=0.95,
        summary={"total_claims": 1, "supported": 1},
    )

    data = report.to_dict()
    assert data["document_name"] == "manuscript_draft.docx"
    assert data["access_tier"] == "full_text"
    assert len(data["claims"]) == 1

    reconstructed = Report.from_dict(data)
    assert reconstructed.document_name == report.document_name
    assert reconstructed.access_tier == AccessTier.FULL_TEXT
    assert len(reconstructed.claims) == 1
    assert reconstructed.claims[0].verdict.verdict == VerdictType.SUPPORTED
    assert reconstructed.claims[0].slot_results[0].quote_verified is True

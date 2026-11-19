"""Demonstration of the worked LearnFast verification pipeline example.

Claim: "LearnFast improved test scores by 30% [4]"
Cited Source: Study reporting 12.1% increase on 40 students with no control group.
Expected Outcome: "Partially supported, needs review"
"""

from credence.report.models import AccessTier
from credence.verify.pipeline import build_report, verify_claim


def main():
    print("=" * 80)
    print(" CREDENCE VERIFICATION PIPELINE: WORKED LEARNFAST EXAMPLE")
    print("=" * 80)

    claim_text = "LearnFast improved test scores by 30% [4]"
    source_text = (
        "Background: Educational software interventions were evaluated. "
        "In our pilot evaluation involving 40 students with no control group, "
        "test scores increased by 12.1%. Further randomized trials are required to establish efficacy."
    )

    print(f"\n[CLAIM]  : \"{claim_text}\"")
    print(f"[SOURCE] : \"{source_text}\"")
    print(f"[ACCESS] : AccessTier.FULL_TEXT (Cap: 0.90)\n")

    print("--- Executing Verification Pipeline ---")
    verified_claim = verify_claim(
        claim_input=claim_text,
        source_text=source_text,
        access_tier=AccessTier.FULL_TEXT,
        citation_key="4",
    )

    print("\n--- Atomized Slots & Results ---")
    for sr in verified_claim.slot_results:
        quote_status = "VERIFIED [OK]" if sr.quote_verified else "UNVERIFIED [FAIL]"
        print(f"  Slot: {sr.slot_id}")
        print(f"    - Status:        {sr.status.upper()}")
        print(f"    - Number Match:  {sr.number_match}")
        print(f"    - Quote Check:   {quote_status} (Span: {sr.quote_span})")
        print(f"    - Quote:         \"{sr.quote}\"")

    verdict = verified_claim.verdict
    print("\n" + "=" * 80)
    print(" FINAL VERDICT & COMPUTED CONFIDENCE")
    print("=" * 80)
    print(f"  Verdict (Raw)       : {verdict.verdict.value}")
    print(f"  Display Verdict     : {verdict.display_verdict}")
    print(f"  Computed Confidence : {verdict.confidence:.2f} (Access Cap 0.90 - unverified 0.15 - pass disagreement 0.20)")
    print(f"  Human Review Needed : {verdict.needs_review}")
    print(f"  Rules Triggered     : {verdict.rules_triggered}")
    print(f"  Detailed Triage     : {verdict.explanation}")
    print("=" * 80)

    report = build_report("LearnFast_Evaluation.docx", [verified_claim])
    print("\nReport Summary JSON:")
    print(f"  Total Claims:            {report.summary['total_claims']}")
    print(f"  Partially Supported:     {report.summary['partially_supported']}")
    print(f"  Human Review Required:   {report.summary['human_review_required']}")
    print(f"  Overall Confidence:      {report.overall_confidence:.2f}")


if __name__ == "__main__":
    main()

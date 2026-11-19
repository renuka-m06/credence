"""Adversarial verification pass hunting for contradicting evidence and methodological flaws.

Rules (AGENTS.md):
- LLM judges MEANING only. Python decides every deterministic fact.
- Core principle: EVERY VERDICT CARRIES PROOF. The LLM must return a verbatim quote
  that OUR CODE confirms exists in the source.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from credence.report.models import Claim, SlotResult
from credence.verify.checks import hedge_check, number_check, polarity_check, quote_check
from credence.verify.retrieve import retrieve_evidence_passages


@dataclass
class AdversarialResult:
    """Findings from the adversarial counter-evidence retrieval pass."""
    contradiction_found: bool
    pass_disagreement: bool
    discrepancy_details: list[str] = field(default_factory=list)
    adversarial_quote: str = ""
    quote_verified: bool = False
    quote_span: Optional[tuple[int, int]] = None
    methodological_caveats: list[str] = field(default_factory=list)
    updated_slot_results: list[SlotResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contradiction_found": self.contradiction_found,
            "pass_disagreement": self.pass_disagreement,
            "discrepancy_details": self.discrepancy_details,
            "adversarial_quote": self.adversarial_quote,
            "quote_verified": self.quote_verified,
            "quote_span": self.quote_span,
            "methodological_caveats": self.methodological_caveats,
            "updated_slot_results": [r.to_dict() for r in self.updated_slot_results],
        }


# Lexicon of adversarial and methodological constraint terms
METHODOLOGY_CAVEAT_TERMS = {
    "no control group": "Study lacks a control group (uncontrolled cohort)",
    "without a control group": "Study lacks a control group (uncontrolled cohort)",
    "pilot evaluation": "Small pilot evaluation, not a definitive trial",
    "pilot study": "Preliminary pilot study",
    "uncontrolled": "Uncontrolled study design",
    "non-randomized": "Non-randomized intervention",
    "small sample": "Limited sample size",
    "in vitro": "In vitro laboratory finding, not human clinical evidence",
    "in mice": "Preclinical animal model, not verified in humans",
}


def run_adversarial_pass(
    claim: Claim,
    source_text: str,
    initial_slot_results: list[SlotResult],
) -> AdversarialResult:
    """Execute a second adversarial pass to identify contradicting passages or caveats.

    Hunts for:
    1. Direct numerical contradictions (e.g. claim asserts 30%, source reports 12.1%)
    2. Contrary directional findings (e.g. no significant improvement)
    3. Methodological limitations (e.g. no control group, pilot study of 40 students)
    """
    discrepancies: list[str] = []
    caveats: list[str] = []
    contradiction_found = False
    pass_disagreement = False
    best_quote = ""
    quote_verified = False
    quote_span = None

    # 1. Search for counter-evidence and methodology caveats in source
    adversarial_queries = [
        f"limitations of {claim.text[:50]}",
        "no control group pilot evaluation",
        "adverse effects failed to improve",
        "no significant difference",
    ]

    candidate_passages = []
    for q in adversarial_queries:
        candidate_passages.extend(retrieve_evidence_passages(q, source_text, top_k=2))

    # Also search for numerical passages
    num_query = " ".join(re.findall(r'\d+(?:\.\d+)?%?', claim.text))
    if num_query:
        candidate_passages.extend(retrieve_evidence_passages(num_query, source_text, top_k=3))

    # Deduplicate passages
    seen_texts = set()
    unique_passages = []
    for p in candidate_passages:
        if p.text not in seen_texts:
            seen_texts.add(p.text)
            unique_passages.append(p)

    # 2. Check for methodological caveats
    source_lower = source_text.lower()
    for term, desc in METHODOLOGY_CAVEAT_TERMS.items():
        if term in source_lower:
            caveats.append(desc)

    # 3. Deterministic check on retrieved passages against claim
    updated_results: list[SlotResult] = list(initial_slot_results)

    for p in unique_passages:
        # Run deterministic number check for genuine numerical value conflicts
        num_res = number_check(claim.text, p.text)
        # Genuine conflict: passage has a different percentage value AND the claim's asserted number is missing from the entire paper
        conflicting_mismatches = [
            m for m in num_res.details.get("mismatches", [])
            if m.get("type") == "value_mismatch"
            and not re.search(r'\b' + re.escape(str(m.get("claim_token", "")).replace('%', '').strip()) + r'\b', source_text)
        ]
        if conflicting_mismatches:
            # We found a genuine numerical contradiction in the source text!
            contradiction_found = True
            pass_disagreement = True
            discrepancies.append(conflicting_mismatches[0].get("message", num_res.reason))

            # Extract exact quote
            q_res = quote_check(p.text, source_text)
            if q_res.passed:
                best_quote = p.text
                quote_verified = True
                quote_span = q_res.details.get("span")

            # Update numerical slots (asserted number e.g. 30% is absent/unverified in source)
            for sr in updated_results:
                slot_obj = next((s for s in claim.slots if s.id == sr.slot_id), None)
                if slot_obj and slot_obj.field_type in ("number", "quantity"):
                    sr.number_match = False
                    sr.status = "absent"
                    sr.details["adversarial_finding"] = num_res.reason
                    if best_quote:
                        sr.quote = best_quote
                        sr.quote_verified = True
                        sr.quote_span = quote_span

        # Run hedge check
        hdg_res = hedge_check(claim.text, p.text)
        if not hdg_res.passed:
            discrepancies.append(hdg_res.reason)
            for sr in updated_results:
                sr.hedge_match = False
                sr.status = "absent"
                sr.details["scope_widen_failure"] = hdg_res.reason

        # Run polarity / negation check
        pol_res = polarity_check(claim.text, p.text)
        if not pol_res.passed:
            contradiction_found = True
            pass_disagreement = True
            discrepancies.append(pol_res.reason)
            for sr in updated_results:
                sr.status = "mismatch"
                sr.details["polarity_contradiction"] = pol_res.reason

    # Check if caveats were found
    if caveats:
        discrepancies.extend(caveats)
        pass_disagreement = True

    return AdversarialResult(
        contradiction_found=contradiction_found,
        pass_disagreement=pass_disagreement,
        discrepancy_details=discrepancies,
        adversarial_quote=best_quote,
        quote_verified=quote_verified,
        quote_span=quote_span,
        methodological_caveats=caveats,
        updated_slot_results=updated_results,
    )

"""Full verification pipeline: slot atomization, hybrid retrieval, checks, adversarial pass, and verdict."""

from __future__ import annotations

import re
from typing import Any, Optional, Union

from credence.report.models import AccessTier, Claim, Report, Slot, SlotResult, Verdict, VerdictType
from credence.verify.adversarial import run_adversarial_pass
from credence.verify.checks import (
    doi_mismatch_check,
    hedge_check,
    number_check,
    polarity_check,
    quote_check,
    retraction_check,
    secondary_source_check,
)
from credence.verify.retrieve import retrieve_evidence_passages
from credence.verify.slots import extract_slots
from credence.verify.verdict import SlotStatus, determine_verdict


def verify_claim(
    claim_input: Union[Claim, str],
    source_text: str,
    access_tier: AccessTier = AccessTier.FULL_TEXT,
    is_outdated: bool = False,
    outdated_evidence: Optional[Union[dict[str, Any], list[Any], str]] = None,
    candidate_paper: Optional[Any] = None,
    citation_key: str = "4",
    llm_client: Optional[Any] = None,
    simulated_hallucinated_quote: Optional[str] = None,
    resolver: Optional[Any] = None,
) -> Claim:
    """Execute complete verification pipeline for an individual claim against its cited source.

    Steps:
    1. Atomize claim into verifiable slots (finding, number, quote)
    2. Reference integrity check (retraction status, secondary-source hop)
    3. Primary retrieval pass (BM25 + embeddings + number-regex reranking)
    4. Primary deterministic verification (quote_check, number_check, hedge_check)
    5. Adversarial second pass hunting for contradictions and methodological limitations
    6. Final verdict calculation via fixed rule table and computed confidence
    """
    # 1. Structure Claim and extract slots
    if isinstance(claim_input, str):
        claim_id = "claim-1"
        slots = extract_slots(claim_input, claim_id=claim_id, citation_key=citation_key, llm_client=llm_client)
        claim = Claim(
            id=claim_id,
            text=claim_input,
            citation_keys=[citation_key],
            source_location="Manuscript",
            slots=slots,
        )
    else:
        claim = claim_input
        if not claim.slots:
            claim.slots = extract_slots(
                claim.text,
                claim_id=claim.id,
                citation_key=claim.citation_keys[0] if claim.citation_keys else citation_key,
                llm_client=llm_client,
            )

    # 2. Check candidate paper integrity (retraction & secondary source 1-hop traversal)
    primary_hop_info: Optional[dict[str, Any]] = None
    if candidate_paper is not None:
        # Check retraction
        ret_res = retraction_check(candidate_paper)
        if not ret_res.passed:
            is_outdated = True
            outdated_evidence = outdated_evidence or {
                "is_retracted": True,
                "retraction": getattr(candidate_paper, "retraction_details", {}) or ret_res.reason
            }

        # Check secondary source (review/survey)
        sec_res = secondary_source_check(candidate_paper)
        if not sec_res.passed:
            # Attempt 1 citation hop to original source
            if resolver is not None and hasattr(resolver, "follow_citation_hop"):
                hop_paper = resolver.follow_citation_hop(candidate_paper, claim.text)
                if hop_paper:
                    primary_hop_info = {
                        "original_title": hop_paper.title,
                        "original_doi": hop_paper.doi,
                        "original_source": hop_paper.source,
                    }
                    # Augment source text with original paper text or abstract if available
                    if hop_paper.abstract:
                        source_text = f"{source_text}\n\n[Original Source: {hop_paper.title}]\n{hop_paper.abstract}"

    slot_results: list[SlotResult] = []

    # 3. Primary evidence retrieval and verification
    for slot in claim.slots:
        passages = retrieve_evidence_passages(slot.expected_value or claim.text, source_text, top_k=3)
        best_passage = passages[0].text if passages else ""

        # Perform checks
        q_res = quote_check(best_passage, source_text) if best_passage else None
        n_res = number_check(claim.text, best_passage) if best_passage else None
        h_res = hedge_check(claim.text, best_passage) if best_passage else None
        p_res = polarity_check(claim.text, best_passage) if best_passage else None

        # Determine slot status
        retrieval_score = passages[0].final_score if passages else 0.0

        # Check informative word overlap between claim and best_passage (verifies passage topic relevance)
        claim_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', claim.text.lower()))
        stopwords = {"the", "and", "for", "with", "that", "this", "from", "was", "were", "are", "been", "have", "had", "which", "into", "their"}
        informative_words = claim_words - stopwords
        passage_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', best_passage.lower()))
        word_overlap = len(informative_words & passage_words) / len(informative_words) if informative_words else 1.0

        if not best_passage or retrieval_score < 0.10 or word_overlap < 0.20:
            # Unrelated source, irrelevant passage, or empty
            status = "absent"
        elif p_res and not p_res.passed:
            # Polarity contradiction (claim directly negates empirical findings in quote)
            status = "mismatch"
        elif slot.field_type in ("finding", "quote"):
            # Check if qualitative finding or quote is confirmed in passage
            # If hedge check failed on this passage, it cannot match as verified
            if h_res and not h_res.passed:
                status = "absent"
            else:
                finding_stems = (
                    "increas", "improv", "reduc", "favor", "benefit", "exhibit", "achiev",
                    "reach", "detect", "efficac", "efficien", "yield", "differ", "surviv",
                    "disrupt", "superconduct", "level", "fluctuat", "effect", "report",
                    "observ", "demonstrat", "confirm", "presen", "drop", "resist", "find", "occur"
                )
                has_finding = any(term in best_passage.lower() for term in finding_stems) if any(
                    t in claim.text.lower() for t in finding_stems
                ) else (word_overlap >= 0.25)

                status = "match" if has_finding else "absent"
        elif slot.field_type == "number":
            status = "match" if (n_res and n_res.passed) else "mismatch"
        else:
            status = "match" if (best_passage and q_res and q_res.passed) else "absent"

        slot_results.append(SlotResult(
            slot_id=slot.id,
            quote=best_passage,
            quote_verified=q_res.passed if q_res else False,
            quote_span=q_res.details.get("span") if (q_res and q_res.passed) else None,
            number_match=n_res.passed if n_res else None,
            hedge_match=h_res.passed if h_res else None,
            status=status,
            access_tier=access_tier,
            details={"retrieval_score": retrieval_score},
        ))

    # 3. Adversarial second pass hunting for counter-evidence and methodology caveats
    adv_res = run_adversarial_pass(claim, source_text, slot_results)
    final_slot_results = adv_res.updated_slot_results

    # If simulated hallucinated quote was injected to test code gate:
    if simulated_hallucinated_quote:
        q_sim = quote_check(simulated_hallucinated_quote, source_text)
        final_slot_results.append(SlotResult(
            slot_id="slot-hallucinated",
            quote=simulated_hallucinated_quote,
            quote_verified=q_sim.passed,
            quote_span=q_sim.details.get("span") if q_sim.passed else None,
            status="match" if q_sim.passed else "absent",
            access_tier=access_tier,
            details={"hallucination_tested": True, "caught_by_code": not q_sim.passed},
        ))

    claim.slot_results = final_slot_results

    # 4. Determine final verdict from fixed rule table
    has_hallucinated = any(sr.quote and not sr.quote_verified for sr in final_slot_results)

    verdict = determine_verdict(
        slots=final_slot_results,
        claim_id=claim.id,
        is_outdated=is_outdated,
        outdated_evidence=outdated_evidence,
        access_tier=access_tier,
        has_hallucinated_quote=has_hallucinated,
        pass_disagreement=adv_res.pass_disagreement,
    )

    # Attach secondary source hop details if traversed
    if primary_hop_info:
        for sr in claim.slot_results:
            sr.details["primary_source_hop"] = primary_hop_info
        verdict.explanation += f" (Secondary source review resolved to primary empirical study: {primary_hop_info.get('original_title')})"

    # If adversarial pass found contradiction/caveat but partial finding was supported:
    # Set clear explanation and human-review stance
    if adv_res.contradiction_found:
        verdict.explanation += f" Adversarial pass flagged: {'; '.join(adv_res.discrepancy_details)}."

    claim.verdict = verdict
    return claim


def build_report(
    document_name: str,
    claims: list[Claim],
    access_tier: AccessTier = AccessTier.FULL_TEXT,
    metadata: Optional[dict[str, Any]] = None,
) -> Report:
    """Wire verified claims into a comprehensive human-reviewable Report."""
    total = len(claims)
    supported_cnt = sum(1 for c in claims if c.verdict and c.verdict.verdict == VerdictType.SUPPORTED)
    partial_cnt = sum(1 for c in claims if c.verdict and c.verdict.verdict == VerdictType.PARTIALLY_SUPPORTED)
    unsupported_cnt = sum(1 for c in claims if c.verdict and c.verdict.verdict == VerdictType.UNSUPPORTED)
    contradictory_cnt = sum(1 for c in claims if c.verdict and c.verdict.verdict == VerdictType.CONTRADICTORY)
    review_cnt = sum(1 for c in claims if c.verdict and c.verdict.verdict == VerdictType.NEEDS_REVIEW)

    avg_conf = (
        sum(c.verdict.confidence for c in claims if c.verdict) / total
        if total > 0 else 0.0
    )

    summary = {
        "total_claims": total,
        "supported": supported_cnt,
        "partially_supported": partial_cnt,
        "unsupported": unsupported_cnt,
        "contradictory": contradictory_cnt,
        "needs_review": review_cnt,
        "human_review_required": review_cnt > 0 or partial_cnt > 0 or contradictory_cnt > 0,
    }

    return Report(
        document_name=document_name,
        claims=claims,
        access_tier=access_tier,
        overall_confidence=round(avg_conf, 4),
        summary=summary,
        metadata=metadata or {},
    )

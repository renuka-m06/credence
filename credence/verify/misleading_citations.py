"""Misleading Citation Detection Module for Credence.

Identifies citations that are genuine or present but fail to support the empirical claims
associated with them.

Detects the following situations:
A. Citation exists but discusses an unrelated topic (UNRELATED CITATION)
B. Citation is relevant to the topic but does not support the specific claim (MISLEADING CITATION)
C. Citation reports findings that contradict the claim (CONTRADICTORY CITATION)
D. Citation contains different numerical values from those mentioned (MISLEADING CITATION)
E. Citation points to an incorrect research paper / DOI mismatch (UNRELATED CITATION)
F. Claim has no citation (MISSING CITATION)

Classifications:
- VALID CITATION
- MISLEADING CITATION
- UNRELATED CITATION
- CONTRADICTORY CITATION
- MISSING CITATION
- NEEDS REVIEW

Rules (AGENTS.md):
- LLM judges MEANING only. Python decides every deterministic fact.
- Never allow an LLM to independently determine the final verdict.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union

from credence.report.models import AccessTier, Claim, VerdictType
from credence.resolve.matcher import CandidatePaper, check_doi_mismatch
from credence.resolve.reference import Reference
from credence.verify.checks import (
    doi_mismatch_check,
    number_check,
    polarity_check,
    quote_check,
)
from credence.verify.retrieve import retrieve_evidence_passages
from credence.verify.verdict import compute_confidence


class CitationClassification(str, Enum):
    """Primary classification of citation truthfulness and relevance."""
    VALID_CITATION = "VALID CITATION"
    MISLEADING_CITATION = "MISLEADING CITATION"
    UNRELATED_CITATION = "UNRELATED CITATION"
    CONTRADICTORY_CITATION = "CONTRADICTORY CITATION"
    MISSING_CITATION = "MISSING CITATION"
    NEEDS_REVIEW = "NEEDS REVIEW"

    @property
    def display_name(self) -> str:
        return self.value


class MisleadingSituation(str, Enum):
    """Specific empirical situation detected in the claim-citation pair."""
    UNRELATED_TOPIC = "unrelated_topic"                   # Situation A
    UNSUPPORTED_SPECIFIC_CLAIM = "unsupported_claim"       # Situation B
    CONTRADICTORY_FINDINGS = "contradictory_findings"     # Situation C
    NUMBER_MISMATCH = "number_mismatch"                   # Situation D
    INCORRECT_PAPER = "incorrect_paper"                   # Situation E
    MISSING_CITATION = "missing_citation"                 # Situation F
    VERIFIED_VALID = "verified_valid"                     # Valid citation
    INACCESSIBLE_OR_UNVERIFIED = "needs_review"           # Needs review


@dataclass
class MisleadingCitationResult:
    """Comprehensive diagnostic result for a single claim-citation pair."""
    claim_id: str
    original_claim: str
    classification: CitationClassification
    citation_details: dict[str, Any]
    retrieved_source: dict[str, Any]
    passage: str
    explanation: str
    confidence: float
    situation: MisleadingSituation
    rules_triggered: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["classification"] = self.classification.value
        data["situation"] = self.situation.value
        return data


@dataclass
class MisleadingCitationReport:
    """Document-wide misleading citation audit dossier."""
    document_name: str
    total_claims: int
    valid_citations: int
    misleading_citations: int
    unrelated_citations: int
    contradictory_citations: int
    missing_citations: int
    needs_review_citations: int
    results: list[MisleadingCitationResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_name": self.document_name,
            "total_claims": self.total_claims,
            "summary": {
                "valid": self.valid_citations,
                "misleading": self.misleading_citations,
                "unrelated": self.unrelated_citations,
                "contradictory": self.contradictory_citations,
                "missing": self.missing_citations,
                "needs_review": self.needs_review_citations,
            },
            "results": [r.to_dict() for r in self.results],
        }


# Standard common stop words for topic relevance overlap
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "was", "were", "are",
    "been", "have", "had", "which", "into", "their", "about", "above", "after",
    "before", "between", "both", "during", "each", "further", "once", "other",
    "some", "such", "than", "through", "under", "until", "while", "where", "what",
}


def compute_topic_overlap(claim_text: str, source_text: str) -> float:
    """Compute informative lexical topic overlap between a claim and a candidate source text."""
    if not claim_text or not source_text:
        return 0.0

    c_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', claim_text.lower())) - _STOPWORDS
    s_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', source_text.lower())) - _STOPWORDS

    if not c_words or not s_words:
        return 0.0

    inter = len(c_words & s_words)
    return inter / len(c_words)


def audit_citation(
    claim: Claim,
    candidate_paper: Optional[CandidatePaper] = None,
    source_text: str = "",
    reference_entry: Optional[Reference] = None,
    citation_key: Optional[str] = None,
) -> MisleadingCitationResult:
    """Deterministically audit a claim against its cited reference.

    Evaluates situations A-F without letting any LLM dictate the outcome:
    - F: Claim has no citation (MISSING CITATION)
    - E: Citation points to an incorrect research paper (UNRELATED CITATION)
    - A: Citation exists but discusses an unrelated topic (UNRELATED CITATION)
    - C: Citation reports findings that contradict the claim (CONTRADICTORY CITATION)
    - D: Citation contains different numerical values (MISLEADING CITATION)
    - B: Citation is relevant to topic but does not support specific claim (MISLEADING CITATION)
    - Valid: Citation verified with supporting verbatim passage (VALID CITATION)
    - Fallback: Inaccessible source or unverified quote (NEEDS REVIEW)
    """
    key = citation_key or (claim.citation_keys[0] if claim.citation_keys else "")
    rules_triggered: list[str] = []

    # Prepare citation details
    citation_details = {
        "citation_key": key,
        "citation_keys": list(claim.citation_keys),
        "source_location": claim.source_location,
        "reference_title": reference_entry.title if reference_entry else None,
        "reference_doi": reference_entry.doi if reference_entry else None,
        "reference_raw": reference_entry.raw_text if reference_entry else None,
    }

    # Prepare retrieved source metadata
    retrieved_source = {
        "title": getattr(candidate_paper, "title", None),
        "doi": getattr(candidate_paper, "doi", None),
        "source": getattr(candidate_paper, "source", "unknown"),
        "access_tier": getattr(candidate_paper, "access_tier", AccessTier.NOT_FOUND).value if candidate_paper else AccessTier.NOT_FOUND.value,
        "is_retracted": getattr(candidate_paper, "is_retracted", False),
        "is_corrected": getattr(candidate_paper, "is_corrected", False),
    }

    # =======================================================================
    # Situation F: Claim has no citation (MISSING CITATION)
    # =======================================================================
    if not claim.citation_keys or not any(k.strip() for k in claim.citation_keys):
        rules_triggered.append("RULE_MISSING_CITATION")
        return MisleadingCitationResult(
            claim_id=claim.id,
            original_claim=claim.text,
            classification=CitationClassification.MISSING_CITATION,
            citation_details=citation_details,
            retrieved_source=retrieved_source,
            passage="",
            explanation="Claim asserts an empirical or factual proposition but lacks any citation marker.",
            confidence=0.0,
            situation=MisleadingSituation.MISSING_CITATION,
            rules_triggered=rules_triggered,
        )

    # =======================================================================
    # Situation E: Citation points to an incorrect research paper (DOI mismatch)
    # =======================================================================
    if reference_entry and candidate_paper:
        is_doi_mismatch, mismatch_reason = check_doi_mismatch(reference_entry, candidate_paper)
        if is_doi_mismatch:
            rules_triggered.append("RULE_DOI_MISMATCH")
            return MisleadingCitationResult(
                claim_id=claim.id,
                original_claim=claim.text,
                classification=CitationClassification.UNRELATED_CITATION,
                citation_details=citation_details,
                retrieved_source=retrieved_source,
                passage="",
                explanation=(
                    f"Citation points to an incorrect research paper: cited '{reference_entry.title or reference_entry.doi}' "
                    f"but resolved to '{candidate_paper.title}' ({mismatch_reason})."
                ),
                confidence=0.0,
                situation=MisleadingSituation.INCORRECT_PAPER,
                rules_triggered=rules_triggered,
                details={"mismatch_reason": mismatch_reason},
            )

    # Determine source text if empty
    effective_text = source_text.strip()
    is_inaccessible = False
    if not effective_text:
        if candidate_paper:
            if candidate_paper.abstract and len(candidate_paper.abstract.strip()) >= 30:
                effective_text = candidate_paper.abstract.strip()
            elif candidate_paper.access_tier in (AccessTier.INACCESSIBLE, AccessTier.NOT_FOUND, AccessTier.METADATA_ONLY):
                is_inaccessible = True
            elif candidate_paper.title and len(candidate_paper.title.strip()) >= 10:
                effective_text = f"{candidate_paper.title}. {candidate_paper.journal or ''} {candidate_paper.year or ''}."
            else:
                is_inaccessible = True
        else:
            is_inaccessible = True

    # If source is completely inaccessible or not found
    if is_inaccessible or not effective_text or retrieved_source["access_tier"] in (AccessTier.INACCESSIBLE.value, AccessTier.NOT_FOUND.value):
        rules_triggered.append("RULE_INACCESSIBLE_SOURCE")
        return MisleadingCitationResult(
            claim_id=claim.id,
            original_claim=claim.text,
            classification=CitationClassification.NEEDS_REVIEW,
            citation_details=citation_details,
            retrieved_source=retrieved_source,
            passage="",
            explanation="Needs review: cited research paper is inaccessible or could not be retrieved from academic databases.",
            confidence=0.0,
            situation=MisleadingSituation.INACCESSIBLE_OR_UNVERIFIED,
            rules_triggered=rules_triggered,
        )

    # Retrieve top passages from source text
    passages = retrieve_evidence_passages(claim.text, effective_text, top_k=3)
    best_passage = passages[0].text if passages else ""
    retrieval_score = passages[0].final_score if passages else 0.0

    # Compute topic overlap between claim informative words and retrieved source
    overlap = compute_topic_overlap(claim.text, effective_text)

    # =======================================================================
    # Situation A: Citation exists but discusses an unrelated topic
    # =======================================================================
    if overlap < 0.15 or (retrieval_score < 0.12 and overlap < 0.20):
        rules_triggered.append("RULE_UNRELATED_TOPIC")
        return MisleadingCitationResult(
            claim_id=claim.id,
            original_claim=claim.text,
            classification=CitationClassification.UNRELATED_CITATION,
            citation_details=citation_details,
            retrieved_source=retrieved_source,
            passage=best_passage,
            explanation=(
                f"Citation exists but discusses an unrelated topic: topic lexical overlap is {overlap:.1%}. "
                "The source text does not mention or investigate the empirical subject asserted in the claim."
            ),
            confidence=0.0,
            situation=MisleadingSituation.UNRELATED_TOPIC,
            rules_triggered=rules_triggered,
            details={"topic_overlap": round(overlap, 4), "retrieval_score": round(retrieval_score, 4)},
        )

    # Execute deterministic verification checks on best retrieved passage
    polarity_res = polarity_check(claim.text, best_passage) if best_passage else None
    quote_res = quote_check(best_passage, effective_text) if best_passage else None

    # Check for numbers in claim
    claim_numbers = re.findall(r'\b\d+(?:\.\d+)?%?', claim.text)
    num_res = None
    if claim_numbers:
        target_num = claim_numbers[0]
        num_res = number_check(claim.text, best_passage) if best_passage else None

    # Check existing claim slot results if already verified by pipeline
    number_slot_mismatch = any(
        sr.status == "mismatch" for sr in claim.slot_results if any(s.field_type == "number" for s in claim.slots if s.id == sr.slot_id)
    ) if claim.slot_results else False

    # =======================================================================
    # Situation C: Citation reports findings that contradict the claim
    # =======================================================================
    if (polarity_res is not None and not polarity_res.passed) or (claim.verdict and claim.verdict.verdict == VerdictType.CONTRADICTORY and not number_slot_mismatch):
        rules_triggered.append("RULE_CONTRADICTORY_FINDINGS")
        conf = compute_confidence(AccessTier.FULL_TEXT, unverified_slots=0)
        reason_msg = polarity_res.reason if polarity_res else "Empirical findings in cited paper report opposite or contradicting effects"
        return MisleadingCitationResult(
            claim_id=claim.id,
            original_claim=claim.text,
            classification=CitationClassification.CONTRADICTORY_CITATION,
            citation_details=citation_details,
            retrieved_source=retrieved_source,
            passage=best_passage,
            explanation=f"Citation reports empirical findings that contradict the claim: {reason_msg}.",
            confidence=conf,
            situation=MisleadingSituation.CONTRADICTORY_FINDINGS,
            rules_triggered=rules_triggered,
            details={"polarity_check": polarity_res.details if polarity_res else {}},
        )

    # =======================================================================
    # Situation D: Citation contains different numerical values
    # =======================================================================
    if (num_res is not None and not num_res.passed) or number_slot_mismatch:
        rules_triggered.append("RULE_NUMBER_MISMATCH")
        conf = compute_confidence(AccessTier.FULL_TEXT, unverified_slots=1)
        mismatch_detail = num_res.details if num_res else {}
        return MisleadingCitationResult(
            claim_id=claim.id,
            original_claim=claim.text,
            classification=CitationClassification.MISLEADING_CITATION,
            citation_details=citation_details,
            retrieved_source=retrieved_source,
            passage=best_passage,
            explanation=(
                f"Citation contains different numerical values from those asserted: document claims '{', '.join(claim_numbers)}' "
                f"whereas cited passage reports conflicting quantities."
            ),
            confidence=conf,
            situation=MisleadingSituation.NUMBER_MISMATCH,
            rules_triggered=rules_triggered,
            details=mismatch_detail,
        )

    # =======================================================================
    # Situation B: Relevant to topic but does not support specific claim
    # =======================================================================
    # If quote check failed or passage does not contain the specific finding
    finding_stems = (
        "increas", "improv", "reduc", "favor", "benefit", "exhibit", "achiev",
        "reach", "detect", "efficac", "efficien", "yield", "differ", "surviv",
        "superconduct", "drop", "resist", "find", "occur", "demonstrat"
    )
    has_specific_finding = any(stem in best_passage.lower() for stem in finding_stems) if any(
        t in claim.text.lower() for t in finding_stems
    ) else (overlap >= 0.35)

    if not has_specific_finding or (claim.verdict and claim.verdict.verdict == VerdictType.UNSUPPORTED):
        rules_triggered.append("RULE_UNSUPPORTED_SPECIFIC_CLAIM")
        conf = compute_confidence(AccessTier.FULL_TEXT, unverified_slots=1)
        return MisleadingCitationResult(
            claim_id=claim.id,
            original_claim=claim.text,
            classification=CitationClassification.MISLEADING_CITATION,
            citation_details=citation_details,
            retrieved_source=retrieved_source,
            passage=best_passage,
            explanation="Citation discusses the relevant scientific topic but fails to substantiate the specific empirical claim asserted.",
            confidence=conf,
            situation=MisleadingSituation.UNSUPPORTED_SPECIFIC_CLAIM,
            rules_triggered=rules_triggered,
            details={"topic_overlap": round(overlap, 4)},
        )

    # =======================================================================
    # Valid Citation: Verified supporting evidence
    # =======================================================================
    if quote_res is not None and quote_res.passed and (num_res is None or num_res.passed) and (polarity_res is None or polarity_res.passed):
        rules_triggered.append("RULE_VALID_CITATION")
        conf = compute_confidence(AccessTier.FULL_TEXT, unverified_slots=0)
        return MisleadingCitationResult(
            claim_id=claim.id,
            original_claim=claim.text,
            classification=CitationClassification.VALID_CITATION,
            citation_details=citation_details,
            retrieved_source=retrieved_source,
            passage=best_passage,
            explanation="Citation is valid and directly supports the empirical claim with verified verbatim passage in the source.",
            confidence=conf,
            situation=MisleadingSituation.VERIFIED_VALID,
            rules_triggered=rules_triggered,
            details={"quote_verified": True},
        )

    # Fallback to Needs Review
    rules_triggered.append("RULE_NEEDS_REVIEW")
    return MisleadingCitationResult(
        claim_id=claim.id,
        original_claim=claim.text,
        classification=CitationClassification.NEEDS_REVIEW,
        citation_details=citation_details,
        retrieved_source=retrieved_source,
        passage=best_passage,
        explanation="Needs review: citation requires human reviewer inspection to verify supporting evidence.",
        confidence=0.30,
        situation=MisleadingSituation.INACCESSIBLE_OR_UNVERIFIED,
        rules_triggered=rules_triggered,
    )


# ===========================================================================
# Document-Wide Misleading Citation Audit
# ===========================================================================

def audit_document_citations(
    file_path: Union[str, Path],
    resolver: Optional[Any] = None,
) -> MisleadingCitationReport:
    """Extract claims from document, map citations, retrieve papers, and audit for misleading citations.

    Implements the 4-step pipeline:
    1. Extract every empirical claim from uploaded PDF/DOCX.
    2. Map each claim to its corresponding citation.
    3. Retrieve the original research paper.
    4. Compare the claim against actual findings in the retrieved paper.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document file not found: {file_path}")

    from credence.ingest.citations import map_citations
    from credence.ingest.claims import extract_claims
    from credence.ingest.parse import parse_document
    from credence.resolve.sources import UnifiedResolver

    active_resolver = resolver or UnifiedResolver()

    # 1. Extract claims & parsed text
    parsed_doc = parse_document(path)
    mapping = map_citations(
        body_text=parsed_doc.text,
        ref_section_text=parsed_doc.reference_section_text,
        sections=parsed_doc.sections,
    )

    claims: list[Claim] = []
    for sec in parsed_doc.sections:
        if sec.title.lower() not in ("references", "bibliography", "header / metadata"):
            claims.extend(extract_claims(sec.content, section_name=sec.title))

    if not claims:
        claims = extract_claims(parsed_doc.text, section_name="Full Manuscript")

    results: list[MisleadingCitationResult] = []

    valid_cnt = 0
    misleading_cnt = 0
    unrelated_cnt = 0
    contradictory_cnt = 0
    missing_cnt = 0
    review_cnt = 0

    # 2. Map, retrieve, and compare
    for idx, claim in enumerate(claims, 1):
        claim.id = f"claim-{idx}"
        ref_key = claim.citation_keys[0] if claim.citation_keys else ""
        ref_entry = mapping.mapped.get(ref_key)

        # Retrieve paper
        cand_paper = None
        source_text = ""
        if ref_entry:
            match_res = active_resolver.resolve(ref_entry)
            cand_paper = match_res.candidate
            if cand_paper and cand_paper.abstract:
                source_text = cand_paper.abstract
            elif cand_paper and cand_paper.title:
                source_text = f"{cand_paper.title}. {cand_paper.journal or ''} {cand_paper.year or ''}."
            else:
                source_text = f"{ref_entry.title}. {ref_entry.journal or ''} {ref_entry.year or ''}."

        audit_res = audit_citation(
            claim=claim,
            candidate_paper=cand_paper,
            source_text=source_text,
            reference_entry=ref_entry,
            citation_key=ref_key,
        )

        # Attach audit to claim
        claim.citation_classification = audit_res.classification.value
        claim.citation_audit = audit_res.to_dict()
        results.append(audit_res)

        # Count classifications
        if audit_res.classification == CitationClassification.VALID_CITATION:
            valid_cnt += 1
        elif audit_res.classification == CitationClassification.MISLEADING_CITATION:
            misleading_cnt += 1
        elif audit_res.classification == CitationClassification.UNRELATED_CITATION:
            unrelated_cnt += 1
        elif audit_res.classification == CitationClassification.CONTRADICTORY_CITATION:
            contradictory_cnt += 1
        elif audit_res.classification == CitationClassification.MISSING_CITATION:
            missing_cnt += 1
        else:
            review_cnt += 1

    return MisleadingCitationReport(
        document_name=path.name,
        total_claims=len(claims),
        valid_citations=valid_cnt,
        misleading_citations=misleading_cnt,
        unrelated_citations=unrelated_cnt,
        contradictory_citations=contradictory_cnt,
        missing_citations=missing_cnt,
        needs_review_citations=review_cnt,
        results=results,
    )

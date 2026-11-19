"""Verify subpackage: Pure-Python deterministic verification checks, fixed rule verdict, and pipeline."""

from credence.verify.adversarial import AdversarialResult, run_adversarial_pass
from credence.verify.checks import (
    CheckResult,
    hedge_check,
    normalize_text,
    number_check,
    quote_check,
    strip_outer_quotes,
)
from credence.verify.llm import GeminiClient, LLMResponse, llm_client
from credence.verify.pipeline import build_report, verify_claim
from credence.verify.retrieve import RetrievedPassage, retrieve_evidence_passages, segment_passages
from credence.verify.slots import extract_slots
from credence.verify.verdict import (
    RULE_ALL_ABSENT,
    RULE_ALL_MATCH,
    RULE_CONTRADICTORY,
    RULE_DEFAULT_REVIEW,
    RULE_EMPTY_SLOTS,
    RULE_HALLUCINATED_QUOTE,
    RULE_INACCESSIBLE_SOURCE,
    RULE_OUTDATED_CITATION,
    RULE_PARTIAL_MATCH,
    SlotStatus,
    compute_confidence,
    determine_verdict,
)

__all__ = [
    "CheckResult",
    "quote_check",
    "number_check",
    "hedge_check",
    "normalize_text",
    "strip_outer_quotes",
    "SlotStatus",
    "determine_verdict",
    "compute_confidence",
    "extract_slots",
    "RetrievedPassage",
    "segment_passages",
    "retrieve_evidence_passages",
    "GeminiClient",
    "LLMResponse",
    "llm_client",
    "AdversarialResult",
    "run_adversarial_pass",
    "verify_claim",
    "build_report",
    "RULE_HALLUCINATED_QUOTE",
    "RULE_INACCESSIBLE_SOURCE",
    "RULE_EMPTY_SLOTS",
    "RULE_OUTDATED_CITATION",
    "RULE_CONTRADICTORY",
    "RULE_ALL_MATCH",
    "RULE_PARTIAL_MATCH",
    "RULE_ALL_ABSENT",
    "RULE_DEFAULT_REVIEW",
]

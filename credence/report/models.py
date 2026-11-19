"""Core data models and enums for Credence claim verification reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class AccessTier(str, Enum):
    """Academic paper access tier, setting the theoretical ceiling for confidence."""
    FULL_TEXT = "full_text"
    ABSTRACT_ONLY = "abstract_only"
    METADATA_ONLY = "metadata_only"
    INACCESSIBLE = "inaccessible"
    NOT_FOUND = "not_found"

    @property
    def confidence_cap(self) -> float:
        """Maximum confidence allowed under this tier per AGENTS.md rules."""
        caps = {
            AccessTier.FULL_TEXT: 0.9,
            AccessTier.ABSTRACT_ONLY: 0.6,
            AccessTier.METADATA_ONLY: 0.2,
            AccessTier.INACCESSIBLE: 0.0,
            AccessTier.NOT_FOUND: 0.0,
        }
        return caps.get(self, 0.0)

    @classmethod
    def from_str(cls, val: str) -> AccessTier:
        normalized = val.strip().lower().replace(" ", "_").replace("-", "_")
        for member in cls:
            if member.value == normalized:
                return member
        if normalized in ("fulltext", "full"):
            return cls.FULL_TEXT
        if normalized in ("abstract", "abstract_text"):
            return cls.ABSTRACT_ONLY
        if normalized in ("metadata", "title_only"):
            return cls.METADATA_ONLY
        return cls.INACCESSIBLE


class VerdictType(str, Enum):
    """Evidence verdict types matching the fixed rule table."""
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTORY = "contradictory"
    POTENTIALLY_OUTDATED = "potentially outdated"
    NEEDS_REVIEW = "needs review"

    @classmethod
    def from_str(cls, val: str) -> VerdictType:
        """Parse string to VerdictType accepting spaces, underscores, or shorthand."""
        normalized = val.strip().lower().replace("-", " ")
        if normalized in ("supported",):
            return cls.SUPPORTED
        if normalized in ("partially supported", "partially_supported", "partial"):
            return cls.PARTIALLY_SUPPORTED
        if normalized in ("unsupported",):
            return cls.UNSUPPORTED
        if normalized in ("contradictory", "contradiction"):
            return cls.CONTRADICTORY
        if normalized in ("potentially outdated", "potentially_outdated", "outdated"):
            return cls.POTENTIALLY_OUTDATED
        if normalized in ("needs review", "needs_review", "review"):
            return cls.NEEDS_REVIEW
        return cls.NEEDS_REVIEW

    @classmethod
    def _missing_(cls, value: object) -> Optional[VerdictType]:
        if isinstance(value, str):
            return cls.from_str(value)
        return None


@dataclass
class Verdict:
    """Computed evidence verdict for a scientific claim."""
    claim_id: str
    verdict: VerdictType | str
    confidence: float
    explanation: str = ""
    unverified_slots: int = 0
    contradiction_detected: bool = False
    needs_review: bool = True  # Default stance = human review (AGENTS.md)
    rules_triggered: list[str] = field(default_factory=list)
    access_tier: AccessTier = AccessTier.FULL_TEXT

    def __post_init__(self):
        if isinstance(self.verdict, str):
            self.verdict = VerdictType.from_str(self.verdict)
        if isinstance(self.access_tier, str):
            self.access_tier = AccessTier.from_str(self.access_tier)

    @property
    def display_verdict(self) -> str:
        """Human-readable triage verdict string, e.g. 'Partially supported, needs review'."""
        v_str = self.verdict.value if isinstance(self.verdict, Enum) else str(self.verdict)
        if self.needs_review and "review" not in v_str.lower():
            return f"{v_str.capitalize()}, needs review"
        return v_str.capitalize()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if isinstance(self.verdict, Enum):
            data["verdict"] = self.verdict.value
        if isinstance(self.access_tier, Enum):
            data["access_tier"] = self.access_tier.value
        data["display_verdict"] = self.display_verdict
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Verdict:
        verdict = data.get("verdict", VerdictType.NEEDS_REVIEW)
        if isinstance(verdict, str):
            verdict = VerdictType.from_str(verdict)

        tier = data.get("access_tier", AccessTier.FULL_TEXT)
        if isinstance(tier, str):
            tier = AccessTier.from_str(tier)

        return cls(
            claim_id=data.get("claim_id", ""),
            verdict=verdict,
            confidence=float(data.get("confidence", 0.0)),
            explanation=data.get("explanation", ""),
            unverified_slots=int(data.get("unverified_slots", 0)),
            contradiction_detected=bool(data.get("contradiction_detected", False)),
            rules_triggered=list(data.get("rules_triggered", [])),
            access_tier=tier,
        )


@dataclass
class Slot:
    """A specific factual slot or proposition extracted from a claim."""
    id: str
    claim_id: str
    citation_key: str
    field_type: str = "quote"  # e.g., 'quote', 'number', 'finding', 'sample_size'
    expected_value: Optional[str] = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Slot:
        return cls(**data)


@dataclass
class SlotResult:
    """Outcome of verifying a single slot against retrieved evidence."""
    slot_id: str
    quote: str = ""
    quote_verified: bool = False
    quote_span: Optional[tuple[int, int]] = None
    number_match: Optional[bool] = None
    hedge_match: Optional[bool] = None
    status: str = "needs_review"  # 'match', 'mismatch', 'absent', 'needs_review'
    source_doi: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    page_number: Optional[int] = None
    section_name: Optional[str] = None
    paragraph_number: Optional[int] = None
    source_location: Optional[str] = None
    exact_quotation: Optional[str] = None
    claim_text: Optional[str] = None
    evidence_highlight: Optional[str] = None
    access_tier: AccessTier = AccessTier.NOT_FOUND
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if isinstance(self.access_tier, Enum):
            data["access_tier"] = self.access_tier.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlotResult:
        tier = data.get("access_tier", AccessTier.NOT_FOUND)
        if isinstance(tier, str):
            tier = AccessTier.from_str(tier)

        span = data.get("quote_span")
        if span and isinstance(span, list):
            span = tuple(span)

        return cls(
            slot_id=data.get("slot_id", ""),
            quote=data.get("quote", ""),
            quote_verified=bool(data.get("quote_verified", False)),
            quote_span=span,
            number_match=data.get("number_match"),
            hedge_match=data.get("hedge_match"),
            status=data.get("status", "needs_review"),
            source_doi=data.get("source_doi"),
            source_title=data.get("source_title"),
            source_url=data.get("source_url"),
            page_number=data.get("page_number"),
            section_name=data.get("section_name"),
            paragraph_number=data.get("paragraph_number"),
            source_location=data.get("source_location"),
            exact_quotation=data.get("exact_quotation"),
            claim_text=data.get("claim_text"),
            evidence_highlight=data.get("evidence_highlight"),
            access_tier=tier,
            details=data.get("details", {}),
        )


@dataclass
class Claim:
    """Extracted claim from the input document with its associated citation keys."""
    id: str
    text: str
    citation_keys: list[str] = field(default_factory=list)
    source_location: str = ""  # e.g., page 3, section 2.1 or Results, Paragraph 4
    page_number: Optional[int] = None
    section_name: Optional[str] = None
    paragraph_number: Optional[int] = None
    paper_title: Optional[str] = None
    doi: Optional[str] = None
    exact_quotation: Optional[str] = None
    evidence_highlight: Optional[str] = None
    slots: list[Slot] = field(default_factory=list)
    slot_results: list[SlotResult] = field(default_factory=list)
    verdict: Optional[Verdict] = None
    citation_classification: Optional[str] = None
    citation_audit: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "text": self.text,
            "citation_keys": list(self.citation_keys),
            "source_location": self.source_location,
            "page_number": self.page_number,
            "section_name": self.section_name,
            "paragraph_number": self.paragraph_number,
            "paper_title": self.paper_title,
            "doi": self.doi,
            "exact_quotation": self.exact_quotation,
            "evidence_highlight": self.evidence_highlight,
            "slots": [slot.to_dict() for slot in self.slots],
            "slot_results": [res.to_dict() for res in self.slot_results],
            "verdict": self.verdict.to_dict() if self.verdict else None,
            "citation_classification": self.citation_classification,
            "citation_audit": self.citation_audit,
        }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Claim:
        slots = [Slot.from_dict(s) for s in data.get("slots", [])]
        slot_results = [SlotResult.from_dict(r) for r in data.get("slot_results", [])]
        verdict = Verdict.from_dict(data["verdict"]) if data.get("verdict") else None
        return cls(
            id=data.get("id", ""),
            text=data.get("text", ""),
            citation_keys=list(data.get("citation_keys", [])),
            source_location=data.get("source_location", ""),
            page_number=data.get("page_number"),
            section_name=data.get("section_name"),
            paragraph_number=data.get("paragraph_number"),
            paper_title=data.get("paper_title"),
            doi=data.get("doi"),
            exact_quotation=data.get("exact_quotation"),
            evidence_highlight=data.get("evidence_highlight"),
            slots=slots,
            slot_results=slot_results,
            verdict=verdict,
            citation_classification=data.get("citation_classification"),
            citation_audit=data.get("citation_audit"),
        )


@dataclass
class Report:
    """Full triage report for an analyzed document."""
    document_name: str
    claims: list[Claim] = field(default_factory=list)
    access_tier: AccessTier = AccessTier.FULL_TEXT
    overall_confidence: float = 0.0
    summary: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_name": self.document_name,
            "claims": [c.to_dict() for c in self.claims],
            "access_tier": self.access_tier.value if isinstance(self.access_tier, Enum) else self.access_tier,
            "overall_confidence": self.overall_confidence,
            "summary": self.summary,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Report:
        tier = data.get("access_tier", AccessTier.FULL_TEXT)
        if isinstance(tier, str):
            tier = AccessTier.from_str(tier)

        claims = [Claim.from_dict(c) for c in data.get("claims", [])]
        return cls(
            document_name=data.get("document_name", ""),
            claims=claims,
            access_tier=tier,
            overall_confidence=float(data.get("overall_confidence", 0.0)),
            summary=data.get("summary", {}),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )

"""Candidate scoring, threshold evaluation, and discrepancy classification for references.

Rules (AGENTS.md):
- LLM judges MEANING only. Python decides every deterministic fact.
- "Not found in databases" != fabricated. Report what was searched and where.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from credence.resolve.reference import Reference

# Optional rapidfuzz import with robust pure-Python fallback
try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False


@dataclass
class CandidatePaper:
    """Standardized academic paper metadata retrieved from external sources."""
    source: str  # 'crossref', 'openalex', 'semanticscholar', 'unpaywall', 'arxiv', 'pmc'
    title: str
    doi: Optional[str] = None
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    journal: Optional[str] = None
    abstract: Optional[str] = None
    url: Optional[str] = None
    open_access_pdf_url: Optional[str] = None
    is_retracted: bool = False
    is_corrected: bool = False
    retraction_details: dict[str, Any] = field(default_factory=dict)
    correction_details: dict[str, Any] = field(default_factory=dict)
    publication_type: str = "journal-article"
    references: list[dict[str, Any]] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MatchResult:
    """Detailed score and verification outcome between reference and candidate."""
    is_match: bool
    score: float
    classification: str  # 'valid', 'wrong_year', 'fake_doi', 'fake_title', 'not_found'
    title_score: float = 0.0
    author_score: float = 0.0
    year_score: float = 0.0
    doi_score: Optional[float] = None
    discrepancies: list[str] = field(default_factory=list)
    candidate: Optional[CandidatePaper] = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.candidate:
            data["candidate"] = self.candidate.to_dict()
        return data


def normalize_title(title: str) -> str:
    """Normalize paper title for fuzzy token matching."""
    if not title:
        return ""
    t = unicodedata.normalize("NFKC", title).lower()
    # Remove punctuation
    t = re.sub(r'[^\w\s]', ' ', t)
    # Collapse whitespace
    return re.sub(r'\s+', ' ', t).strip()


def compute_title_similarity(title1: str, title2: str) -> float:
    """Compute title similarity in [0.0, 1.0]. Uses rapidfuzz token_set_ratio if present."""
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)
    if not norm1 or not norm2:
        return 0.0

    if norm1 == norm2:
        return 1.0

    if HAS_RAPIDFUZZ:
        score = fuzz.token_set_ratio(norm1, norm2) / 100.0
        return round(score, 4)

    # Pure Python token Jaccard & overlap fallback
    tokens1 = set(norm1.split())
    tokens2 = set(norm2.split())
    if not tokens1 or not tokens2:
        return 0.0

    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    jaccard = intersection / union if union else 0.0
    overlap = intersection / min(len(tokens1), len(tokens2))
    score = 0.6 * overlap + 0.4 * jaccard
    return round(score, 4)


def extract_surnames(author_names: list[str]) -> set[str]:
    """Extract lowercased author surnames from list of author strings."""
    surnames = set()
    for name in author_names:
        clean = re.sub(r'[^\w\s]', '', name).strip().lower()
        parts = clean.split()
        if parts:
            # Usually last token is surname, or first token if "Surname, Forename"
            if "," in name:
                surnames.add(name.split(",")[0].strip().lower())
            else:
                surnames.add(parts[-1])
    return surnames


def compute_author_similarity(authors1: list[str], authors2: list[str]) -> float:
    """Compute surname overlap between two author lists."""
    if not authors1 or not authors2:
        return 0.5  # Neutral when metadata missing

    surnames1 = extract_surnames(authors1)
    surnames2 = extract_surnames(authors2)

    if not surnames1 or not surnames2:
        return 0.5

    common = surnames1 & surnames2
    if common:
        return round(len(common) / min(len(surnames1), len(surnames2)), 4)
    return 0.0


def compute_year_similarity(year1: Optional[int], year2: Optional[int]) -> tuple[float, Optional[str]]:
    """Compare publication years with tolerance for publication lag."""
    if year1 is None or year2 is None:
        return 0.5, None

    diff = abs(year1 - year2)
    if diff == 0:
        return 1.0, None
    if diff == 1:
        return 0.8, None  # Preprint or online-first publication lag
    return 0.0, f"Year mismatch: reference cited {year1} but candidate published in {year2} (diff: {diff} years)"


# Matching thresholds
VALID_MATCH_THRESHOLD = 0.80
TITLE_MISMATCH_THRESHOLD = 0.45


def score_candidate(
    reference: Reference,
    candidate: Optional[CandidatePaper],
    doi_lookup_failed: bool = False,
) -> MatchResult:
    """Score a candidate paper against a reference and classify the verification status.

    Classifies into:
      - 'valid': High confidence match on title/DOI/year
      - 'wrong_year': Title and/or DOI matches, but publication year differs by > 1 year
      - 'fake_doi': Reference provided a DOI that does not resolve or conflicts with real record
      - 'fake_title': Reference title has negligible overlap with actual paper / literature
      - 'not_found': Reference could not be located in academic databases
    """
    discrepancies: list[str] = []

    # Case 1: Candidate is None (no record found)
    if candidate is None:
        if reference.doi and doi_lookup_failed:
            discrepancies.append(f"DOI '{reference.doi}' does not exist in Crossref/OpenAlex/SemanticScholar.")
            return MatchResult(
                is_match=False,
                score=0.0,
                classification="fake_doi",
                discrepancies=discrepancies,
                details={"reason": "doi_not_found_in_databases"}
            )
        return MatchResult(
            is_match=False,
            score=0.0,
            classification="not_found",
            discrepancies=["No candidate records found matching query in databases."],
            details={"reason": "no_results_returned"}
        )

    # Compute component scores
    title_score = compute_title_similarity(reference.title, candidate.title)
    author_score = compute_author_similarity(reference.authors, candidate.authors)
    year_score, year_err = compute_year_similarity(reference.year, candidate.year)

    if year_err:
        discrepancies.append(year_err)

    # DOI comparison
    doi_score: Optional[float] = None
    if reference.doi and candidate.doi:
        norm_ref_doi = reference.doi.lower().strip()
        norm_cand_doi = candidate.doi.lower().strip()
        if norm_ref_doi == norm_cand_doi:
            doi_score = 1.0
        else:
            doi_score = 0.0
            discrepancies.append(f"DOI mismatch: reference cited '{norm_ref_doi}' but candidate is '{norm_cand_doi}'")
    elif reference.doi and not candidate.doi:
        doi_score = 0.5
    else:
        doi_score = None

    # Classification logic:

    # 1. Fake DOI: Reference has a DOI, but candidate DOI exists and differs, or title is wildly different
    if reference.doi and candidate.doi and doi_score == 0.0 and title_score < TITLE_MISMATCH_THRESHOLD:
        discrepancies.append(f"Fake or mismatched DOI: '{reference.doi}' does not match candidate DOI '{candidate.doi}'")
        return MatchResult(
            is_match=False,
            score=round(0.3 * title_score, 4),
            classification="fake_doi",
            title_score=title_score,
            author_score=author_score,
            year_score=year_score,
            doi_score=doi_score,
            discrepancies=discrepancies,
            candidate=candidate,
        )

    # 2. Fake Title / DOI Mismatch: Extremely low title similarity (< 0.45)
    if title_score < TITLE_MISMATCH_THRESHOLD:
        if reference.doi:
            mismatch_msg = (
                f"DOI mismatch: cited DOI '{reference.doi}' resolves to '{candidate.title}' "
                f"which does not match cited title '{reference.title}' (similarity {title_score:.2f})"
            )
            doi_mismatch_flag = True
        else:
            mismatch_msg = (
                f"Title mismatch: reference title '{reference.title}' does not match candidate title '{candidate.title}' (similarity {title_score:.2f})"
            )
            doi_mismatch_flag = False

        discrepancies.append(mismatch_msg)
        return MatchResult(
            is_match=False,
            score=round(title_score, 4),
            classification="fake_title",
            title_score=title_score,
            author_score=author_score,
            year_score=year_score,
            doi_score=doi_score,
            discrepancies=discrepancies,
            candidate=candidate,
            details={"doi_mismatch": doi_mismatch_flag, "reason": mismatch_msg},
        )

    # 3. Wrong Year: Title matches well (>= 0.70) or DOI matches, but year differs significantly
    if year_err is not None and (title_score >= 0.70 or doi_score == 1.0):
        return MatchResult(
            is_match=False,
            score=round(0.5 * title_score, 4),
            classification="wrong_year",
            title_score=title_score,
            author_score=author_score,
            year_score=year_score,
            doi_score=doi_score,
            discrepancies=discrepancies,
            candidate=candidate,
        )

    # 4. Valid Match: High title similarity and year within tolerance
    if doi_score == 1.0 and year_score >= 0.8:
        overall_score = round(0.95 + 0.05 * title_score, 4)
    elif doi_score == 1.0:
        overall_score = round(0.85 + 0.15 * title_score, 4)
    else:
        overall_score = round(0.60 * title_score + 0.25 * author_score + 0.15 * year_score, 4)

    is_match = overall_score >= VALID_MATCH_THRESHOLD

    classification = "valid" if is_match else "unmatched"
    if not is_match:
        discrepancies.append(f"Overall match score {overall_score:.2f} below threshold {VALID_MATCH_THRESHOLD:.2f}")

    # Note retractions and corrections in discrepancies if matched
    if candidate.is_retracted:
        discrepancies.append(f"Retraction notice: candidate paper has been retracted (source: {candidate.source}).")
    if candidate.is_corrected:
        discrepancies.append(f"Correction notice: candidate paper has a formal erratum/correction (source: {candidate.source}).")

    return MatchResult(
        is_match=is_match,
        score=overall_score,
        classification=classification,
        title_score=title_score,
        author_score=author_score,
        year_score=year_score,
        doi_score=doi_score,
        discrepancies=discrepancies,
        candidate=candidate,
        details={
            "is_retracted": candidate.is_retracted,
            "is_corrected": candidate.is_corrected,
            "retraction_details": candidate.retraction_details,
            "correction_details": candidate.correction_details,
            "publication_type": candidate.publication_type,
        },
    )


def check_doi_mismatch(
    reference: Reference,
    candidate: Optional[CandidatePaper],
    threshold: float = TITLE_MISMATCH_THRESHOLD,
) -> tuple[bool, Optional[str]]:
    """Determine whether a cited DOI resolved to a paper with a mismatched title.

    Returns:
        (is_mismatch, reason_string)
    """
    if not reference or not reference.doi or not candidate or not candidate.title:
        return False, None

    sim = compute_title_similarity(reference.title, candidate.title)
    if sim < threshold:
        return True, (
            f"DOI mismatch: cited DOI '{reference.doi}' resolves to '{candidate.title}' "
            f"which differs from cited title '{reference.title}' (similarity: {sim:.2f})"
        )
    return False, None

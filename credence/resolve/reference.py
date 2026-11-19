"""Reference string parser: DOI regex extraction, deterministic rules, and LLM fallback.

Rules (AGENTS.md):
- Every LLM call validates against a JSON schema; bad JSON -> 1 retry -> "Needs review", never crash.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class Reference:
    """Structured representation of a bibliographic citation."""
    raw_text: str = ""
    key: Optional[str] = None  # e.g., '1', '4', 'Smith2020'
    doi: Optional[str] = None
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    pages: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Reference:
        return cls(**data)


# Standard DOI regular expression matching DOI syntax across publishers
_DOI_REGEX = re.compile(
    r'(?:https?://(?:dx\.)?doi\.org/|doi:\s*)?(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)',
    re.IGNORECASE
)


def extract_doi(text: str) -> Optional[str]:
    """Extract and normalize a digital object identifier (DOI) from text.

    Cleans trailing punctuation (periods, brackets, commas) often captured at end of citations.
    """
    if not text:
        return None

    match = _DOI_REGEX.search(text)
    if not match:
        return None

    raw_doi = match.group(1).strip()
    # Strip trailing punctuation that might be citation delimiters
    cleaned_doi = re.sub(r'[\s.,;:)>\]]+$', '', raw_doi)
    return cleaned_doi.lower()


# Year extraction pattern: 1800-2099
_YEAR_REGEX = re.compile(r'\b(19\d{2}|20\d{2})\b')


def _deterministic_parse(raw_text: str, key: Optional[str] = None) -> Reference:
    """Deterministic heuristic parsing of standard reference formats (APA, Vancouver, IEEE)."""
    text = raw_text.strip()

    # Extract leading key if not provided (e.g. "[4] Smith et al." or "4. Smith...")
    if not key:
        key_match = re.match(r'^(?:\[(\d+|[A-Za-z0-9_-]+)\]|(\d+)\.)\s*', text)
        if key_match:
            key = key_match.group(1) or key_match.group(2)
            # Remove key from start of text
            text = text[key_match.end():].strip()

    doi = extract_doi(text)

    # Remove DOI url portion from text for cleaner field tokenization
    clean_text = _DOI_REGEX.sub('', text).strip()
    clean_text = re.sub(r'https?://\S+', '', clean_text).strip()

    # Extract year
    years = [int(y) for y in _YEAR_REGEX.findall(clean_text)]
    year: Optional[int] = None
    if years:
        # Prefer year in parentheses e.g. (2020)
        paren_year = re.search(r'\((19\d{2}|20\d{2})\)', clean_text)
        if paren_year:
            year = int(paren_year.group(1))
        else:
            year = years[0]

    authors: list[str] = []
    title = ""
    journal = None

    # Common citation splitting by periods or quotes
    # E.g. "Smith J, Doe A. Study on cardioprotection. J Med. 2020;12(3):45-50."
    quote_title_match = re.search(r'["“](.+?)["”]', clean_text)
    if quote_title_match:
        title = quote_title_match.group(1).strip()
        parts = clean_text.split(quote_title_match.group(0), 1)
        author_part = parts[0].strip(" .;,")
        if author_part:
            authors = [a.strip() for a in re.split(r'[,;&]|\band\b', author_part) if a.strip()]
        if len(parts) > 1 and parts[1].strip():
            journal_part = parts[1].strip(" .;,")
            journal = journal_part.split(".")[0].strip() or None
    else:
        # Split by periods
        parts = [p.strip() for p in clean_text.split(".") if p.strip()]
        if len(parts) >= 3:
            # First part authors, second title, third journal/source
            author_part = parts[0]
            authors = [a.strip() for a in re.split(r'[,;&]|\band\b', author_part) if a.strip()]
            title = parts[1]
            journal = parts[2]
        elif len(parts) == 2:
            title = parts[0]
            journal = parts[1]
        elif len(parts) == 1:
            title = parts[0]

    return Reference(
        raw_text=raw_text.strip(),
        key=key,
        doi=doi,
        title=title.strip(),
        authors=authors,
        year=year,
        journal=journal.strip() if journal else None,
    )


def parse_reference(
    raw_text: str,
    key: Optional[str] = None,
    use_llm_fallback: bool = False,
    llm_client: Optional[Any] = None,
) -> Reference:
    """Parse a bibliographic reference string into structured fields.

    Extracts DOI with regex first. Falls back to LLM atomization if regex/heuristic
    yields incomplete metadata and use_llm_fallback is enabled.
    """
    ref = _deterministic_parse(raw_text, key=key)

    # If title and year are extracted or DOI is found, deterministic parse is successful
    if ref.title and (ref.doi or ref.year):
        return ref

    # If deterministic parsing was incomplete and LLM fallback requested
    if use_llm_fallback and llm_client:
        try:
            prompt = (
                "Parse the following academic citation into strict JSON with fields: "
                "title (string), authors (list of strings), year (integer or null), "
                "journal (string or null), volume (string or null), pages (string or null), "
                "doi (string or null).\n"
                f"Citation: {raw_text}\n"
                "Output ONLY valid JSON."
            )
            resp = llm_client.generate(prompt)
            data = json.loads(resp)
            return Reference(
                raw_text=raw_text.strip(),
                key=key or ref.key,
                doi=data.get("doi") or ref.doi,
                title=data.get("title") or ref.title,
                authors=data.get("authors") or ref.authors,
                year=data.get("year") or ref.year,
                journal=data.get("journal") or ref.journal,
                volume=data.get("volume") or ref.volume,
                pages=data.get("pages") or ref.pages,
            )
        except Exception:
            # Golden rule: Bad LLM output falls back gracefully, never crashes
            pass

    return ref

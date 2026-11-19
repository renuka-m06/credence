"""In-text citation parser and reference-list mapper.

Extracts numeric citations ([n], [1-3], [1, 2]) and author-year citations ((Smith et al., 2020)).
Maps in-text citations to reference entries and flags:
- missing: cited in text but absent from bibliography
- uncited: present in bibliography but never cited in text
- ambiguous: author-year marker matching multiple bibliography entries
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from credence.resolve.reference import Reference, parse_reference


@dataclass
class InTextCitation:
    """An in-text citation marker found in the manuscript."""
    raw_marker: str  # e.g., '[4]', '[1-3]', '(Vaswani et al., 2017)'
    keys: list[str]  # e.g., ['4'], ['1', '2', '3'], ['Vaswani2017']
    context_sentence: str
    page_number: int = 1
    section_name: str = ""


@dataclass
class CitationMappingResult:
    """Mapping of in-text citations to reference-list entries with diagnostic flags."""
    citations: list[InTextCitation] = field(default_factory=list)
    references: dict[str, Reference] = field(default_factory=dict)  # key -> Reference
    mapped: dict[str, Reference] = field(default_factory=dict)      # in-text key -> Reference
    missing: list[str] = field(default_factory=list)               # cited but not in bibliography
    uncited: list[str] = field(default_factory=list)               # in bibliography but never cited
    ambiguous: list[str] = field(default_factory=list)             # matched multiple entries

    def to_dict(self) -> dict[str, Any]:
        return {
            "citations": [asdict(c) for c in self.citations],
            "references": {k: v.to_dict() for k, v in self.references.items()},
            "mapped_keys": list(self.mapped.keys()),
            "missing": self.missing,
            "uncited": self.uncited,
            "ambiguous": self.ambiguous,
        }


# Pattern for numeric in-text citations: [1], [1, 2], [1-4], [1–3]
_NUMERIC_CITATION_REGEX = re.compile(r'\[(\d+(?:\s*[-–,]\s*\d+)*)\]')

# Pattern for author-year in-text citations: (Smith et al., 2020), (Vaswani, 2017; Devlin, 2019)
_AUTHOR_YEAR_CITATION_REGEX = re.compile(
    r'\(([A-Z][a-zA-Z]+(?:\s+et\s+al\.?)?(?:\s+(?:and|&)\s+[A-Z][a-zA-Z]+)?,\s*(?:19|20)\d{2}[a-z]?'
    r'(?:;\s*[A-Z][a-zA-Z]+(?:\s+et\s+al\.?)?(?:\s+(?:and|&)\s+[A-Z][a-zA-Z]+)?,\s*(?:19|20)\d{2}[a-z]?)*)\)'
)


def expand_numeric_range(token_str: str) -> list[str]:
    """Expand citation expressions like '1-3' or '1, 4, 7-9' into individual string keys."""
    keys: list[str] = []
    parts = re.split(r'[,;]', token_str)
    for part in parts:
        part = part.strip()
        range_match = re.match(r'^(\d+)\s*[-–]\s*(\d+)$', part)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            if start <= end and (end - start) < 50:  # Sanity bound
                for num in range(start, end + 1):
                    keys.append(str(num))
            else:
                keys.append(part)
        elif part.isdigit():
            keys.append(part)
    return keys


def parse_reference_list(ref_section_text: str) -> dict[str, Reference]:
    """Parse reference entries from the bibliography text into a key-indexed dict."""
    entries: dict[str, Reference] = {}
    if not ref_section_text or not ref_section_text.strip():
        return entries

    # Pattern for numeric bibliography item start: e.g. "[1]", "1.", "1 "
    item_pattern = re.compile(r'(?:^|\n)(?:\[(\d+)\]|(\d+)\.)\s*', re.MULTILINE)
    splits = list(item_pattern.finditer(ref_section_text))

    if splits:
        for idx, match in enumerate(splits):
            key = match.group(1) or match.group(2)
            start_pos = match.end()
            end_pos = splits[idx + 1].start() if idx + 1 < len(splits) else len(ref_section_text)
            entry_text = ref_section_text[start_pos:end_pos].strip()
            if entry_text:
                ref = parse_reference(entry_text, key=key)
                entries[key] = ref
    else:
        # Paragraph or line based (Author-Year style)
        lines = [line.strip() for line in ref_section_text.split("\n\n") if line.strip()]
        if len(lines) <= 1:
            lines = [line.strip() for line in ref_section_text.split("\n") if line.strip()]

        for idx, line in enumerate(lines, start=1):
            ref = parse_reference(line, key=str(idx))
            # Generate author-year key if possible
            if ref.authors and ref.year:
                first_surname = ref.authors[0].split(",")[0].split()[-1]
                key = f"{first_surname}{ref.year}"
            else:
                key = str(idx)
            ref.key = key
            entries[key] = ref

    return entries


def extract_in_text_citations(body_text: str, page_number: int = 1, section_name: str = "") -> list[InTextCitation]:
    """Extract numeric and author-year in-text citation occurrences with their sentence context."""
    citations: list[InTextCitation] = []
    sentences = re.split(r'(?<=[.!?])\s+', body_text)

    for sentence in sentences:
        clean_sentence = sentence.strip()
        if not clean_sentence:
            continue

        # 1. Numeric matches e.g. [4], [1, 2], [1-3]
        for match in _NUMERIC_CITATION_REGEX.finditer(clean_sentence):
            raw = match.group(0)
            inner = match.group(1)
            keys = expand_numeric_range(inner)
            citations.append(InTextCitation(
                raw_marker=raw,
                keys=keys,
                context_sentence=clean_sentence,
                page_number=page_number,
                section_name=section_name,
            ))

        # 2. Author-year matches e.g. (Vaswani et al., 2017)
        for match in _AUTHOR_YEAR_CITATION_REGEX.finditer(clean_sentence):
            raw = match.group(0)
            inner = match.group(1)
            # Split multiple citations separated by semicolons
            sub_cites = [c.strip() for c in inner.split(";")]
            keys = []
            for sc in sub_cites:
                m = re.match(r'([A-Z][a-zA-Z]+)(?:\s+et\s+al\.?)?.*?,\s*((?:19|20)\d{2})', sc)
                if m:
                    keys.append(f"{m.group(1)}{m.group(2)}")
                else:
                    keys.append(sc)

            citations.append(InTextCitation(
                raw_marker=raw,
                keys=keys,
                context_sentence=clean_sentence,
                page_number=page_number,
                section_name=section_name,
            ))

    return citations


def map_citations(
    body_text: str,
    ref_section_text: str,
    sections: Optional[list[Any]] = None,
) -> CitationMappingResult:
    """Extract in-text citations, parse references, map them, and flag missing/uncited entries."""
    references = parse_reference_list(ref_section_text)

    in_text_citations: list[InTextCitation] = []
    if sections:
        for sec in sections:
            # Skip references section when scanning for in-text citations
            if getattr(sec, "title", "").lower() in ("references", "bibliography"):
                continue
            sec_text = getattr(sec, "content", "")
            page_start = getattr(sec, "page_start", 1)
            in_text_citations.extend(
                extract_in_text_citations(sec_text, page_number=page_start, section_name=getattr(sec, "title", ""))
            )
    else:
        in_text_citations = extract_in_text_citations(body_text)

    # Collect all cited keys
    all_cited_keys: set[str] = set()
    for cite in in_text_citations:
        all_cited_keys.update(cite.keys)

    mapped: dict[str, Reference] = {}
    missing: list[str] = []
    ambiguous: list[str] = []

    for k in sorted(all_cited_keys):
        if k in references:
            mapped[k] = references[k]
        else:
            # Check for partial author-year matching if numeric direct key not found
            candidate_matches = [ref for key, ref in references.items() if k.lower() in key.lower()]
            if len(candidate_matches) == 1:
                mapped[k] = candidate_matches[0]
            elif len(candidate_matches) > 1:
                ambiguous.append(k)
            else:
                missing.append(k)

    # Uncited bibliography entries: in bibliography but never cited in body text
    uncited = [k for k in references.keys() if k not in mapped]

    return CitationMappingResult(
        citations=in_text_citations,
        references=references,
        mapped=mapped,
        missing=sorted(missing),
        uncited=sorted(uncited),
        ambiguous=sorted(ambiguous),
    )

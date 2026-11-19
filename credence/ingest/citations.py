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
    missing_details: list[dict[str, Any]] = field(default_factory=list)
    uncited_details: list[dict[str, Any]] = field(default_factory=list)
    ambiguous_details: list[dict[str, Any]] = field(default_factory=list)
    incomplete_mappings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "citations": [asdict(c) for c in self.citations],
            "references": {k: v.to_dict() for k, v in self.references.items()},
            "mapped_keys": list(self.mapped.keys()),
            "missing": self.missing,
            "uncited": self.uncited,
            "ambiguous": self.ambiguous,
            "missing_details": self.missing_details,
            "uncited_details": self.uncited_details,
            "ambiguous_details": self.ambiguous_details,
            "incomplete_mappings": self.incomplete_mappings,
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
    body_text: Union[str, list[Any]],
    ref_section_text: Union[str, list[Reference], dict[str, Reference]],
    sections: Optional[list[Any]] = None,
) -> CitationMappingResult:
    """Extract in-text citations, parse references, map them, and flag missing/uncited entries."""
    if isinstance(ref_section_text, dict):
        references = dict(ref_section_text)
    elif isinstance(ref_section_text, list):
        references = {getattr(r, "key", str(idx + 1)): r for idx, r in enumerate(ref_section_text)}
    else:
        references = parse_reference_list(str(ref_section_text or ""))

    in_text_citations: list[InTextCitation] = []
    if isinstance(body_text, list):
        for item in body_text:
            s_item = str(item).strip()
            in_text_citations.append(InTextCitation(
                raw_marker=f"[{s_item}]" if not s_item.startswith("[") else s_item,
                keys=[s_item.strip("[]()")],
                context_sentence=f"In-text citation for marker {s_item}",
                page_number=1,
                section_name="Results",
            ))
    elif sections:
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
        in_text_citations = extract_in_text_citations(str(body_text or ""))

    # Collect all cited keys
    all_cited_keys: set[str] = set()
    for cite in in_text_citations:
        all_cited_keys.update(cite.keys)

    mapped: dict[str, Reference] = {}
    missing: list[str] = []
    ambiguous: list[str] = []
    missing_details: list[dict[str, Any]] = []
    ambiguous_details: list[dict[str, Any]] = []

    for k in sorted(all_cited_keys):
        if k in references:
            mapped[k] = references[k]
        else:
            # Check for author-year or normalized matching
            k_clean = k.strip("[]()")
            k_norm = re.sub(r'[^a-zA-Z0-9]', '', k_clean).lower()
            candidate_matches = []
            for key, ref in references.items():
                ref_key_norm = re.sub(r'[^a-zA-Z0-9]', '', key).lower()
                if (k_clean.lower() in key.lower()) or (k_norm and k_norm in ref_key_norm):
                    candidate_matches.append(ref)
                elif getattr(ref, "authors", None):
                    author_surname = k_clean.split(",")[0].strip().lower()
                    if any(author_surname in a.lower() for a in ref.authors):
                        m_yr = re.search(r'\b(19\d{2}|20\d{2})\b', k_clean)
                        if m_yr:
                            if ref.year and str(ref.year) == m_yr.group(1):
                                candidate_matches.append(ref)
                        else:
                            candidate_matches.append(ref)

            # Find in-text citation occurrence for contextual traceability
            matching_cite = next((c for c in in_text_citations if k in c.keys), None)
            pg = matching_cite.page_number if matching_cite else 1
            sec = matching_cite.section_name if matching_cite else "Body"
            ctx = matching_cite.context_sentence if matching_cite else ""

            if len(candidate_matches) == 1:
                mapped[k] = candidate_matches[0]
            elif len(candidate_matches) > 1:
                ambiguous.append(k)
                ambiguous_details.append({
                    "marker": k,
                    "page_number": pg,
                    "section_name": sec,
                    "source_location": f"{sec}, page {pg}" if pg else sec,
                    "context_sentence": ctx,
                    "candidate_titles": [r.title for r in candidate_matches],
                    "reason": f"Citation marker '{k}' is ambiguous; it matches {len(candidate_matches)} entries in the reference list: {', '.join(r.title[:40] for r in candidate_matches)}.",
                    "recommended_action": f"Disambiguate citation marker '{k}' by adding distinctive year suffixes (e.g. {k}a, {k}b) or unique numbering.",
                })
            else:
                missing.append(k)
                missing_details.append({
                    "citation_key": k,
                    "page_number": pg,
                    "section_name": sec,
                    "source_location": f"{sec}, page {pg}" if pg else sec,
                    "context_sentence": ctx,
                    "reason": f"In-text citation [{k}] appears in section '{sec}' (page {pg}) but is missing from the reference list.",
                    "recommended_action": f"Add full bibliographic entry for reference [{k}] in the bibliography section.",
                })

    # Uncited bibliography entries: in bibliography but never cited in body text
    uncited = [k for k in references.keys() if k not in mapped]
    uncited_details: list[dict[str, Any]] = []
    for uk in sorted(uncited):
        ref_obj = references.get(uk)
        ref_title = ref_obj.title if ref_obj and ref_obj.title else f"Reference entry [{uk}]"
        uncited_details.append({
            "citation_key": uk,
            "title": ref_title,
            "reason": f"Reference [{uk}] ('{ref_title[:60]}...') is present in the bibliography but never cited anywhere in the document.",
            "recommended_action": f"Insert an in-text citation for reference [{uk}] at the relevant empirical finding or remove the unused entry.",
        })

    return CitationMappingResult(
        citations=in_text_citations,
        references=references,
        mapped=mapped,
        missing=sorted(missing),
        uncited=sorted(uncited),
        ambiguous=sorted(ambiguous),
        missing_details=missing_details,
        uncited_details=uncited_details,
        ambiguous_details=ambiguous_details,
    )


def audit_missing_citations(
    mapping: CitationMappingResult,
    claims: list[Any],
    body_text: str = "",
    sections: Optional[list[Any]] = None,
) -> list[MissingCitationWarning]:
    """Audit missing citations, uncited claims, incomplete mappings, and unused bibliography entries.

    Covers all 5 missing citation detection dimensions:
    1. Empirical claims without associated citations (Requirement 1 & 7)
    2. Claims with incomplete citation mapping (Requirement 2)
    3. Citations mentioned in text but missing from reference list (Requirement 3)
    4. References present in bibliography but never cited in document (Requirement 4)
    5. Ambiguous citation mappings (Requirement 5)
    """
    from credence.report.models import MissingCitationWarning

    warnings: list[MissingCitationWarning] = []

    # 1. Identify empirical claims that do not have associated citations (Requirement 1, 7)
    for cl in claims:
        keys = getattr(cl, "citation_keys", [])
        if not keys or len(keys) == 0:
            warning = MissingCitationWarning(
                warning_type="uncited_claim",
                claim_id=getattr(cl, "id", ""),
                claim_text=getattr(cl, "text", ""),
                citation_marker=None,
                page_number=getattr(cl, "page_number", None),
                section_name=getattr(cl, "section_name", "Results"),
                source_location=getattr(cl, "source_location", ""),
                reason="Empirical claim asserted without any supporting in-text citation marker.",
                recommended_action="Provide a peer-reviewed citation supporting this assertion or qualify as an original author hypothesis.",
            )
            warnings.append(warning)
            if hasattr(cl, "has_missing_citation"):
                cl.has_missing_citation = True
            if hasattr(cl, "missing_citation_reason"):
                cl.missing_citation_reason = warning.reason
            if hasattr(cl, "recommended_action"):
                cl.recommended_action = warning.recommended_action
            if hasattr(cl, "citation_classification") and not cl.citation_classification:
                cl.citation_classification = "MISSING CITATION"

    # 2. Detect claims with incomplete citation mapping (Requirement 2)
    for cl in claims:
        keys = getattr(cl, "citation_keys", [])
        if keys:
            unmapped = [k for k in keys if k not in mapping.mapped]
            if unmapped:
                warning = MissingCitationWarning(
                    warning_type="incomplete_mapping",
                    claim_id=getattr(cl, "id", ""),
                    claim_text=getattr(cl, "text", ""),
                    citation_marker=", ".join(f"[{k}]" for k in keys),
                    page_number=getattr(cl, "page_number", None),
                    section_name=getattr(cl, "section_name", "Results"),
                    source_location=getattr(cl, "source_location", ""),
                    reason=f"Incomplete citation mapping: citation key(s) {', '.join(f'[{u}]' for u in unmapped)} could not be resolved in the reference list.",
                    recommended_action=f"Verify reference list numbering and add missing bibliography entries for {', '.join(f'[{u}]' for u in unmapped)}.",
                    details={"unmapped_keys": unmapped},
                )
                warnings.append(warning)
                if hasattr(cl, "has_missing_citation"):
                    cl.has_missing_citation = True
                if hasattr(cl, "missing_citation_reason"):
                    cl.missing_citation_reason = warning.reason
                if hasattr(cl, "recommended_action"):
                    cl.recommended_action = warning.recommended_action
            else:
                # Check if mapped reference lacks crucial bibliographic details (incomplete reference entry)
                for k in keys:
                    ref = mapping.mapped.get(k)
                    if ref and (not ref.title or ref.title.strip() == "" or (not ref.authors and not ref.year)):
                        warning = MissingCitationWarning(
                            warning_type="incomplete_mapping",
                            claim_id=getattr(cl, "id", ""),
                            claim_text=getattr(cl, "text", ""),
                            citation_marker=f"[{k}]",
                            page_number=getattr(cl, "page_number", None),
                            section_name=getattr(cl, "section_name", "Results"),
                            source_location=getattr(cl, "source_location", ""),
                            reason=f"Bibliography entry [{k}] has incomplete bibliographic metadata (missing title or authors).",
                            recommended_action=f"Update reference [{k}] in bibliography with complete title, authors, and publication details.",
                            details={"incomplete_key": k},
                        )
                        warnings.append(warning)
                        if hasattr(cl, "has_missing_citation"):
                            cl.has_missing_citation = True
                        if hasattr(cl, "missing_citation_reason"):
                            cl.missing_citation_reason = warning.reason
                        if hasattr(cl, "recommended_action"):
                            cl.recommended_action = warning.recommended_action

    # 3. Detect citations mentioned in text but missing from reference list (Requirement 3)
    for missing_item in mapping.missing_details:
        raw_key = str(missing_item.get("citation_key", "")).strip("[]()")
        warning = MissingCitationWarning(
            warning_type="missing_reference",
            citation_marker=raw_key,
            claim_text=missing_item.get("context_sentence", ""),
            page_number=missing_item.get("page_number"),
            section_name=missing_item.get("section_name", "Manuscript"),
            source_location=missing_item.get("source_location", ""),
            reason=missing_item.get("reason", f"Citation [{raw_key}] appears in text but is absent from bibliography."),
            recommended_action=missing_item.get("recommended_action", f"Add complete reference [{raw_key}] to bibliography."),
            details=missing_item,
        )
        warnings.append(warning)

    # 4. Detect references present in bibliography but never cited in document (Requirement 4)
    for uncited_item in mapping.uncited_details:
        raw_key = str(uncited_item.get("citation_key", "")).strip("[]()")
        warning = MissingCitationWarning(
            warning_type="uncited_reference",
            citation_marker=raw_key,
            claim_text=uncited_item.get("title", ""),
            page_number=None,
            section_name="References",
            source_location="References",
            reason=uncited_item.get("reason", f"Reference [{raw_key}] is present in bibliography but never cited."),
            recommended_action=uncited_item.get("recommended_action", f"Cite [{raw_key}] at relevant empirical finding or remove from bibliography."),
            details=uncited_item,
        )
        warnings.append(warning)

    # 5. Identify ambiguous citation mappings (Requirement 5)
    for amb_item in mapping.ambiguous_details:
        raw_marker = str(amb_item.get("marker", "")).strip("[]()")
        warning = MissingCitationWarning(
            warning_type="ambiguous_citation",
            citation_marker=raw_marker,
            claim_text=amb_item.get("context_sentence", ""),
            page_number=amb_item.get("page_number"),
            section_name=amb_item.get("section_name", "Manuscript"),
            source_location=amb_item.get("source_location", ""),
            reason=amb_item.get("reason", f"Citation marker '{raw_marker}' matches multiple bibliography entries."),
            recommended_action=amb_item.get("recommended_action", f"Disambiguate citation '{raw_marker}' with distinctive suffix or unique numbering."),
            details=amb_item,
        )
        warnings.append(warning)

    return warnings

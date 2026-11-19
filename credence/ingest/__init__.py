"""Ingest subpackage: Document parsing (PDF/DOCX), claim extraction, and citation mapping."""

from credence.ingest.citations import (
    CitationMappingResult,
    InTextCitation,
    extract_in_text_citations,
    map_citations,
    parse_reference_list,
)
from credence.ingest.claims import deterministic_extract_claims, extract_claims, validate_claims_json
from credence.ingest.parse import PageText, ParsedDocument, Section, parse_document, parse_docx, parse_pdf

__all__ = [
    "PageText",
    "Section",
    "ParsedDocument",
    "parse_pdf",
    "parse_docx",
    "parse_document",
    "InTextCitation",
    "CitationMappingResult",
    "extract_in_text_citations",
    "parse_reference_list",
    "map_citations",
    "extract_claims",
    "deterministic_extract_claims",
    "validate_claims_json",
]

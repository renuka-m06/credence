"""Unit tests for document ingest: PDF parsing, claim extraction, and citation mapping."""

from pathlib import Path

from credence.ingest.citations import map_citations
from credence.ingest.claims import deterministic_extract_claims, extract_claims
from credence.ingest.parse import parse_pdf


def test_pdf_parsing_and_sections():
    """Verify PyMuPDF parses pages, sections, and references correctly."""
    pdf_path = Path("data/demo/sample_paper.pdf")
    assert pdf_path.exists(), "Sample PDF must exist in data/demo/"

    doc = parse_pdf(pdf_path)
    assert doc.metadata["page_count"] == 2
    assert len(doc.pages) == 2
    assert doc.file_type == "pdf"

    section_titles = [s.title.lower() for s in doc.sections]
    assert any("abstract" in t for t in section_titles)
    assert any("introduction" in t for t in section_titles)
    assert any("results" in t for t in section_titles)
    assert any("references" in t for t in section_titles)

    # Reference section text must be non-empty and contain references
    assert "[4]" in doc.reference_section_text
    assert "Attention Is All You Need" in doc.reference_section_text


def test_citation_mapping_and_ref_4():
    """Verify in-text citations map to references, specifically verifying [4]."""
    pdf_path = Path("data/demo/sample_paper.pdf")
    doc = parse_pdf(pdf_path)

    mapping = map_citations(
        body_text=doc.text,
        ref_section_text=doc.reference_section_text,
        sections=doc.sections,
    )

    # All 4 in-text citations should be mapped
    assert "1" in mapping.mapped
    assert "2" in mapping.mapped
    assert "3" in mapping.mapped
    assert "4" in mapping.mapped

    # Check mapping of [4]
    ref_4 = mapping.mapped["4"]
    assert ref_4.key == "4"
    assert "Attention Is All You Need" in ref_4.title
    assert ref_4.year == 2017
    assert ref_4.doi == "10.1145/3065386"
    assert any("Vaswani" in a for a in ref_4.authors)

    # Check diagnostic flags
    assert len(mapping.missing) == 0
    assert len(mapping.uncited) == 0


def test_claim_extraction_and_slot_atomization():
    """Verify claim extraction identifies claims and atomizes slots."""
    pdf_path = Path("data/demo/sample_paper.pdf")
    doc = parse_pdf(pdf_path)

    # Find Results section
    results_sec = next(s for s in doc.sections if "results" in s.title.lower())
    claims = extract_claims(results_sec.content, section_name="Results")

    assert len(claims) >= 2

    # Check mortality reduction claim
    claim_mortality = next(
        (c for c in claims if "12.1%" in c.text and "4" in c.citation_keys),
        None
    )
    assert claim_mortality is not None, "Expected claim with 12.1% and citation [4]"
    assert "30-day mortality" in claim_mortality.text
    assert "4" in claim_mortality.citation_keys

    # Check slot atomization
    slot_types = [s.field_type for s in claim_mortality.slots]
    assert "number" in slot_types
    assert "quote" in slot_types

    number_slot = next(s for s in claim_mortality.slots if s.field_type == "number")
    assert "12.1%" in number_slot.expected_value

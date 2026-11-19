"""Demonstration script: End-to-end ingest and reference mapping."""

from pathlib import Path
from credence.ingest.parse import parse_pdf
from credence.ingest.citations import map_citations
from credence.ingest.claims import extract_claims

def main():
    pdf_path = Path("data/demo/sample_paper.pdf")
    doc = parse_pdf(pdf_path)

    print("=== 1. PARSED DOCUMENT ===")
    print(f"File: {doc.file_path}")
    print(f"Pages: {len(doc.pages)}")
    print("Sections identified:", [s.title for s in doc.sections])

    print("\n=== 2. IN-TEXT CITATIONS & REFERENCE MAPPING ===")
    mapping = map_citations(doc.text, doc.reference_section_text, doc.sections)
    print(f"Total in-text citations found: {len(mapping.citations)}")
    for c in mapping.citations:
        print(f"  Marker: {c.raw_marker:<6} Keys: {c.keys} in {c.section_name}: \"{c.context_sentence[:60]}...\"")

    print("\n=== 3. MAPPING FOR CITATION [4] ===")
    ref_4 = mapping.mapped.get("4")
    if ref_4:
        print(f"  Key:         [{ref_4.key}]")
        print(f"  Title:       {ref_4.title}")
        print(f"  Authors:     {ref_4.authors}")
        print(f"  Year:        {ref_4.year}")
        print(f"  DOI:         {ref_4.doi}")
        print(f"  Journal:     {ref_4.journal}")
    else:
        print("  [4] NOT MAPPED!")

    print("\n=== 4. EXTRACTED CLAIMS & SLOTS ===")
    results_sec = next(s for s in doc.sections if "results" in s.title.lower())
    claims = extract_claims(results_sec.content, section_name="Results")
    print(f"Extracted {len(claims)} claim(s) from Results:")
    for cl in claims:
        print(f"\n  Claim ID:      {cl.id}")
        print(f"  Text:          \"{cl.text}\"")
        print(f"  Citation keys: {cl.citation_keys}")
        print("  Slots:")
        for sl in cl.slots:
            print(f"    - [{sl.field_type}] expected: \"{sl.expected_value}\" ({sl.description})")

if __name__ == "__main__":
    main()

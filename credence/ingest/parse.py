"""Document parser for PDF and DOCX manuscripts.

Extracts text, page numbers, structural sections, and isolates the bibliography section.
Uses PyMuPDF (pymupdf) for PDF and python-docx for DOCX.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

try:
    import docx
except ImportError:
    docx = None


@dataclass
class PageText:
    """Page number and extracted text."""
    page_number: int
    text: str


@dataclass
class Section:
    """Logical document section (e.g. Abstract, Introduction, Results, References)."""
    title: str
    content: str
    page_start: int = 1
    page_end: int = 1


@dataclass
class ParsedDocument:
    """Fully parsed manuscript representation."""
    file_path: str
    file_type: str  # 'pdf' or 'docx'
    text: str
    pages: list[PageText] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    reference_section_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "file_type": self.file_type,
            "text": self.text,
            "pages": [asdict(p) for p in self.pages],
            "sections": [asdict(s) for s in self.sections],
            "reference_section_text": self.reference_section_text,
            "metadata": self.metadata,
        }


# Section header patterns common in scientific manuscripts
SECTION_HEADER_PATTERN = re.compile(
    r'^(?:\d+\.?\s*)?(abstract|introduction|background|methods|methodology|materials\s+and\s+methods|results|discussion|conclusion|conclusions|references|bibliography|literature\s+cited)\b[:.]?',
    re.IGNORECASE
)


def _split_into_sections(pages: list[PageText]) -> tuple[list[Section], str]:
    """Segment extracted pages into standard academic sections and isolate references."""
    sections: list[Section] = []
    current_title = "Header / Metadata"
    current_lines: list[str] = []
    start_page = 1
    ref_text = ""

    for page in pages:
        lines = page.text.split("\n")
        for line in lines:
            line_str = line.strip()
            match = SECTION_HEADER_PATTERN.match(line_str)
            # Ensure line looks like a header (short length, not a long sentence)
            if match and len(line_str) < 60:
                if current_lines:
                    content = "\n".join(current_lines).strip()
                    if content:
                        sections.append(Section(
                            title=current_title,
                            content=content,
                            page_start=start_page,
                            page_end=page.page_number
                        ))
                current_title = match.group(1).title()
                current_lines = []
                start_page = page.page_number
            else:
                current_lines.append(line)

    if current_lines:
        content = "\n".join(current_lines).strip()
        if content:
            sections.append(Section(
                title=current_title,
                content=content,
                page_start=start_page,
                page_end=pages[-1].page_number if pages else 1
            ))

    # Identify References section
    for sec in sections:
        if sec.title.lower() in ("references", "bibliography", "literature cited"):
            ref_text = sec.content
            break

    # If no explicit References section found, look for "References" heading in full text
    if not ref_text and sections:
        full_text = "\n".join(p.text for p in pages)
        ref_match = re.search(r'\n(?:references|bibliography)\s*\n(.*)$', full_text, re.IGNORECASE | re.DOTALL)
        if ref_match:
            ref_text = ref_match.group(1).strip()

    return sections, ref_text


def parse_pdf(file_path: Path | str) -> ParsedDocument:
    """Parse PDF file into pages, sections, and references using PyMuPDF."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if fitz is None:
        raise ImportError("pymupdf (fitz) is required to parse PDF documents.")

    doc = fitz.open(str(path))
    pages: list[PageText] = []
    full_text_parts: list[str] = []

    for page_idx, page in enumerate(doc, start=1):
        txt = page.get_text("text")
        pages.append(PageText(page_number=page_idx, text=txt))
        full_text_parts.append(txt)

    full_text = "\n\n".join(full_text_parts)
    sections, ref_text = _split_into_sections(pages)

    metadata = {
        "page_count": len(doc),
        "title": doc.metadata.get("title", ""),
        "author": doc.metadata.get("author", ""),
    }

    return ParsedDocument(
        file_path=str(path),
        file_type="pdf",
        text=full_text,
        pages=pages,
        sections=sections,
        reference_section_text=ref_text,
        metadata=metadata,
    )


def parse_docx(file_path: Path | str) -> ParsedDocument:
    """Parse DOCX file into text, sections, and references using python-docx."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if docx is None:
        raise ImportError("python-docx is required to parse DOCX documents.")

    doc = docx.Document(str(path))
    full_lines = []
    for para in doc.paragraphs:
        full_lines.append(para.text)

    full_text = "\n".join(full_lines)
    # DOCX doesn't have native page divisions without pagination engine; treat as page 1
    pages = [PageText(page_number=1, text=full_text)]
    sections, ref_text = _split_into_sections(pages)

    return ParsedDocument(
        file_path=str(path),
        file_type="docx",
        text=full_text,
        pages=pages,
        sections=sections,
        reference_section_text=ref_text,
        metadata={"num_paragraphs": len(doc.paragraphs)},
    )


def parse_document(file_path: Path | str) -> ParsedDocument:
    """Convenience function dispatching to PDF or DOCX parser based on file extension."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix in (".docx", ".doc"):
        return parse_docx(path)
    raise ValueError(f"Unsupported file format: '{suffix}'. Expected .pdf or .docx")

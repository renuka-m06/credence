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
    page_start: Optional[int] = 1
    page_end: Optional[int] = 1
    paragraph_start: Optional[int] = None
    paragraph_end: Optional[int] = None
    pages: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "paragraph_start": self.paragraph_start,
            "paragraph_end": self.paragraph_end,
            "pages": list(self.pages),
        }


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


# Canonical academic section names per requirements
CANONICAL_SECTIONS: dict[str, str] = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "background": "Introduction",
    "methods": "Methodology",
    "methodology": "Methodology",
    "materials and methods": "Methodology",
    "results": "Results",
    "discussion": "Discussion",
    "conclusion": "Conclusion",
    "conclusions": "Conclusion",
    "references": "References",
    "bibliography": "References",
    "literature cited": "References",
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
    current_pages: set[int] = set()
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
                        p_list = sorted(current_pages) if current_pages else [1]
                        sections.append(Section(
                            title=current_title,
                            content=content,
                            page_start=p_list[0],
                            page_end=p_list[-1],
                            pages=p_list,
                        ))
                raw_name = match.group(1).lower()
                current_title = CANONICAL_SECTIONS.get(raw_name, raw_name.title())
                current_lines = []
                current_pages = {page.page_number}
            else:
                current_lines.append(line)
                current_pages.add(page.page_number)

    if current_lines:
        content = "\n".join(current_lines).strip()
        if content:
            p_list = sorted(current_pages) if current_pages else ([pages[-1].page_number] if pages else [1])
            sections.append(Section(
                title=current_title,
                content=content,
                page_start=p_list[0],
                page_end=p_list[-1],
                pages=p_list,
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
    """Parse DOCX file into text, sections, and references using python-docx.

    Provides exact paragraph and section references instead of inventing fake PDF page numbers (Requirement 6).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if docx is None:
        raise ImportError("python-docx is required to parse DOCX documents.")

    doc = docx.Document(str(path))
    sections: list[Section] = []
    current_title = "Header / Metadata"
    current_paragraphs: list[str] = []
    start_para = 1
    full_paragraphs: list[str] = []

    for para_idx, para in enumerate(doc.paragraphs, start=1):
        para_text = para.text.strip()
        full_paragraphs.append(para.text)
        if not para_text:
            continue

        is_heading = False
        heading_title = ""

        style_name = getattr(getattr(para, "style", None), "name", "").lower()
        if "heading" in style_name:
            match = SECTION_HEADER_PATTERN.search(para_text)
            if match:
                raw = match.group(1).lower()
                heading_title = CANONICAL_SECTIONS.get(raw, raw.title())
                is_heading = True
            elif len(para_text) < 60:
                heading_title = para_text.title()
                is_heading = True

        if not is_heading:
            match = SECTION_HEADER_PATTERN.match(para_text)
            if match and len(para_text) < 60:
                raw = match.group(1).lower()
                heading_title = CANONICAL_SECTIONS.get(raw, raw.title())
                is_heading = True

        if is_heading:
            if current_paragraphs:
                content = "\n\n".join(current_paragraphs).strip()
                if content:
                    sections.append(Section(
                        title=current_title,
                        content=content,
                        page_start=None,  # No fake page numbers for DOCX
                        page_end=None,
                        paragraph_start=start_para,
                        paragraph_end=para_idx - 1,
                        pages=[],
                    ))
            current_title = heading_title
            current_paragraphs = []
            start_para = para_idx
        else:
            current_paragraphs.append(para.text)

    if current_paragraphs:
        content = "\n\n".join(current_paragraphs).strip()
        if content:
            sections.append(Section(
                title=current_title,
                content=content,
                page_start=None,
                page_end=None,
                paragraph_start=start_para,
                paragraph_end=len(doc.paragraphs),
                pages=[],
            ))

    full_text = "\n\n".join(full_paragraphs)

    # Identify References section
    ref_text = ""
    for sec in sections:
        if sec.title.lower() in ("references", "bibliography", "literature cited"):
            ref_text = sec.content
            break

    if not ref_text and sections:
        ref_match = re.search(r'\n(?:references|bibliography)\s*\n(.*)$', full_text, re.IGNORECASE | re.DOTALL)
        if ref_match:
            ref_text = ref_match.group(1).strip()

    return ParsedDocument(
        file_path=str(path),
        file_type="docx",
        text=full_text,
        pages=[],  # No fake page numbers for DOCX
        sections=sections,
        reference_section_text=ref_text,
        metadata={
            "num_paragraphs": len(doc.paragraphs),
            "file_type": "docx",
        },
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

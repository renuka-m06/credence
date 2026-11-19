"""Secure file upload validator and sanitizer for scientific documents."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Tuple

from fastapi import HTTPException, UploadFile, status

# 25 MB file size limit
MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(25 * 1024 * 1024)))
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}

# Magic byte signatures
PDF_MAGIC = b"%PDF"
DOCX_MAGIC = b"PK\x03\x04"  # Zip container header for docx OpenXML


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal attacks."""
    clean_name = Path(filename).name
    # Strip any directory separators or control characters
    clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', clean_name)
    if not clean_name or clean_name.startswith('.'):
        clean_name = f"upload_{clean_name}"
    return clean_name[:255]


async def validate_and_save_upload(file: UploadFile) -> Tuple[Path, str]:
    """Validate upload size, extension, magic signature, and safely buffer to temp file.

    Returns:
        Tuple of (temporary file Path, sanitized filename).
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing filename for uploaded file.",
        )

    clean_filename = sanitize_filename(file.filename)
    suffix = Path(clean_filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{suffix}'. Supported file formats: .pdf, .docx",
        )

    # Read first chunk to check magic signature
    initial_chunk = await file.read(4096)
    if not initial_chunk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    # Validate magic bytes against claimed extension
    if suffix == ".pdf" and not initial_chunk.startswith(PDF_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file signature: Content does not match PDF format (%PDF signature missing).",
        )
    elif suffix in (".docx", ".doc") and not initial_chunk.startswith(DOCX_MAGIC):
        # Only strict check docx zip header if .docx
        if suffix == ".docx":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file signature: Content does not match DOCX OpenXML format (PK archive signature missing).",
            )

    # Stream remainder of file while enforcing strict 25MB ceiling
    total_bytes = len(initial_chunk)
    temp_dir = Path(tempfile.gettempdir()) / "credence_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=str(temp_dir))
    try:
        tmp.write(initial_chunk)
        chunk_size = 64 * 1024  # 64KB chunks
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > MAX_UPLOAD_SIZE_BYTES:
                tmp.close()
                if Path(tmp.name).exists():
                    os.unlink(tmp.name)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds maximum allowed upload size of {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB.",
                )
            tmp.write(chunk)
    except Exception:
        tmp.close()
        if Path(tmp.name).exists():
            os.unlink(tmp.name)
        raise

    tmp.close()
    return Path(tmp.name), clean_filename

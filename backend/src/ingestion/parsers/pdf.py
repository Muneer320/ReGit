"""PDF adapter (ingestion-spec.md) — pypdf per-page text extraction.

Canonical payload preserves page structure (never flattened):
  {version:1, pages:[{n, paragraphs:[...]}]}
Image-only PDF -> ParseError(PDF_NOT_EXTRACTABLE). OCR is out of scope.
"""
from __future__ import annotations

from .base import PDF_NOT_EXTRACTABLE, ParsedUnit, ParseError, compact_json


def parse_pdf(filename: str, data: bytes) -> ParsedUnit:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover — guarded at import by dep
        raise ParseError(f"pypdf not available: {exc}") from exc

    try:
        reader = PdfReader(__bytesio(data))
        pages: list[dict] = []
        for n, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            paragraphs = _paragraphs(text)
            pages.append({"n": n, "paragraphs": paragraphs})
    except Exception as exc:
        # Covers encrypted / truncated / genuinely unreadable PDFs.
        raise ParseError(f"could not read PDF: {exc}") from exc

    if not any(p["paragraphs"] for p in pages) or len([p for p in pages if p["paragraphs"]]) == 0:
        raise ParseError(
            "no extractable text (scanned/image-only PDF)", code=PDF_NOT_EXTRACTABLE
        )

    payload = {"version": 1, "pages": pages}
    return ParsedUnit(
        kind="pdf",
        title=filename or "untitled.pdf",
        payload=payload,
        storage_bytes=compact_json(payload),
        kind_tag="pdf",
        warnings=[],
    )


def _paragraphs(text: str) -> list[str]:
    """Blank-line split -> non-empty paragraph list."""
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def __bytesio(data: bytes):
    import io

    return io.BytesIO(data)
"""Ingestion parser package — dispatch by `type` field (api-contract.md).

Each adapter returns ParsedUnit(s); structure is preserved (never flattened).
A ParseError from any adapter maps to HTTP 422 by the API layer.
"""
from __future__ import annotations

from .base import (
    PDF_NOT_EXTRACTABLE,
    CodeFile,
    ParsedUnit,
    ParseError,
    compact_json,
    extract_claims,
)
from .chatgpt import parse_chatgpt
from .claude import parse_claude
from .codebase import parse_codebase
from .markdown import parse_markdown, parse_plaintext
from .pdf import parse_pdf

TYPE_MAP = {
    "markdown": parse_markdown,
    "md": parse_markdown,
    "plaintext": parse_plaintext,
    "txt": parse_plaintext,
    "chatgpt": parse_chatgpt,
    "claude": parse_claude,
    "pdf": parse_pdf,
    "codebase": parse_codebase,
}
VALID_TYPES = {"markdown", "md", "plaintext", "txt", "chatgpt", "claude", "pdf", "codebase"}


def parse(kind: str, filename: str, data: bytes) -> list[ParsedUnit]:
    """Dispatch a raw upload to the right adapter. Raises ParseError on failure."""
    fn = TYPE_MAP.get((kind or "").lower())
    if fn is None:
        raise ParseError(f"unknown ingest type '{kind}'", code="UNKNOWN_TYPE")
    result = fn(filename, data)
    if isinstance(result, ParsedUnit):
        result = [result]
    return result

__all__ = [
    "CodeFile",
    "ParseError",
    "ParsedUnit",
    "PDF_NOT_EXTRACTABLE",
    "parse",
    "parse_chatgpt",
    "parse_claude",
    "parse_codebase",
    "parse_markdown",
    "parse_plaintext",
    "parse_pdf",
    "TYPE_MAP",
    "VALID_TYPES",
]
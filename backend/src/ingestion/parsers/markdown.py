"""markdown / plaintext adapter (ingestion-spec.md).

Raw text stored as-is: canonical = the exact input bytes. kind = md|txt.
`claim: ...` lines are surfaced on the unit so the commit engine can write
Claim rows; they do NOT participate in content identity (identity = raw bytes).
"""
from __future__ import annotations

from .base import ParsedUnit, extract_claims


def _payload(kind: str, raw_text: str) -> dict:
    return {"version": 1, "kind": kind, "text": raw_text}


def parse_markdown(filename: str, data: bytes) -> ParsedUnit:
    raw = _decode(data)
    claims = extract_claims(raw)
    return ParsedUnit(
        kind="md",
        title=_title(filename, raw),
        payload=_payload("md", raw),
        storage_bytes=data,           # exact bytes as-is (canonical identity)
        kind_tag="md",
        warnings=[],
        claims=claims,
    )


def parse_plaintext(filename: str, data: bytes) -> ParsedUnit:
    raw = _decode(data)
    return ParsedUnit(
        kind="txt",
        title=_title(filename, raw),
        payload=_payload("txt", raw),
        storage_bytes=data,
        kind_tag="txt",
        warnings=[],
        claims=extract_claims(raw),
    )


def _decode(data: bytes) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _title(filename: str, raw: str) -> str:
    # First non-empty line, truncated, or the filename as fallback.
    for line in raw.splitlines():
        line = line.strip().lstrip("#*-").strip()
        if line:
            return line[:120]
    return filename or "untitled"
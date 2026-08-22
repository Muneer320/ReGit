"""Shared ingestion types + helpers (ingestion-spec.md).

Every adapter produces one or more :class:`ParsedUnit` (canonical typed
payload). Structure is NEVER flattened — chat stays a message list, PDF keeps
page structure, codebase stays a file tree. A :class:`ParseError` surfaces a
specific, actionable message and is converted to a 422 by the API (never a
traceback).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC

# `claim: ...` sentinels declared in md/plaintext and some chat exports
# (data-model.md, ingestion-spec.md). Parsed into Claim rows at commit time.
CLAIM_RE = re.compile(r"^\s*claim\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


class ParseError(Exception):
    """A specific, actionable parse failure. Maps to HTTP 422."""

    def __init__(self, message: str, code: str = "PARSE_ERROR") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# Ingestion image-only-PDF codes per api-contract.md.
PDF_NOT_EXTRACTABLE = "PDF_NOT_EXTRACTABLE"


@dataclass(frozen=True)
class CodeFile:
    """One file inside a codebase tree being ingested."""

    path: str
    kind: str            # "code-file"
    data: bytes          # exact file bytes (canonical for that file blob)
    blob_id: str         # filled in by the pipeline after hash-write


@dataclass
class ParsedUnit:
    """Canonical typed payload for one artifact produced by an adapter."""

    kind: str                       # md|txt|chat|pdf|codebase
    title: str
    payload: dict                   # canonical typed payload (never a flat string)
    storage_bytes: bytes            # exact canonical bytes used for blob identity
    kind_tag: str                   # blob kind tag: md|txt|chat|pdf|tree
    warnings: list[str] = field(default_factory=list)
    claims: list[str] = field(default_factory=list)   # `claim:` sentinel texts
    files: list[CodeFile] = field(default_factory=list)  # codebase only


def compact_json(obj) -> bytes:
    """Canonical JSON bytes: sorted keys, compact separators (hashable form)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def extract_claims(text: str) -> list[str]:
    """Pull `claim: <text>` sentinel lines, in order."""
    return [m.group(1).strip() for m in CLAIM_RE.finditer(text)]


def now_iso() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat()


def result_201() -> int:
    return 201
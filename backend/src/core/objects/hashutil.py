"""Canonical hashing for the content-addressed object store.

ADR-02: identity = SHA256 over type-tagged canonical content.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Iterable, Optional

BLOB_TAG = "gr-obj-v1"
COMMIT_TAG = "gr-commit-v1"


def blob_id(kind: str, canonical_data: bytes) -> str:
    h = hashlib.sha256()
    h.update(BLOB_TAG.encode())
    h.update(kind.encode())
    h.update(b"\0")
    h.update(canonical_data)
    return h.hexdigest()


def tree_id(entries: Iterable[tuple[str, str, str]]) -> str:
    """entries: iterable of (path, blob_id, kind); canonicalized sorted-by-path JSON."""
    canon = json.dumps(
        sorted(([p, b, k] for p, b, k in entries), key=lambda e: e[0]),
        separators=(",", ":"),
    ).encode()
    return blob_id("tree", canon)


def commit_id(
    parents: list[str],
    root_hash: str,
    artifact_id: str,
    message: str,
    author: str,
    author_date: Optional[str] = None,
) -> str:
    """author_date is part of identity; demo scripts pin it via GR_AUTHOR_DATE."""
    date = author_date or os.environ.get("GR_AUTHOR_DATE") or _now_iso()
    h = hashlib.sha256()
    h.update(COMMIT_TAG.encode())
    h.update(",".join(sorted(parents)).encode())
    h.update(root_hash.encode())
    h.update(artifact_id.encode())
    h.update(message.encode())
    h.update(author.encode())
    h.update(date.encode())
    return h.hexdigest()


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def short_hash(text: str) -> str:
    """SHA1-16 used for normalized sentence hashing in the alignment engine."""
    return hashlib.sha1(text.encode()).hexdigest()[:16]

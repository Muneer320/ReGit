"""Relational ID generation (prefixed ULIDs per data-model.md).

Content-addressed entities (Blob/Tree/Commit) use hex SHA-256 ids computed by
hashutil; every ephemeral/relational entity uses a `prefix_ulid` (e.g.
`art_01J...`, `src_01J...`, `clm_01J...`, `pe_01J...`). Uses Crockford base32
(ULID alphabet) so ids are URL-safe, sortable by time, and collision-resistant.
"""
from __future__ import annotations

import os
import time

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # no I/L/O/U


def new_id(prefix: str) -> str:
    """Return `prefix` + ULID (48-bit ms timestamp + 80-bit randomness)."""
    ts = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(10), "big")

    ts_chars = ""
    v = ts
    for _ in range(10):
        ts_chars = _CROCKFORD[v & 31] + ts_chars
        v >>= 5

    rand_chars = ""
    for _ in range(16):
        rand_chars = _CROCKFORD[rand & 31] + rand_chars
        rand >>= 5

    return prefix + ts_chars + rand_chars
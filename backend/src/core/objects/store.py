"""Content-addressed object store (blobs on disk by hash, index in SQLite).

STUB for the scaffold: put_blob/get_blob are real; the rest raise
NotImplementedError with pointers to the owning spec. Owner: Muneer (H0-H1).
Implements ADR-01/02. Invariants: objects immutable; id == hash(content).
"""
from __future__ import annotations

import os
import sqlite3
import zlib
from pathlib import Path

from .hashutil import blob_id


class ObjectStore:
    def __init__(self, data_dir: str = "data") -> None:
        self.objects_dir = Path(data_dir) / "objects"
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(Path(data_dir) / "meta.db"))
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")

    def _path_for(self, oid: str) -> Path:
        return self.objects_dir / oid[:2] / oid[2:]

    def put_blob(self, kind: str, data: bytes) -> str:
        """Content-addressed, deduped write. Returns the blob id."""
        oid = blob_id(kind, data)
        p = self._path_for(oid)
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_bytes(zlib.compress(data))
            os.replace(tmp, p)  # atomic-ish: never a partial object
            self.db.execute(
                "INSERT OR IGNORE INTO objects(hash, kind, size, path) VALUES (?,?,?,?)",
                (oid, kind, len(data), str(p)),
            )
            self.db.commit()
        return oid

    def get_blob(self, oid: str, verify: bool = False) -> bytes:
        p = self._path_for(oid)
        if not p.exists():
            raise KeyError(f"unknown object {oid}")
        data = zlib.decompress(p.read_bytes())
        if verify or os.environ.get("GR_VERIFY_ON_READ") == "1":
            row = self.db.execute("SELECT kind FROM objects WHERE hash=?", (oid,)).fetchone()
            kind = row[0] if row else "unknown"
            assert blob_id(kind, data) == oid, f"integrity failure on {oid}"
        return data

    # --- DAG layer (H1, Muneer) ---
    def commit(self, parents: list[str], root_hash: str, artifact_id: str,
               message: str, author: str, author_date: str | None = None) -> str:
        raise NotImplementedError("H1: write commit row + CAS ref update — see versioning-spec.md")

    def merge_base(self, c1: str, c2: str) -> str | None:
        raise NotImplementedError("H4: BFS paint-down over commit_parents — see adr-03")

    def verify(self) -> list[str]:
        raise NotImplementedError("recompute all hashes; return list of failures — versioning-spec.md")

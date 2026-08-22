"""Content-addressed object store (blobs on disk by hash, index in SQLite).

Implements ADR-01/02/03. Invariants (data-model.md): objects immutable;
id == hash(content); commits immutable; the branch ref is the ONLY mutable
pointer and every ref move is a compare-and-swap (CAS) inside the same
transaction as the commit row write.

Owner: Muneer (H1/H4). Spec of record: versioning-spec.md, data-model.md.
"""
from __future__ import annotations

import os
import sqlite3
import zlib
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .hashutil import blob_id, commit_id


class RefConflictError(Exception):
    """Branch-ref CAS failed: stale expected head or concurrent writer.

    versioning-spec.md: CAS failure -> 409, client reloads. The API layer
    maps this exception to HTTP 409.
    """


class BranchExistsError(Exception):
    """create_branch() on a name that already exists for this artifact."""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class ObjectStore:
    def __init__(self, data_dir: str = "data") -> None:
        self.objects_dir = Path(data_dir) / "objects"
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(Path(data_dir) / "meta.db"), check_same_thread=False)
        # Autocommit mode: transactions are explicit via _tx() (BEGIN IMMEDIATE
        # serializes writers per artifact, which is what ref CAS needs).
        self.db.isolation_level = None
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self._bootstrap_schema()

    def _bootstrap_schema(self) -> None:
        """Apply the canonical DDL if not present. All statements are
        IF NOT EXISTS, so this is idempotent. Schema lives in backend/src/db/
        and is the single source of truth; the store must not drift from it."""
        schema = Path(__file__).resolve().parents[2] / "db" / "schema.sql"
        self.db.executescript(schema.read_text())
        self.db.commit()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        """One write transaction. BEGIN IMMEDIATE grabs the write lock up
        front, so two writers on the same artifact serialize and the
        read-then-CAS sequence below is race-free."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        else:
            self.db.execute("COMMIT")

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
               message: str, author: str, author_date: str | None = None,
               branch: str = "main", expected_head: str | None = None,
               kind: str | None = None) -> str:
        """Write ONE commit atomically: commit row -> commit_parents -> ref CAS.

        parents: [] = root, [head] = normal, [ours, theirs] = merge commit
        (2 parents max). versioning-spec.md / data-model.md.

        author_date is part of the commit identity (hashutil.commit_id) and is
        resolved as: explicit param > GR_AUTHOR_DATE env > wall clock. Passing
        it explicitly pins the commit hash (determinism requirement).

        branch: the ref to advance (default "main"). Created on first commit
        (branch create = new ref at this commit).

        expected_head: CAS guard. When None the current ref head is read inside
        the same transaction (serialized by BEGIN IMMEDIATE). A stale
        expected_head raises RefConflictError (API -> HTTP 409).

        Dedup: committing the same (parents, root, message, author, date)
        yields the same commit id — no phantom version (versioning-spec.md).
        The ref still advances (or no-ops if it already points at the id).
        """
        parents = list(parents)
        if len(parents) > 2:
            raise ValueError("a commit has at most 2 parents (merge = 2); data-model.md")
        date = author_date or os.environ.get("GR_AUTHOR_DATE") or _now_iso()
        cid = commit_id(parents, root_hash, artifact_id, message, author, author_date=date)
        with self._tx() as db:
            if db.execute("SELECT 1 FROM objects WHERE hash=?", (root_hash,)).fetchone() is None:
                raise ValueError(f"root object {root_hash} not in store — write blob(s) before commit")
            for p in parents:
                if db.execute("SELECT 1 FROM commits WHERE id=?", (p,)).fetchone() is None:
                    raise ValueError(f"parent commit {p} does not exist")
            db.execute(
                "INSERT OR IGNORE INTO commits"
                "(id, artifact_id, root_hash, message, author, author_date, kind) "
                "VALUES (?,?,?,?,?,?,?)",
                (cid, artifact_id, root_hash, message, author, date, kind),
            )
            for p in parents:
                db.execute(
                    "INSERT OR IGNORE INTO commit_parents(commit_id, parent_id) VALUES (?,?)",
                    (cid, p),
                )
            self._cas_advance(db, branch, artifact_id, cid, expected_head)
        return cid

    def _cas_advance(self, db: sqlite3.Connection, branch: str,
                     artifact_id: str, cid: str, expected_head: str | None) -> None:
        """Advance (or create) the branch ref to cid, CAS-guarded.

        refs is the operational table (data-model.md DDL); branches mirrors it
        with created_at metadata. Both are kept in sync inside this tx."""
        row = db.execute(
            "SELECT head FROM refs WHERE name=? AND artifact_id=?",
            (branch, artifact_id),
        ).fetchone()
        if row is None:  # branch create
            db.execute("INSERT INTO refs(name, artifact_id, head) VALUES (?,?,?)",
                       (branch, artifact_id, cid))
            db.execute(
                "INSERT OR IGNORE INTO branches"
                "(name, artifact_id, head_commit_id, created_at) VALUES (?,?,?,?)",
                (branch, artifact_id, cid, _now_iso()),
            )
            return
        current = row[0]
        if current == cid:  # dedup no-op: already the head
            return
        expected = expected_head if expected_head is not None else current
        cur = db.execute(
            "UPDATE refs SET head=? WHERE name=? AND artifact_id=? AND head=?",
            (cid, branch, artifact_id, expected),
        )
        if cur.rowcount == 0:
            raise RefConflictError(
                f"ref {branch}@{artifact_id} moved (expected {expected}, "
                f"actual {current}) — reload and retry (409)"
            )
        db.execute("UPDATE branches SET head_commit_id=? WHERE name=? AND artifact_id=?",
                   (cid, branch, artifact_id))

    # --- Branch ref helpers ---

    def head(self, branch: str, artifact_id: str) -> str | None:
        row = self.db.execute(
            "SELECT head FROM refs WHERE name=? AND artifact_id=?",
            (branch, artifact_id),
        ).fetchone()
        return row[0] if row else None

    def create_branch(self, name: str, artifact_id: str, from_commit: str) -> None:
        """Fork: create a new ref at an existing commit (versioning-spec.md)."""
        with self._tx() as db:
            if db.execute("SELECT 1 FROM commits WHERE id=?", (from_commit,)).fetchone() is None:
                raise ValueError(f"cannot branch from unknown commit {from_commit}")
            if db.execute(
                "SELECT 1 FROM refs WHERE name=? AND artifact_id=?",
                (name, artifact_id),
            ).fetchone() is not None:
                raise BranchExistsError(f"branch {name} already exists for {artifact_id}")
            db.execute("INSERT INTO refs(name, artifact_id, head) VALUES (?,?,?)",
                       (name, artifact_id, from_commit))
            db.execute(
                "INSERT INTO branches(name, artifact_id, head_commit_id, created_at) VALUES (?,?,?,?)",
                (name, artifact_id, from_commit, _now_iso()),
            )

    def advance_branch(self, name: str, artifact_id: str, new_head: str,
                       expected_head: str | None = None) -> None:
        """CAS ref move (used by merge resolution; api-contract.md: 'Ref moves:
        single UPDATE guarded by expected head')."""
        with self._tx() as db:
            row = db.execute(
                "SELECT head FROM refs WHERE name=? AND artifact_id=?",
                (name, artifact_id),
            ).fetchone()
            if row is None:
                raise ValueError(f"branch {name} does not exist for {artifact_id}")
            if db.execute("SELECT 1 FROM commits WHERE id=?", (new_head,)).fetchone() is None:
                raise ValueError(f"cannot point branch at unknown commit {new_head}")
            if row[0] == new_head:
                return
            expected = expected_head if expected_head is not None else row[0]
            cur = db.execute(
                "UPDATE refs SET head=? WHERE name=? AND artifact_id=? AND head=?",
                (new_head, name, artifact_id, expected),
            )
            if cur.rowcount == 0:
                raise RefConflictError(
                    f"ref {name}@{artifact_id} moved (expected {expected}) — reload and retry (409)"
                )
            db.execute("UPDATE branches SET head_commit_id=? WHERE name=? AND artifact_id=?",
                       (new_head, name, artifact_id))

    # --- DAG operations ---

    def _parents_map(self) -> dict[str, list[str]]:
        edges: dict[str, list[str]] = {}
        for cid, pid in self.db.execute("SELECT commit_id, parent_id FROM commit_parents"):
            edges.setdefault(cid, []).append(pid)
        return edges

    def merge_base(self, c1: str, c2: str) -> str | None:
        """BFS paint-down over commit_parents; deterministic LCA (adr-03).

        Walk both ancestry DAGs, then pick the common ancestor minimizing
        (height, hash) where height = dist_from(c1) + dist_from(c2). This is
        the deterministic reading of adr-03's 'first common ancestor wins;
        ties broken by lowest height then hash order'. Returns None when the
        DAGs share no ancestor (root merge -> empty base, everything is an
        add). c1 == c2 -> c1.
        """
        if c1 == c2:
            return c1
        edges = self._parents_map()

        def distances(start: str) -> dict[str, int]:
            dist = {start: 0}
            q: deque[str] = deque([start])
            while q:
                node = q.popleft()
                for p in edges.get(node, ()):
                    if p not in dist:
                        dist[p] = dist[node] + 1
                        q.append(p)
            return dist

        d1 = distances(c1)
        d2 = distances(c2)
        common = d1.keys() & d2.keys()
        if not common:
            return None
        return min(common, key=lambda n: (d1[n] + d2[n], n))

    def history(self, artifact_id: str, branch: str = "main") -> list[dict]:
        """Newest-first walk from the branch head (versioning-spec.md).

        BFS level-order from the head: the first element is the head; ancestors
        follow. Linear chains come out exactly newest-first. api-contract.md
        shape: [{commit_id, parents, message, author, author_date}]."""
        start = self.head(branch, artifact_id)
        if start is None:
            return []
        edges = self._parents_map()
        seen: set[str] = set()
        order: list[dict] = []
        q: deque[str] = deque([start])
        while q:
            node = q.popleft()
            if node in seen:
                continue
            seen.add(node)
            row = self.db.execute(
                "SELECT id, message, author, author_date FROM commits WHERE id=?", (node,)
            ).fetchone()
            if row is None:
                continue
            order.append({
                "commit_id": row[0],
                "parents": list(edges.get(node, [])),
                "message": row[1],
                "author": row[2],
                "author_date": row[3],
            })
            q.extend(edges.get(node, []))
        return order

    def verify(self) -> list[str]:
        """Recompute every stored blob/commit hash; return failure messages.

        Empty list == clean (versioning-spec.md `gr verify`, <30s at demo
        scale). The commit hash is recomputed with the STORED author_date so
        GR_AUTHOR_DATE/env cannot mask a mismatch."""
        failures: list[str] = []
        for h, kind in self.db.execute("SELECT hash, kind FROM objects"):
            try:
                data = self.get_blob(h)
                if blob_id(kind, data) != h:
                    failures.append(f"blob {h} (kind={kind}): hash mismatch")
            except Exception as exc:  # missing file, corrupt zlib, ...
                failures.append(f"blob {h} (kind={kind}): {exc}")
        for cid, artifact_id, root_hash, message, author, author_date, _kind in self.db.execute(
            "SELECT id, artifact_id, root_hash, message, author, author_date, kind FROM commits"
        ):
            parents = [r[0] for r in self.db.execute(
                "SELECT parent_id FROM commit_parents WHERE commit_id=? ORDER BY parent_id", (cid,)
            )]
            if commit_id(parents, root_hash, artifact_id, message, author, author_date) != cid:
                failures.append(f"commit {cid}: hash mismatch")
        return failures
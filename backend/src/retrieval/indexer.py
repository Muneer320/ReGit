"""Delta reindex — the retrieval depth story (retrieval-spec.md §Indexing).

On commit C of artifact A on branch B:
1. align(parent content, C content) -> changed/added/deleted sids (ADR-04 spine).
2. Delete chunks of (A,B) containing deleted/edited sids; upsert chunks for
   added/edited sids.
3. New chunks: introduced_in_commit=C, replaces=[old chunk ids].
4. FTS5 + Chroma updated transactionally-ish (Chroma upsert then FTS row;
   failures logged, index rebuildable via rebuild() / scripts/reindex.py).

Chunk ids are stable per (artifact, branch, position) (chunkers.py), so
"which chunks changed" is decided by id + text comparison — unchanged chunks
keep their rows (and their ORIGINAL introduced_in_commit) untouched; only
affected chunks are deleted/reinserted. `replaces` additionally uses the
aligner's old<->new sentence mapping so a chunk that moved across sections is
still attributed as replacing the chunk it superseded.

Deterministic by contract: same store + same commit -> identical chunk rows,
FTS rows, sentence_index rows and (when vectors are enabled) identical
vector upserts. sqlite writes use the store's shared connection
(check_same_thread=False) inside BEGIN IMMEDIATE transactions (store._tx).

This module never rewrites the align spine — diff_prose/align are reused as
the single alignment engine (demo differentiator #2).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from ..core.diff.align import align, diff_prose, normalize, sentence_hash, split_paragraphs, split_sentences
from .chunkers import Chunk, chunk_document
from .vectors import VectorStore, VectorUnavailable

logger = logging.getLogger(__name__)

_CHANGED_STATUSES = {"edited", "added", "deleted"}


@dataclass
class ReindexOutcome:
    commit_id: str
    branch: str
    deleted_chunk_ids: list[str] = field(default_factory=list)
    upserted_chunk_ids: list[str] = field(default_factory=list)
    sentence_rows: int = 0
    vector_ok: bool = True
    vector_error: str | None = None


# ---------------------------------------------------------------------------
# payload loading (reuses the object store; never re-parses uploads)
# ---------------------------------------------------------------------------

def _load_payload(store, kind: str, root_hash: str):
    """Canonical payload for a commit root: raw text (md/txt), parsed JSON
    (chat/pdf), file map (codebase)."""
    if kind in ("md", "txt"):
        return store.get_blob(root_hash).decode("utf-8", "replace")
    data = store.get_blob(root_hash)
    if kind == "chat":
        payload = json.loads(data)
        payload["messages"] = sorted(payload.get("messages", []), key=lambda m: m["ord"])
        return payload
    if kind == "pdf":
        return json.loads(data)
    if kind == "codebase":
        entries = json.loads(data)  # canonical [[path, blob_id, kind], ...]
        files = {}
        for path, bid, _k in entries:
            files[path] = store.get_blob(bid).decode("utf-8", "replace")
        return {"files": [{"path": p, "text": t} for p, t in sorted(files.items())]}
    raise ValueError(f"no chunker for kind {kind!r}")


# ---------------------------------------------------------------------------
# per-kind alignment (all routing through the ADR-04 spine)
# ---------------------------------------------------------------------------

def _flatten_grid(text: str) -> list[tuple[int, int, str]]:
    return [
        (pi, si, s)
        for pi, p in enumerate(split_paragraphs(text))
        for si, s in enumerate(split_sentences(p))
    ]


def _align_maps(old_text: str, new_text: str) -> tuple[dict[int, int], dict[int, int]]:
    """old<->new sentence-index maps from a second pass over the spine.

    diff_prose emits Change records (the spec's view); this pass recovers the
    positional mapping diff_prose doesn't expose, used to attribute `replaces`.
    """
    old_flat = _flatten_grid(old_text)
    new_flat = _flatten_grid(new_text)
    ops = align([s for _, _, s in old_flat], [s for _, _, s in new_flat])
    new_to_old: dict[int, int] = {}
    old_to_new: dict[int, int] = {}
    for op in ops:
        if op.type in ("equal", "edited") and op.old_i is not None and op.new_i is not None:
            new_to_old[op.new_i] = op.old_i
            old_to_new[op.old_i] = op.new_i
    return new_to_old, old_to_new


def _diff_text(old_text: str, new_text: str, artifact_id: str):
    changes = diff_prose(old_text, new_text, artifact_id)
    new_to_old, _old_to_new = _align_maps(old_text, new_text)
    return changes, new_to_old


def _diff_chat(old_msgs: list[dict], new_msgs: list[dict], artifact_id: str) -> list[dict]:
    """Message-level alignment via the SAME spine (normalize + LCS)."""
    old_repr = [f"{m.get('role','')} {normalize(m.get('text',''))}" for m in old_msgs]
    new_repr = [f"{m.get('role','')} {normalize(m.get('text',''))}" for m in new_msgs]
    ops = align(old_repr, new_repr)
    changes: list[dict] = []
    for op in ops:
        if op.type == "equal":
            continue
        if op.type == "edited":
            o = old_msgs[op.old_i]  # type: ignore[index]
            n = new_msgs[op.new_i]  # type: ignore[index]
            changes.append({
                "sid": f"{artifact_id}:msg:{o['ord']}:{o['role']}", "status": "edited",
                "old_text": o["text"], "new_text": n["text"],
            })
        elif op.type == "delete":
            o = old_msgs[op.old_i]  # type: ignore[index]
            changes.append({"sid": f"{artifact_id}:msg:{o['ord']}:{o['role']}",
                            "status": "deleted", "old_text": o["text"]})
        else:
            n = new_msgs[op.new_i]  # type: ignore[index]
            changes.append({"sid": f"{artifact_id}:msg:{n['ord']}:{n['role']}",
                            "status": "added", "new_text": n["text"]})
    return changes


def _diff_pdf(old_pages: list[dict], new_pages: list[dict], artifact_id: str) -> list[dict]:
    """Per-page prose alignment; sids remapped to page coordinates."""
    old_by_n = {p["n"]: p for p in old_pages}
    new_by_n = {p["n"]: p for p in new_pages}
    changes: list[dict] = []
    for n in sorted(set(old_by_n) | set(new_by_n)):
        old_paras = old_by_n.get(n, {}).get("paragraphs", [])
        new_paras = new_by_n.get(n, {}).get("paragraphs", [])
        old_t = "\n\n".join(old_paras)
        new_t = "\n\n".join(new_paras)
        if not old_t and not new_t:
            continue
        for c in diff_prose(old_t, new_t):
            # diff_prose emits "para:sent" (no artifact prefix); qualify with page.
            c["sid"] = f"{artifact_id}:p{n}:{c['sid']}"
            changes.append(c)
    return changes


def _diff_codebase(old_files: dict[str, str] | None, new_files: dict[str, str],
                   artifact_id: str) -> list[dict]:
    """File-level delta (documented simplification: code spans are qualified
    function names in chunks; the sentence_index trace is per file)."""
    old_files = old_files or {}
    changes: list[dict] = []
    for path in sorted(set(old_files) | set(new_files)):
        old_t = old_files.get(path)
        new_t = new_files.get(path)
        if old_t == new_t:
            continue
        status = "added" if old_t is None else ("deleted" if new_t is None else "edited")
        changes.append({
            "sid": f"{artifact_id}:{path}::<file>", "status": status,
            "old_text": (old_t or "")[:4000], "new_text": (new_t or "")[:4000],
        })
    return changes


def _diff_payloads(kind: str, old_payload, new_payload, artifact_id: str):
    """Dispatch per kind -> (changes, new_to_old_map or None)."""
    if kind in ("md", "txt"):
        return _diff_text(old_payload or "", new_payload, artifact_id)
    if kind == "chat":
        return _diff_chat(old_payload.get("messages", []) if old_payload else [],
                          new_payload.get("messages", []), artifact_id), None
    if kind == "pdf":
        return _diff_pdf(old_payload.get("pages", []) if old_payload else [],
                         new_payload.get("pages", []), artifact_id), None
    if kind == "codebase":
        old_files = {f["path"]: f["text"] for f in old_payload["files"]} if old_payload else None
        new_files = {f["path"]: f["text"] for f in new_payload["files"]}
        return _diff_codebase(old_files, new_files, artifact_id), None
    raise ValueError(f"no diff strategy for kind {kind!r}")


# ---------------------------------------------------------------------------
# the delta planner
# ---------------------------------------------------------------------------

def _sid_to_flat(grid: list[tuple[int, int, str]], artifact_id: str) -> dict[str, int]:
    return {f"{artifact_id}:{pi}:{si}": i for i, (pi, si, _s) in enumerate(grid)}


def _flat_to_sid(grid: list[tuple[int, int, str]], artifact_id: str) -> dict[int, str]:
    return {i: f"{artifact_id}:{pi}:{si}" for i, (pi, si, _s) in enumerate(grid)}


def _plan_delta(
    old_rows: list[dict], new_chunks: list[Chunk],
    new_to_old: dict[int, int] | None,
    old_sid_to_flat: dict[str, int], new_sid_to_flat: dict[str, int],
    old_flat_to_sid: dict[int, str],
) -> tuple[list[str], list[tuple[Chunk, list[str]]]]:
    """Return (deleted_chunk_ids, [(new_chunk, replaces)]) for this commit.

    Rule (retrieval-spec.md): delete chunks whose text is gone or changed;
    upsert chunks whose text is new or changed. `replaces` = old chunk ids
    superseded: the same-id predecessor plus — via the aligner's positional
    map — any deleted old chunk whose old sentences map into this chunk.
    """
    old_by_id = {r["chunk_id"]: r for r in old_rows}
    new_by_id = {c.chunk_id: c for c in new_chunks}

    deleted: list[str] = []
    for cid in sorted(old_by_id):
        oc = old_by_id[cid]
        nc = new_by_id.get(cid)
        if nc is None or nc.text != oc["text"]:
            deleted.append(cid)

    deleted_set = set(deleted)
    upserts: list[tuple[Chunk, list[str]]] = []
    for cid in sorted(new_by_id):
        nc = new_by_id[cid]
        oc = old_by_id.get(cid)
        if oc is not None and oc["text"] == nc.text:
            continue  # unchanged: keep row, keep original introduced_in_commit
        replaces: list[str] = [cid] if oc is not None else []
        old_sids_covered: set[str] = set()
        for s in nc.sids:
            flat = new_sid_to_flat.get(s)
            if flat is not None and new_to_old is not None:
                oi = new_to_old.get(flat)
                if oi is not None:
                    old_sids_covered.add(old_flat_to_sid.get(oi, ""))
        if old_sids_covered:
            for ocid in sorted(deleted_set - {cid}):
                if old_sids_covered & set(json.loads(old_by_id[ocid]["sid_range"])):
                    replaces.append(ocid)
        upserts.append((nc, sorted(set(replaces))))
    return deleted, upserts


# ---------------------------------------------------------------------------
# the indexer
# ---------------------------------------------------------------------------

class Indexer:
    """Owns chunk rows + FTS5 + (optional) Chroma for one ObjectStore."""

    def __init__(self, store, vector: VectorStore | None = None) -> None:
        self.store = store
        self.vector = vector

    # -- commit path --------------------------------------------------------

    def reindex(self, commit_id: str, branch: str = "main") -> ReindexOutcome:
        store = self.store
        outcome = ReindexOutcome(commit_id=commit_id, branch=branch)
        row = store.db.execute(
            "SELECT artifact_id, root_hash, kind FROM commits WHERE id=?", (commit_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown commit {commit_id}")
        artifact_id, root_hash, commit_kind = row
        arow = store.db.execute(
            "SELECT kind, title, source_id FROM artifacts WHERE id=?", (artifact_id,)
        ).fetchone()
        if arow is None:
            raise KeyError(f"unknown artifact {artifact_id}")
        kind = commit_kind or arow[0]
        source_id = arow[2]

        parents = [r[0] for r in store.db.execute(
            "SELECT parent_id FROM commit_parents WHERE commit_id=? ORDER BY parent_id", (commit_id,)
        )]
        parent = parents[0] if parents else None

        new_payload = _load_payload(store, kind, root_hash)
        old_payload = _load_payload(store, kind, store.db.execute(
            "SELECT root_hash FROM commits WHERE id=?", (parent,)
        ).fetchone()[0]) if parent else None

        changes, new_to_old = _diff_payloads(kind, old_payload, new_payload, artifact_id)
        new_chunks = chunk_document(kind, new_payload, artifact_id, branch)

        old_rows = [
            {
                "chunk_id": r[0], "text": r[1],
                "sid_range": r[2] or "[]",
            }
            for r in store.db.execute(
                "SELECT chunk_id, text, sid_range FROM chunks WHERE artifact_id=? AND branch=?",
                (artifact_id, branch),
            )
        ]

        grids = _flatten_grid(old_payload) if old_payload and kind in ("md", "txt") else []
        new_grid = _flatten_grid(new_payload) if kind in ("md", "txt") else []
        deleted, upserts = _plan_delta(
            old_rows, new_chunks, new_to_old,
            _sid_to_flat(grids, artifact_id), _sid_to_flat(new_grid, artifact_id),
            _flat_to_sid(grids, artifact_id),
        )
        outcome.deleted_chunk_ids = deleted
        outcome.upserted_chunk_ids = [c.chunk_id for c, _ in upserts]

        # sentence_index trace (one row per Change record)
        sent_rows = [
            (
                commit_id, artifact_id, c["sid"], c["status"],
                sentence_hash(c["old_text"]) if c.get("old_text") else "",
                sentence_hash(c["new_text"]) if c.get("new_text") else "",
                (c.get("new_text") or c.get("old_text") or "")[:4000],
            )
            for c in changes if c["status"] in _CHANGED_STATUSES
        ]
        outcome.sentence_rows = len(sent_rows)

        # --- sqlite: chunks + fts inside one tx (store's shared connection) ---
        try:
            with store._tx() as db:
                for cid in deleted:
                    db.execute("DELETE FROM chunks WHERE chunk_id=?", (cid,))
                    db.execute("DELETE FROM chunks_fts WHERE chunk_id=?", (cid,))
                for nc, replaces in upserts:
                    db.execute("DELETE FROM chunks WHERE chunk_id=?", (nc.chunk_id,))
                    db.execute("DELETE FROM chunks_fts WHERE chunk_id=?", (nc.chunk_id,))
                    db.execute(
                        "INSERT INTO chunks"
                        "(chunk_id, artifact_id, branch, introduced_in_commit, replaces,"
                        " sid_range, kind, source_id, text) VALUES (?,?,?,?,?,?,?,?,?)",
                        (nc.chunk_id, artifact_id, branch, commit_id,
                         json.dumps(replaces, separators=(",", ":")), nc.sid_range,
                         nc.kind, source_id, nc.text),
                    )
                    db.execute(
                        "INSERT INTO chunks_fts(chunk_id, text) VALUES (?,?)",
                        (nc.chunk_id, nc.text),
                    )
                for r in sent_rows:
                    db.execute(
                        "INSERT OR REPLACE INTO sentence_index"
                        "(commit_id, artifact_id, sid, status, old_hash, new_hash, text)"
                        " VALUES (?,?,?,?,?,?,?)", r,
                    )
        except Exception:
            logger.exception("sqlite index write failed for %s", commit_id)
            raise

        # --- vector leg: transactional-ish, failures degrade, never raise ---
        if self.vector is not None and (deleted or upserts):
            try:
                if deleted:
                    self.vector.delete(deleted)
                if upserts:
                    self.vector.upsert(
                        [nc.chunk_id for nc, _ in upserts],
                        [nc.text for nc, _ in upserts],
                        [
                            {
                                "artifact_id": artifact_id,
                                "branch": branch,
                                "introduced_in_commit": commit_id,
                                "replaces": json.dumps(replaces, separators=(",", ":")),
                                "sid_range": nc.sid_range,
                                "kind": nc.kind,
                                "source_id": source_id or "",
                            }
                            for nc, replaces in upserts
                        ],
                    )
            except VectorUnavailable as exc:
                outcome.vector_ok = False
                outcome.vector_error = str(exc)
                logger.warning("vector leg degraded for %s: %s", commit_id, exc)
        return outcome

    def rebuild(self) -> list[ReindexOutcome]:
        """Full rebuild from the object store (spec fallback: derived data)."""
        store = self.store
        with store._tx() as db:
            db.execute("DELETE FROM chunks")
            db.execute("DELETE FROM chunks_fts")
            db.execute("DELETE FROM sentence_index")
        outcomes: list[ReindexOutcome] = []
        for (aid,) in store.db.execute("SELECT id FROM artifacts"):
            for (bname,) in store.db.execute(
                "SELECT name FROM branches WHERE artifact_id=?", (aid,)
            ):
                chain = [h["commit_id"] for h in reversed(store.history(aid, bname))]
                for cid in chain:
                    outcomes.append(self.reindex(cid, branch=bname))
        logger.info("rebuild: %d commit-reindex outcomes", len(outcomes))
        return outcomes


# ---------------------------------------------------------------------------
# module-level convenience (API/demo wiring)
# ---------------------------------------------------------------------------

_VECTOR_CACHE: dict[str, VectorStore] = {}
_INDEXER_CACHE: dict[str, Indexer] = {}


def _store_key(store) -> str:
    return str(Path(store.objects_dir).resolve())


def get_vector_store(store, data_dir: str | None = None) -> VectorStore:
    """One VectorStore per store data dir (chunks collection, MiniLM)."""
    key = _store_key(store)
    if key not in _VECTOR_CACHE:
        base = data_dir or str(Path(store.objects_dir).parent)
        _VECTOR_CACHE[key] = VectorStore(base)
    return _VECTOR_CACHE[key]


def get_indexer(store, enable_vectors: bool = True) -> Indexer:
    """Cached Indexer for the store; vectors enabled when possible."""
    key = _store_key(store)
    if key in _INDEXER_CACHE:
        return _INDEXER_CACHE[key]
    vector = None
    if enable_vectors:
        try:
            vector = get_vector_store(store)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("vector store init failed: %s", exc)
    idx = Indexer(store, vector)
    _INDEXER_CACHE[key] = idx
    return idx


def reindex_commit(store, commit_id: str, branch: str = "main",
                   vector: VectorStore | None = None) -> ReindexOutcome:
    """One-shot delta reindex of a single commit."""
    if vector is None:
        return Indexer(store, None).reindex(commit_id, branch)
    return Indexer(store, vector).reindex(commit_id, branch)


def rebuild(store, vector: VectorStore | None = None) -> list[ReindexOutcome]:
    return Indexer(store, vector).rebuild()
"""Hybrid retrieval service (retrieval-spec.md / ADR-11).

Pipeline: query -> FTS5 keyword candidates ∪ vector kNN candidates -> dedupe
by chunk_id -> version/provenance filter (branch, as_of_commit ancestry,
artifact_kind) -> rerank (0.6*vector + 0.3*bm25_norm + 0.1*source_diversity)
-> cited SearchResult[] (data-model.md). NOT a RAG chatbot: no LLM, no answer
synthesis — every hit carries its citation metadata.

Degraded mode (spec fallback): when the vector stack is unavailable or fails,
the service runs the deterministic FTS5 + provenance pipeline and returns
degraded=True ("degraded: FTS5 only" banner). Determinism is contractual for
the keyword leg + rerank: identical store/queries -> identical results.

Thread discipline: reads go through the store's shared sqlite connection
(check_same_thread=False, WAL); the indexer owns all writes.
"""
from __future__ import annotations

import json
import logging
import re
from collections import deque

from .indexer import get_vector_store
from .vectors import VectorUnavailable

logger = logging.getLogger(__name__)

VEC_W = 0.6
BM25_W = 0.3
DIVERSITY_W = 0.1
DEGRADED_BANNER = "degraded: FTS5 only"

_FTS_SPECIAL = re.compile(r'["*^(){}:<>~-]')


def fts_query(query: str) -> str:
    """Deterministic FTS5 MATCH expression: quoted, sanitized bare terms.

    FTS5 bare tokens AND by default; each term is double-quoted (quotes
    doubled) so user input can never escape into query syntax.
    """
    terms: list[str] = []
    for raw in query.split():
        t = _FTS_SPECIAL.sub("", raw)
        if t:
            terms.append('"' + t.replace('"', '""') + '"')
    return " ".join(terms)


def compute_score(vec_sim: float, bm25_norm: float, source_diversity: float) -> float:
    """Rerank formula (retrieval-spec.md step 6)."""
    return VEC_W * vec_sim + BM25_W * bm25_norm + DIVERSITY_W * source_diversity


def rerank_candidates(candidates: list[dict], k: int) -> list[dict]:
    """Deterministic hybrid rerank.

    candidates: [{"chunk_id", "artifact_id", "vec_sim", "bm25_raw"}].
    bm25_raw is min-max normalized to [0,1] over the candidate set (all-equal
    -> 1.0). source_diversity rewards distinct artifacts greedily: a chunk
    whose artifact_id is new among higher-ranked chunks gets 1.0 of the
    diversity weight, else 0.0 — so the k results span artifacts, not one
    document (spec: "distinct artifacts preferred"). Ties: chunk_id ascending.
    Returns the top-k candidates scored/sorted (mutates nothing).
    """
    if not candidates:
        return []
    raws = [c["bm25_raw"] for c in candidates]
    mn, mx = min(raws), max(raws)
    denom = (mx - mn) if mx > mn else 1.0

    normed = [(c, 1.0 if mx == mn else (c["bm25_raw"] - mn) / denom) for c in candidates]
    # greedy diversity needs a deterministic ranking: score (diversity=1) desc, id asc
    normed.sort(key=lambda t: (-compute_score(t[0]["vec_sim"], t[1], 1.0), t[0]["chunk_id"]))

    seen_artifacts: set[str] = set()
    scored: list[dict] = []
    for c, bm25_norm in normed:
        diversity = 1.0 if c["artifact_id"] not in seen_artifacts else 0.0
        seen_artifacts.add(c["artifact_id"])
        scored.append({
            **c,
            "bm25_norm": bm25_norm,
            "diversity": diversity,
            "score": compute_score(c["vec_sim"], bm25_norm, diversity),
        })
    scored.sort(key=lambda s: (-s["score"], s["chunk_id"]))
    return scored[:k]


def commit_ancestors(store, commit_id: str) -> set[str]:
    """Ancestry closure of a commit (itself + all transitive parents)."""
    anc: set[str] = set()
    q: deque[str] = deque([commit_id])
    while q:
        cid = q.popleft()
        if cid in anc:
            continue
        anc.add(cid)
        for (p,) in store.db.execute(
            "SELECT parent_id FROM commit_parents WHERE commit_id=?", (cid,)
        ):
            q.append(p)
    return anc


class SearchService:
    """One service per store; vector leg optional (degraded when absent)."""

    def __init__(self, store, vector=None) -> None:
        self.store = store
        self.vector = vector  # VectorStore | None

    # -- legs ---------------------------------------------------------------

    def _keyword_leg(self, query: str) -> dict[str, float]:
        match = fts_query(query)
        if not match:
            return {}
        rows = self.store.db.execute(
            "SELECT c.chunk_id, bm25(chunks_fts, 5.0, 2.0) AS bm "
            "FROM chunks_fts JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id "
            "WHERE chunks_fts MATCH ? ORDER BY bm LIMIT 300",
            (match,),
        ).fetchall()
        return {r[0]: float(r[1]) for r in rows}

    def _vector_leg(self, query: str, branch: str | None, kind: str | None,
                    k: int) -> dict[str, float]:
        if self.vector is None:
            raise VectorUnavailable("vector leg disabled")
        where: dict | None = None
        if branch and kind:
            where = {"$and": [{"branch": {"$eq": branch}}, {"kind": {"$eq": kind}}]}
        elif branch:
            where = {"branch": {"$eq": branch}}
        elif kind:
            where = {"kind": {"$eq": kind}}
        ids, sims = self.vector.query(query, n_results=max(20, k * 4), where=where)
        return dict(zip(ids, sims, strict=True))

    # -- provenance filter ---------------------------------------------------

    def _visible_chunk_ids(self, candidates: set[str], branch: str | None,
                           as_of_commit: str | None, kind: str | None) -> set[str]:
        """Version/provenance filter (spec step 5).

        branch: exact match on the chunk row (default: any).
        artifact_kind: exact match on the artifact's kind.
        as_of_commit: keep chunks whose introduced_in_commit is an ancestor of
        as_of (time-travel), minus chunks replaced before that commit.
        """
        store = self.store
        if not candidates:
            return set()
        placeholders = ",".join("?" * len(candidates))
        rows = store.db.execute(
            f"SELECT chunk_id, artifact_id, branch, introduced_in_commit, replaces "
            f"FROM chunks WHERE chunk_id IN ({placeholders})",
            tuple(candidates),
        ).fetchall()
        art_ids = {r[1] for r in rows}
        kinds: dict[str, str] = {}
        if kind is not None and art_ids:
            qmark = ",".join("?" * len(art_ids))
            kinds = dict(store.db.execute(
                f"SELECT id, kind FROM artifacts WHERE id IN ({qmark})", tuple(art_ids)
            ))

        anc: set[str] | None = commit_ancestors(store, as_of_commit) if as_of_commit else None
        replaced_before: set[str] = set()
        if anc is not None:
            for r in rows:
                if r[3] in anc:
                    for old_cid in json.loads(r[4] or "[]"):
                        # An in-place delta (replaces == own id) supersedes a row
                        # that no longer exists: it must NOT self-exclude the
                        # current chunk from its own introduction window.
                        if old_cid != r[0]:
                            replaced_before.add(old_cid)

        visible: set[str] = set()
        for chunk_id, art_id, br, introduced, _replaces in rows:
            if branch is not None and br != branch:
                continue
            if kind is not None and kinds.get(art_id) != kind:
                continue
            if anc is not None:
                if introduced not in anc or chunk_id in replaced_before:
                    continue
            visible.add(chunk_id)
        return visible

    # -- citations -----------------------------------------------------------

    def _citations(self, chunk_ids: list[str]) -> dict[str, dict]:
        store = self.store
        if not chunk_ids:
            return {}
        qmark = ",".join("?" * len(chunk_ids))
        rows = store.db.execute(
            f"SELECT chunk_id, artifact_id, branch, introduced_in_commit, sid_range, "
            f"replaces, kind, source_id, text FROM chunks WHERE chunk_id IN ({qmark})",
            tuple(chunk_ids),
        ).fetchall()
        art_ids = {r[1] for r in rows}
        artifacts: dict[str, tuple] = {}
        if art_ids:
            amark = ",".join("?" * len(art_ids))
            artifacts = {
                r[0]: (r[1], r[2])
                for r in store.db.execute(
                    f"SELECT id, title, source_id FROM artifacts WHERE id IN ({amark})",
                    tuple(art_ids),
                )
            }
        src_ids = {a[1] for a in artifacts.values() if a[1]}
        sources: dict[str, tuple] = {}
        if src_ids:
            smark = ",".join("?" * len(src_ids))
            sources = {
                r[0]: (r[1], r[2])
                for r in store.db.execute(
                    f"SELECT id, type, original_filename FROM sources WHERE id IN ({smark})",
                    tuple(src_ids),
                )
            }
        out: dict[str, dict] = {}
        for chunk_id, art_id, branch, introduced, sid_range, _replaces, _kind, src_id, text in rows:
            art = artifacts.get(art_id)
            src = sources.get(src_id) if src_id else None
            out[chunk_id] = {
                "chunk_id": chunk_id,
                "text": text,
                "artifact_id": art_id,
                "artifact_title": art[0] if art else "",
                "branch": branch,
                "introduced_in_commit": introduced,
                "sid_range": sid_range,
                "source": {"type": src[0], "filename": src[1]} if src else None,
            }
        return out

    # -- main ----------------------------------------------------------------

    def search(self, query: str, k: int = 5, branch: str | None = None,
               as_of_commit: str | None = None, artifact_kind: str | None = None) -> dict:
        store = self.store
        if as_of_commit is not None and store.db.execute(
            "SELECT 1 FROM commits WHERE id=?", (as_of_commit,)
        ).fetchone() is None:
            raise ValueError(f"unknown as_of_commit {as_of_commit}")
        degraded = False

        scores_bm25 = self._keyword_leg(query)
        vec_sims: dict[str, float] = {}
        try:
            vec_sims = self._vector_leg(query, branch, artifact_kind, k)
        except VectorUnavailable:
            degraded = True

        union = set(scores_bm25) | set(vec_sims)
        if not union:
            return {"results": [], "degraded": degraded}

        visible = self._visible_chunk_ids(union, branch, as_of_commit, artifact_kind)
        if not visible:
            return {"results": [], "degraded": degraded}

        candidates = [
            {
                "chunk_id": cid,
                "artifact_id": self._artifact_id(cid),
                "vec_sim": vec_sims.get(cid, 0.0),
                "bm25_raw": scores_bm25.get(cid, 0.0),
            }
            for cid in visible
        ]
        top = rerank_candidates(candidates, max(1, k))
        citations = self._citations([s["chunk_id"] for s in top])
        results = []
        for s in top:
            hit = citations.get(s["chunk_id"])
            if hit is None:
                continue
            results.append({**hit, "score": round(s["score"], 6)})
        return {"results": results, "degraded": degraded}

    def _artifact_id(self, chunk_id: str) -> str:
        row = self.store.db.execute(
            "SELECT artifact_id FROM chunks WHERE chunk_id=?", (chunk_id,)
        ).fetchone()
        return row[0] if row else ""


# ---------------------------------------------------------------------------
# module-level entry point — keeps the API wiring signature stable
# ---------------------------------------------------------------------------

_SERVICES: dict[str, SearchService] = {}


def search(store, query: str, k: int = 5, branch: str | None = None,
           as_of_commit: str | None = None, artifact_kind: str | None = None) -> dict:
    """POST /search -> {results: [SearchResult], degraded: bool}.

    Vector leg is enabled per-store when the stack is usable; any vector
    failure degrades this call to keyword-only (never raises).
    """
    from pathlib import Path

    key = str(Path(store.objects_dir).resolve())
    svc = _SERVICES.get(key)
    if svc is None or svc.store is not store:
        try:
            vector = get_vector_store(store)
        except Exception:  # defensive: never fail search on vector init
            vector = None
        svc = SearchService(store, vector)
        _SERVICES[key] = svc
    return svc.search(query, k, branch, as_of_commit, artifact_kind)
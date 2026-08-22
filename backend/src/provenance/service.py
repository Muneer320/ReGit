"""Provenance queries (provenance-spec.md) — the three API queries.

The edges/claims/sources rows are written mechanically by the ingest pipeline
and by claims-at-commit; these functions answer:
  1. Where did this claim come from?      -> GET /provenance/claim/:id
  2. Which sources influenced artifact A? -> GET /provenance/artifact/:id/sources
  3. What was known at commit X?          -> GET /provenance/at/:commit_id/claims

All reads are over locally persisted rows; no engine dependency.
"""
from __future__ import annotations

from collections import deque


def ancestors(store, commit_id: str) -> set[str]:
    """All commits reachable via parent edges from commit_id (inclusive)."""
    parents: dict[str, list[str]] = {}
    for cid, pid in store.db.execute("SELECT commit_id, parent_id FROM commit_parents"):
        parents.setdefault(cid, []).append(pid)
    seen: set[str] = set()
    q: deque[str] = deque([commit_id])
    while q:
        node = q.popleft()
        if node in seen:
            continue
        seen.add(node)
        q.extend(parents.get(node, ()))
    return seen


def _claim_dict(row) -> dict:
    cid, text, artifact_id, commit_id, sid, created_at = row
    return {
        "id": cid, "text": text, "artifact_id": artifact_id,
        "commit_id": commit_id, "sid": sid, "created_at": created_at,
    }


def get_claim(store, claim_id: str) -> dict | None:
    """GET /provenance/claim/:id -> {claim, chain:[{kind,id,snippet}]}."""
    row = store.db.execute(
        "SELECT id, text, artifact_id, commit_id, sid, created_at FROM claims WHERE id=?",
        (claim_id,),
    ).fetchone()
    if row is None:
        return None
    claim = _claim_dict(row)

    # Walk edges backwards from the claim to materialize the chain.
    chain: list[dict] = []
    seen: set[tuple[str, str]] = set()
    q: deque[tuple[str, str]] = deque([("claim", claim_id)])  # (kind, id)
    while q:
        kind, oid = q.popleft()
        key = (kind, oid)
        if key in seen:
            continue
        seen.add(key)
        snippet = _snippet(store, kind, oid)
        chain.append({"kind": kind, "id": oid, "snippet": snippet})
        # Walk edges in BOTH directions:
        #   backward (WHERE to_kind=node) -> find what STATES this node
        #     (e.g. a commit that states the claim);
        #   forward  (WHERE from_kind=node) -> find the node's ORIGIN
        #     (e.g. the source an import derived from, then the source's
        #      artifact) — answers "where did this claim come from?" end-to-end.
        for fk, fid, rel in store.db.execute(
            "SELECT from_kind, from_id, relation FROM provenance_edges "
            "WHERE to_kind=? AND to_id=?",
            (kind, oid),
        ):
            q.append((fk, fid))
        for tk, tid, rel in store.db.execute(
            "SELECT to_kind, to_id, relation FROM provenance_edges "
            "WHERE from_kind=? AND from_id=?",
            (kind, oid),
        ):
            q.append((tk, tid))
    return {"claim": claim, "chain": chain}


def artifact_sources(store, artifact_id: str) -> list[dict]:
    """GET /provenance/artifact/:id/sources -> [{source, via_commits}]."""
    # sources reachable from this artifact via imported_as (reverse) or from
    # this artifact's commits via claim derived_from edges.
    rows = store.db.execute(
        "SELECT DISTINCT s.id, s.type, s.original_filename "
        "FROM sources s "
        "JOIN provenance_edges e ON (e.from_kind='source' AND e.from_id=s.id AND e.to_kind='artifact') "
        "WHERE e.to_id=?",
        (artifact_id,),
    ).fetchall()
    result: list[dict] = []
    for src_id, s_type, fname in rows:
        commits = [
            r[0] for r in store.db.execute(
                "SELECT id FROM commits WHERE artifact_id=?", (artifact_id,)
            )
        ]
        result.append({
            "source": {"id": src_id, "type": s_type, "original_filename": fname},
            "via_commits": commits,
        })
    return result


def claims_at(store, commit_id: str) -> list[dict]:
    """GET /provenance/at/:commit_id/claims -> [Claim] (ancestry-filtered)."""
    anc = ancestors(store, commit_id)
    if not anc:
        return []
    rows = store.db.execute(
        "SELECT id, text, artifact_id, commit_id, sid, created_at FROM claims WHERE commit_id IN (%s)"
        % ",".join("?" * len(anc)),
        tuple(anc),
    ).fetchall()
    return [_claim_dict(r) for r in rows]


def _snippet(store, kind: str, oid: str) -> str:
    try:
        if kind == "claim":
            row = store.db.execute("SELECT text FROM claims WHERE id=?", (oid,)).fetchone()
            return (row[0][:200] if row else "") or ""
        if kind == "commit":
            row = store.db.execute("SELECT message FROM commits WHERE id=?", (oid,)).fetchone()
            return (row[0] or "")[:200] if row else ""
        if kind == "artifact":
            row = store.db.execute("SELECT title FROM artifacts WHERE id=?", (oid,)).fetchone()
            return (row[0] or "")[:200] if row else ""
        if kind == "source":
            row = store.db.execute(
                "SELECT type, original_filename FROM sources WHERE id=?", (oid,)
            ).fetchone()
            return f"{row[0]}:{row[1]}"[:200] if row else ""
        return ""
    except Exception:
        return ""
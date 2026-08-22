"""Retrieval/search service (retrieval-spec.md / adr-11).

STUB: the retrieval engine (chunkers + FTS5 + embeddings delta-reindex +
hybrid query) is owned by Amrit/Muneer and not yet landed (backend/src/retrieval
is otherwise empty). The API route wires to this function so the contract shape
is fixed; until the engine lands this raises NotImplementedError (-> HTTP 501).
"""
from __future__ import annotations


def search(
    store,
    query: str,
    k: int = 5,
    branch: str | None = None,
    as_of_commit: str | None = None,
    artifact_kind: str | None = None,
) -> dict:
    """POST /search -> {results: [SearchResult]} (cited, per data-model.md).

    When the engine lands it must: FTS5 BM25 leg + vector kNN leg, dedupe by
    chunk_id, version/provenance filter (branch / ancestry time-travel), rerank
    (0.6*vector + 0.3*bm25_norm + 0.1*source_diversity), and carry mandatory
    citation metadata on every hit.
    """
    raise NotImplementedError(
        "H3: retrieval/search engine pending — chunking, FTS5+Chroma, "
        "version/provenance-filtered hybrid query (retrieval-spec.md)"
    )
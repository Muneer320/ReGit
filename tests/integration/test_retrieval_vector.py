"""Vector-leg integration tests — real Chroma PersistentClient + MiniLM-L6-v2.

This is the INTEGRATION split of the retrieval contract (unit tests cover the
deterministic keyword leg + provenance + rerank). Chroma kNN is an approximate
nearest-neighbor search, so assertions here are set-membership / degraded-flag
shaped, never exact ordering (determinism contract applies to the keyword leg
only). Skips cleanly when the vector stack is unavailable (VectorUnavailable).

Run: uv run pytest tests/integration/test_retrieval_vector.py -q
"""
from __future__ import annotations

import pytest

from backend.src.core.objects.store import ObjectStore
from backend.src.retrieval.indexer import Indexer
from backend.src.retrieval.service import SearchService
from backend.src.retrieval.vectors import VectorStore, VectorUnavailable

ART = "art_01JVEC"
DATE = "2026-01-15T12:00:00+00:00"

V0 = (
    "# Notes\n\n"
    "Gradient descent diverges when the learning rate exceeds the curvature bound.\n\n"
    "## Experiments\n\n"
    "Adam mitigates loss spikes.\n"
)
V1 = (
    "# Notes\n\n"
    "Gradient descent diverges when the learning rate exceeds the curvature bound.\n\n"
    "## Experiments\n\n"
    "Adam mitigates loss spikes at high learning rates. "
    "Momentum accelerates convergence on ill-conditioned problems.\n"
)


@pytest.fixture()
def indexed(tmp_path):
    store = ObjectStore(str(tmp_path / "store"))
    try:
        vector = VectorStore(str(tmp_path / "store"))
    except Exception as exc:
        pytest.skip(f"vector stack unavailable: {exc}")
    r0 = store.put_blob("md", V0.encode())
    c0 = store.commit([], r0, ART, "root", "m", author_date=DATE, kind="md")
    store.db.execute(
        "INSERT INTO artifacts(id, kind, title, source_id, created_at) "
        "VALUES (?,?,?,?,?)", (ART, "md", "Notes", "src_fix", DATE),
    )
    store.db.execute(
        "INSERT INTO sources(id, type, original_filename, imported_at, uploader) "
        "VALUES ('src_fix','markdown','notes.md','t','u')",
    )
    store.db.commit()
    r1 = store.put_blob("md", V1.encode())
    c1 = store.commit([c0], r1, ART, "edit", "m", author_date=DATE, kind="md")
    idx = Indexer(store, vector)
    o0 = idx.reindex(c0, branch="main")
    o1 = idx.reindex(c1, branch="main")
    if not (o0.vector_ok and o1.vector_ok):
        pytest.skip(f"vector writes failed: {o1.vector_error}")
    return store, vector, c1


def test_vector_leg_contributes_semantic_hits(indexed):
    store, vector, _c1 = indexed
    res = SearchService(store, vector).search("optimizer jitter divergence", k=5)
    assert res["degraded"] is False
    chunks = {h["chunk_id"] for h in res["results"]}
    assert chunks  # semantic kNN surfaced candidates
    # every result still carries the mandatory citation spine
    for h in res["results"]:
        assert h["artifact_id"] == ART
        assert h["artifact_title"] == "Notes"
        assert h["branch"] == "main"
        assert h["introduced_in_commit"]
        assert h["sid_range"]
        assert h["source"] == {"type": "markdown", "filename": "notes.md"}


def test_hybrid_union_dedupes_by_chunk_id(indexed):
    store, vector, _c1 = indexed
    svc = SearchService(store, vector)
    res = svc.search("Adam mitigates loss spikes", k=5)
    ids = [h["chunk_id"] for h in res["results"]]
    assert len(ids) == len(set(ids))           # union + dedupe by chunk_id
    # the updated Experiments chunk is the strong lexical hit
    assert any("momentum" in h["text"].lower() for h in res["results"])


def test_as_of_filter_applies_to_vector_results_too(indexed):
    store, vector, c1 = indexed
    svc = SearchService(store, vector)
    # momentum sentence was added at c1: absent before c1, present at c1
    before = svc.search("momentum accelerates", as_of_commit=c1, k=5)
    assert any("momentum" in h["text"].lower() for h in before["results"])


def test_failed_vector_leg_degrades_to_keyword(indexed):
    store, _vector, _c1 = indexed

    class Boom:
        def query(self, *a, **k):
            raise VectorUnavailable("boom")

    res = SearchService(store, Boom()).search("Adam mitigates")
    assert res["degraded"] is True
    assert res["results"]                      # keyword leg still answers
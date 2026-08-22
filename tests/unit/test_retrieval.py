"""Retrieval engine unit tests — deterministic (keyword leg + provenance +
rerank; NO vector leg here — see tests/integration/test_retrieval_vector.py).

Covers the depth story (delta reindex: changed sids -> only affected chunks
deleted/upserted, introduced_in_commit + replaces) and the time-travel query
(as_of_commit ancestry filter) per retrieval-spec.md.
"""
from __future__ import annotations

import json

import pytest

from backend.src.core.objects.hashutil import short_hash
from backend.src.core.objects.store import ObjectStore
from backend.src.retrieval.indexer import Indexer, reindex_commit
from backend.src.retrieval.service import (
    SearchService,
    compute_score,
    rerank_candidates,
)
from backend.src.retrieval.vectors import VectorUnavailable

ART = "art_01JRETRIEV"
DATE = "2026-01-15T12:00:00+00:00"
PREFIX = short_hash(ART)[:8]

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
    "Adam mitigates loss spikes at high learning rates.\n"
)
V2 = (
    "# Notes\n\n"
    "Gradient descent diverges when the learning rate exceeds the curvature bound. "
    "SGD oscillates on ill-conditioned objectives.\n\n"
    "## Experiments\n\n"
    "Adam mitigates loss spikes at high learning rates.\n"
)


def make_store(tmp_path):
    return ObjectStore(str(tmp_path / "store"))


def register_artifact(store, kind="md", title="Notes"):
    store.db.execute(
        "INSERT INTO artifacts(id, kind, title, source_id, created_at) VALUES (?,?,?,?,?)",
        (ART, kind, title, "src_fix", DATE),
    )
    store.db.execute(
        "INSERT INTO sources(id, type, original_filename, imported_at, uploader) "
        "VALUES ('src_fix','markdown','notes.md','t','u')",
    )
    store.db.commit()


def build_chain(tmp_path):
    """Root c0 (V0) -> c1 (V1: edit Adam sentence) -> c2 (V2: add SGD sentence)."""
    store = make_store(tmp_path)
    r0 = store.put_blob("md", V0.encode())
    c0 = store.commit([], r0, ART, "root", "m", author_date=DATE, kind="md")
    register_artifact(store)
    r1 = store.put_blob("md", V1.encode())
    c1 = store.commit([c0], r1, ART, "edit adam", "m", author_date=DATE, kind="md")
    r2 = store.put_blob("md", V2.encode())
    c2 = store.commit([c1], r2, ART, "add sgd", "m", author_date=DATE, kind="md")
    idx = Indexer(store, None)
    idx.reindex(c0, branch="main")
    idx.reindex(c1, branch="main")
    idx.reindex(c2, branch="main")
    return store, c0, c1, c2


def chunk_rows(store):
    return list(store.db.execute(
        "SELECT chunk_id, introduced_in_commit, replaces FROM chunks ORDER BY chunk_id"
    ))


# --- delta reindex (the depth story) -----------------------------------------

def test_root_commit_indexes_all_chunks(tmp_path):
    """A root commit (no parent) introduces every chunk at itself."""
    store = make_store(tmp_path)
    r0 = store.put_blob("md", V0.encode())
    c0 = store.commit([], r0, ART, "root", "m", author_date=DATE, kind="md")
    register_artifact(store)
    Indexer(store, None).reindex(c0, branch="main")
    rows = chunk_rows(store)
    assert {r[0] for r in rows} == {f"{PREFIX}:main:notes", f"{PREFIX}:main:experiments"}
    assert all(r[1] == c0 for r in rows)          # everything introduced at the root
    assert all(r[2] == "[]" for r in rows)        # nothing replaced yet
    fts = store.db.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
    assert fts == 2


def test_delta_reindex_only_churns_changed_section(tmp_path):
    """The depth story: on commit c1 only the Experiments section churns; the
    Notes section keeps its original introduced_in_commit and chunk id."""
    store = ObjectStore(str(tmp_path / "store"))
    rA = store.put_blob("md", V0.encode())
    ca = store.commit([], rA, ART, "root", "m", author_date=DATE, kind="md")
    register_artifact(store)
    rB = store.put_blob("md", V1.encode())
    cb = store.commit([ca], rB, ART, "edit adam", "m", author_date=DATE, kind="md")
    idx = Indexer(store, None)
    idx.reindex(ca, branch="main")
    out = idx.reindex(cb, branch="main")
    assert out.deleted_chunk_ids == [f"{PREFIX}:main:experiments"]
    assert out.upserted_chunk_ids == [f"{PREFIX}:main:experiments"]

    by_id = {r[0]: r for r in chunk_rows(store)}
    notes = by_id[f"{PREFIX}:main:notes"]
    assert notes[1] == ca                           # untouched -> original commit
    assert notes[2] == "[]"
    exp = by_id[f"{PREFIX}:main:experiments"]
    assert exp[1] == cb                            # churned at the edit commit
    assert json.loads(exp[2]) == [f"{PREFIX}:main:experiments"]  # old id superseded


def test_added_content_introduces_new_chunk_at_new_commit(tmp_path):
    store, _c0, c1, c2 = build_chain(tmp_path)
    notes = [r for r in chunk_rows(store) if r[0].endswith(":notes")][0]
    assert notes[1] == c2                          # c2 touched the Notes section
    assert json.loads(notes[2]) == [f"{PREFIX}:main:notes"]


def test_sentence_index_trace_records_change_statuses(tmp_path):
    from backend.src.core.diff.align import sentence_hash

    store, _c0, c1, c2 = build_chain(tmp_path)
    expected_old = sentence_hash("Adam mitigates loss spikes.")
    expected_new = sentence_hash("Adam mitigates loss spikes at high learning rates.")
    rows = list(store.db.execute(
        "SELECT commit_id, sid, status, old_hash, new_hash FROM sentence_index "
        "WHERE commit_id=? ORDER BY sid", (c1,)
    ))
    assert rows == [(c1, f"{ART}:3:0", "edited", expected_old, expected_new)]
    added = list(store.db.execute(
        "SELECT sid, status FROM sentence_index WHERE commit_id=? AND status='added'", (c2,)
    ))
    assert (f"{ART}:1:1", "added") in added


def test_reindex_is_idempotent(tmp_path):
    store, c0, c1, c2 = build_chain(tmp_path)
    before = chunk_rows(store)
    idx = Indexer(store, None)
    idx.reindex(c0, branch="main")
    idx.reindex(c1, branch="main")
    idx.reindex(c2, branch="main")
    assert chunk_rows(store) == before


def test_rebuild_from_object_store_recovers_index(tmp_path):
    store, _c0, _c1, _c2 = build_chain(tmp_path)
    before = chunk_rows(store)
    with store._tx() as db:
        db.execute("DELETE FROM chunks")
        db.execute("DELETE FROM chunks_fts")
        db.execute("DELETE FROM sentence_index")
    Indexer(store, None).rebuild()
    assert chunk_rows(store) == before


# --- hybrid search: keyword leg + citations ----------------------------------

def test_search_keyword_leg_returns_cited_results(tmp_path):
    store, _c0, c1, _c2 = build_chain(tmp_path)
    res = SearchService(store, None).search("Adam mitigates", k=5)
    assert res["degraded"] is True                 # vector leg disabled here
    assert len(res["results"]) == 1
    hit = res["results"][0]
    assert "at high learning rates" in hit["text"]  # the NEW chunk text, not old
    assert hit["artifact_id"] == ART
    assert hit["artifact_title"] == "Notes"
    assert hit["branch"] == "main"
    assert hit["introduced_in_commit"] == c1
    assert json.loads(hit["sid_range"])             # mandatory citation metadata
    assert hit["source"] == {"type": "markdown", "filename": "notes.md"}


def test_search_deterministic(tmp_path):
    store, _c0, _c1, _c2 = build_chain(tmp_path)
    svc = SearchService(store, None)
    assert svc.search("Adam mitigates") == svc.search("Adam mitigates")
    assert svc.search("diverges superlative-unique-token") == \
        svc.search("diverges superlative-unique-token")


def test_search_fts_query_sanitizes_special_chars(tmp_path):
    store, _c0, _c1, _c2 = build_chain(tmp_path)
    svc = SearchService(store, None)
    assert svc.search('Adam "mitigates" *')["results"] == svc.search("Adam mitigates")["results"]
    assert svc.search("!!!" )["results"] == []     # no searchable terms -> empty


# --- version/provenance filter (time-travel) ----------------------------------

def test_as_of_commit_ancestry_excludes_later_chunks(tmp_path):
    store, c0, c1, c2 = build_chain(tmp_path)
    svc = SearchService(store, None)
    # Adam sentence was edited at c1 -> not known at c0
    assert svc.search("Adam mitigates", as_of_commit=c0)["results"] == []
    assert len(svc.search("Adam mitigates", as_of_commit=c1)["results"]) == 1
    assert len(svc.search("Adam mitigates", as_of_commit=c2)["results"]) == 1
    # SGD sentence was added at c2 -> only known from c2 on
    assert svc.search("oscillates", as_of_commit=c1)["results"] == []
    assert len(svc.search("oscillates", as_of_commit=c2)["results"]) == 1

    # c0-era content stays visible while its section is untouched: a 2-commit
    # chain (V0 -> V1) leaves the Notes section (intro ca) untouched, so as_of
    # either commit returns it with the ORIGINAL (c0-era) text.
    store2 = ObjectStore(str(tmp_path / "s2"))
    rA = store2.put_blob("md", V0.encode())
    ca = store2.commit([], rA, ART, "root", "m", author_date=DATE, kind="md")
    register_artifact(store2)
    rB = store2.put_blob("md", V1.encode())
    cb = store2.commit([ca], rB, ART, "edit adam", "m", author_date=DATE, kind="md")
    idx = Indexer(store2, None)
    idx.reindex(ca, branch="main")
    idx.reindex(cb, branch="main")
    svc2 = SearchService(store2, None)
    for commit in (ca, cb):
        hits = svc2.search("diverges", as_of_commit=commit)["results"]
        assert len(hits) == 1
        assert "SGD" not in hits[0]["text"]
        assert hits[0]["introduced_in_commit"] == ca


def test_as_of_unknown_commit_raises(tmp_path):
    store, _c0, _c1, _c2 = build_chain(tmp_path)
    with pytest.raises(ValueError):
        SearchService(store, None).search("diverges", as_of_commit="f" * 64)


def test_branch_filter_scopes_results(tmp_path):
    store, c0, _c1, _c2 = build_chain(tmp_path)
    store.create_branch("feature", ART, c0)
    rfeat = store.put_blob("md", V1.encode())       # feature edits Adam too
    cfeat = store.commit([c0], rfeat, ART, "feature edit", "m",
                         author_date=DATE, kind="md", branch="feature")
    Indexer(store, None).reindex(cfeat, branch="feature")
    svc = SearchService(store, None)

    main_only = svc.search("Adam mitigates", branch="main")["results"]
    feat_only = svc.search("Adam mitigates", branch="feature")["results"]
    assert main_only and all(r["branch"] == "main" for r in main_only)
    assert feat_only and all(r["branch"] == "feature" for r in feat_only)
    assert feat_only[0]["introduced_in_commit"] == cfeat
    # default (branch=None) unions both branches
    both = svc.search("Adam mitigates")["results"]
    assert {r["branch"] for r in both} == {"main", "feature"}


def test_artifact_kind_filter(tmp_path):
    store, _c0, _c1, _c2 = build_chain(tmp_path)
    svc = SearchService(store, None)
    assert len(svc.search("Adam mitigates", artifact_kind="md")["results"]) == 1
    assert svc.search("Adam mitigates", artifact_kind="chat")["results"] == []


# --- rerank formula (exact weights) ------------------------------------------

def test_compute_score_weights():
    assert abs(compute_score(1.0, 1.0, 1.0) - 1.0) < 1e-12
    assert abs(compute_score(0.0, 1.0, 1.0) - 0.4) < 1e-12          # 0.3 + 0.1
    assert abs(compute_score(0.5, 0.5, 0.0) - 0.45) < 1e-12         # 0.3 + 0.15


def test_rerank_bm25_normalization_and_diversity():
    cands = [
        {"chunk_id": "a", "artifact_id": "art1", "vec_sim": 0.8, "bm25_raw": -2.0},
        {"chunk_id": "b", "artifact_id": "art1", "vec_sim": 0.2, "bm25_raw": -1.0},
    ]
    top = rerank_candidates(cands, 2)
    assert [t["chunk_id"] for t in top] == ["a", "b"]        # vector weight dominates
    assert top[0]["bm25_norm"] == 0.0 and top[1]["bm25_norm"] == 1.0   # min-max
    assert top[0]["diversity"] == 1.0 and top[1]["diversity"] == 0.0   # same artifact
    assert abs(top[0]["score"] - 0.58) < 1e-9                # 0.6*0.8 + 0.1
    assert abs(top[1]["score"] - 0.42) < 1e-9                # 0.6*0.2 + 0.3


def test_rerank_distinct_artifacts_get_diversity_bonus():
    cands = [
        {"chunk_id": "a", "artifact_id": "art1", "vec_sim": 0.5, "bm25_raw": -2.0},
        {"chunk_id": "b", "artifact_id": "art2", "vec_sim": 0.5, "bm25_raw": -1.0},
    ]
    top = rerank_candidates(cands, 2)
    assert [t["chunk_id"] for t in top] == ["b", "a"]
    assert top[0]["diversity"] == 1.0 and top[1]["diversity"] == 1.0


def test_rerank_tie_breaks_by_chunk_id():
    cands = [
        {"chunk_id": "z", "artifact_id": "a1", "vec_sim": 0.0, "bm25_raw": 1.0},
        {"chunk_id": "a", "artifact_id": "a1", "vec_sim": 0.0, "bm25_raw": 1.0},
    ]
    top = rerank_candidates(cands, 2)
    assert [t["chunk_id"] for t in top] == ["a", "z"]


def test_rerank_truncates_to_k():
    cands = [{"chunk_id": f"c{i}", "artifact_id": f"art{i}", "vec_sim": 0.0,
              "bm25_raw": float(i)} for i in range(10)]
    assert len(rerank_candidates(cands, 3)) == 3


# --- degraded mode -----------------------------------------------------------

class _BrokenVector:
    """A vector backend that always fails (exercises the degraded hook)."""

    def query(self, *a, **k):
        raise VectorUnavailable("broken on purpose")


def test_degraded_keyword_only_when_vector_fails(tmp_path):
    store, _c0, _c1, _c2 = build_chain(tmp_path)
    res = SearchService(store, _BrokenVector()).search("Adam mitigates")
    assert res["degraded"] is True
    assert res["results"] and "at high learning rates" in res["results"][0]["text"]


# --- chat delta reindex -------------------------------------------------------

def test_chat_delta_reindex_message_level(tmp_path):
    import json as _json

    store = make_store(tmp_path)
    msgs1 = {"version": 1, "source": "claude",
             "messages": [{"ord": 0, "role": "user", "text": "hello"},
                          {"ord": 1, "role": "assistant", "text": "hi"}]}
    msgs2 = {"version": 1, "source": "claude",
             "messages": [{"ord": 0, "role": "user", "text": "hello"},
                          {"ord": 1, "role": "assistant", "text": "hi there"}]}
    enc = lambda m: _json.dumps(m, sort_keys=True, separators=(",", ":")).encode()
    r0 = store.put_blob("chat", enc(msgs1))
    c0 = store.commit([], r0, ART, "root", "m", author_date=DATE, kind="chat")
    register_artifact(store, kind="chat", title="Conv")
    r1 = store.put_blob("chat", enc(msgs2))
    c1 = store.commit([c0], r1, ART, "edit msg", "m", author_date=DATE, kind="chat")

    idx = Indexer(store, None)
    idx.reindex(c0, branch="main")
    out = idx.reindex(c1, branch="main")
    assert out.deleted_chunk_ids == [f"{PREFIX}:main:msg:1:assistant"]
    assert out.upserted_chunk_ids == [f"{PREFIX}:main:msg:1:assistant"]
    rows = chunk_rows(store)
    assert len(rows) == 2
    msg0 = [r for r in rows if r[0].endswith("msg:0:user")][0]
    assert msg0[1] == c0                              # untouched message, original commit
    si = store.db.execute(
        "SELECT sid, status FROM sentence_index WHERE commit_id=?", (c1,)
    ).fetchall()
    assert (f"{ART}:msg:1:assistant", "edited") in si
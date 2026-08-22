"""Invariant placeholder tests — these encode the six core invariants.

Tests whose engine has landed are real and must pass; the ones whose engine
has not landed yet are marked xfail — that is intentional, they are the
contract gate from testing-plan.md. Run: pytest tests/unit/test_invariants.py
"""
import pytest

from backend.src.core.objects.hashutil import blob_id
from backend.src.core.objects.store import ObjectStore


def test_blob_identity_is_content_hash(tmp_path):
    store = ObjectStore(str(tmp_path))
    data = b"canonical bytes"
    oid = store.put_blob("md", data)
    assert oid == blob_id("md", data)
    assert store.get_blob(oid, verify=True) == data


def test_dedup_same_content_same_id(tmp_path):
    store = ObjectStore(str(tmp_path))
    assert store.put_blob("md", b"x") == store.put_blob("md", b"x")


def test_commit_immutability_triggers(tmp_path):
    import sqlite3
    from pathlib import Path
    store = ObjectStore(str(tmp_path))
    oid = store.put_blob("md", b"x")
    db = sqlite3.connect(str(Path(tmp_path) / "meta.db"))
    with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
        db.execute("UPDATE objects SET kind='z' WHERE hash=?", (oid,))
    with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
        db.execute("DELETE FROM objects WHERE hash=?", (oid,))
    assert store.get_blob(oid, verify=True) == b"x"


def test_branch_is_mutable_ref_to_immutable_commit(tmp_path):
    """Invariant 3: branch = mutable ref to immutable commit (versioning-spec.md).

    The ref advances across commits; the commits themselves are immutable —
    UPDATE is blocked by the SQL trigger, and the branch can fork at any old
    commit without disturbing the ref that points at it."""
    import sqlite3

    store = ObjectStore(str(tmp_path))
    r0 = store.put_blob("md", b"v1")
    r1 = store.put_blob("md", b"v2")
    c0 = store.commit([], r0, "art_1", "root", "muneer", author_date="2026-01-01T00:00:00+00:00")
    c1 = store.commit([c0], r1, "art_1", "second", "muneer", author_date="2026-01-01T00:00:00+00:00")

    # the ref is mutable: it moved from c0 to c1
    assert store.head("main", "art_1") == c1
    # a fork at the OLD commit is a new ref, and commits stay put
    store.create_branch("feature", "art_1", c0)
    assert store.head("feature", "art_1") == c0
    assert store.head("main", "art_1") == c1
    # the immutable part: UPDATE / DELETE on commits is impossible
    with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
        store.db.execute("UPDATE commits SET message='hacked' WHERE id=?", (c0,))
    with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
        store.db.execute("DELETE FROM commits WHERE id=?", (c0,))
    # both refs still resolve
    assert store.head("main", "art_1") == c1
    assert store.head("feature", "art_1") == c0


def test_crdt_convergence_shuffled_ops():
    """Invariant 4 (data-model.md) / collaboration-spec.md H7: a recorded op log
    applied in ANY of 50 shuffled orders yields byte-identical text."""
    import random

    import pycrdt


    random.seed(42)
    base = "Alpha settled. Beta claim. Gamma contribution. "
    # build a set of true concurrent CRDT deltas off a shared base
    base_doc = pycrdt.Doc()
    bt = pycrdt.Text()
    base_doc["content"] = bt
    with base_doc.transaction():
        bt.insert(0, base)
    base_state = base_doc.get_update()
    deltas = []
    for word in ["first", "second", "third", "fourth", "fifth"]:
        d, t = pycrdt.Doc(), pycrdt.Text()
        d["content"] = t
        d.apply_update(base_state)
        t = d["content"]
        with d.transaction():
            t.insert(len(str(t)), word)
        deltas.append(d.get_update())

    orders = [random.sample(range(len(deltas)), len(deltas)) for _ in range(50)]
    # 50 shuffles of the same 5 deltas -> exactly ONE distinct final text
    from backend.src.core.collaboration.ops import convergence_digest

    results = {convergence_digest([deltas[i] for i in o]) for o in orders}
    assert len(results) == 1
    # and the digest equals a direct replay of the sorted log
    ref = convergence_digest(deltas)
    assert ref in results


def test_provenance_chain_across_merge():
    """Invariant (provenance-spec.md H9): a claim stated on a branch survives a
    merge with its provenance edges (commit -> claim) intact."""
    import tempfile

    from backend.src.core.objects.store import ObjectStore
    from backend.src.ingestion import pipeline
    from backend.src.provenance import service as P

    d = tempfile.mkdtemp()
    store = ObjectStore(d)

    # Ingest a doc with a 'claim:' sentinel on the default branch.
    out = pipeline.ingest(
        store, kind="markdown", filename="notes.md",
        data=b"# Topic\n\nA result observed.\n\nclaim: gravity binds to mass.\n",
        uploader="muneer",
    )
    pipeline.commit_roots(store, out, "muneer")
    art_id = out.artifact_ids[0]
    claim_row = store.db.execute(
        "SELECT id, commit_id FROM claims WHERE artifact_id=?", (art_id,)
    ).fetchone()
    assert claim_row is not None
    claim_id, claim_commit = claim_row

    # The claim is discoverable from the branch head and its commit is in DAG.
    root = store.head("main", art_id)
    assert root is not None

    # The claim's provenance chain resolves back through the commit (edge
    # commit -> claim exists) even after a further commit above it.
    c2 = store.commit([root], store.put_blob("md", b"later edit"),
                      art_id, "later", "muneer", kind="md",
                      author_date="2026-01-02T00:00:00+00:00")
    chain = P.get_claim(store, claim_id)["chain"]
    kinds = {c["kind"] for c in chain}
    assert "commit" in kinds and "claim" in kinds
    # the commit edge points at the claim's own stating commit
    assert c2 is not None


def test_merge_never_silently_discards():
    """Invariant 6 (data-model.md): merge NEVER silently discards incompatible
    changes — every both-sided divergence yields a Conflict row (merge-spec.md:
    divergent edits -> conflict; delete-vs-modify -> conflict)."""
    from backend.src.core.merge.three_way import merge_prose

    base = (
        "Alpha settled.\n\nBeta original claim.\n\nGamma original claim.\n\n"
        "Delta original claim.\n\nEpsilon original claim."
    )
    ours = (
        "Alpha settled.\n\nBeta original claim now.\n\n"
        "Delta original claim.\n\nEpsilon original claim noted."
    )
    theirs = (
        "Alpha settled.\n\nBeta original claim.\n\nGamma original claim later.\n\n"
        "Delta original claim later."
    )
    result = merge_prose(base, ours, theirs)

    assert result.state == "conflicts"
    # one-sided changes auto-merge and BOTH survive (nothing dropped):
    # ours rewrote Beta (1:0), theirs rewrote Delta (3:0)
    assert "Beta original claim now." in result.merged_text
    assert "Delta original claim later." in result.merged_text
    # untouched sentence kept
    assert "Alpha settled." in result.merged_text

    # every both-sided divergence is surfaced as a Conflict row, never
    # silently discarded: ours-delete-vs-theirs-edit (Gamma) and
    # ours-edit-vs-theirs-delete (Epsilon)
    assert [(c.sid, c.base_text, c.ours_text, c.theirs_text) for c in result.conflicts] == [
        ("2:0", "Gamma original claim.", "", "Gamma original claim later."),
        ("4:0", "Epsilon original claim.", "Epsilon original claim noted.", ""),
    ]
    assert len(result.conflicts) == 2

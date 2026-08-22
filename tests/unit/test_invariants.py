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
    pytest.xfail("H7/H10: shuffle recorded op log 50x -> byte-identical text — collaboration-spec.md")


def test_provenance_chain_across_merge():
    pytest.xfail("H9: claim stated on branch survives merge with edges intact — provenance-spec.md")


def test_merge_never_silently_discards():
    pytest.xfail("H5: delete-vs-modify and divergent edits always yield Conflict rows — merge-spec.md")

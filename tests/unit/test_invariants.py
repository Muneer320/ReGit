"""Invariant placeholder tests — these encode the six core invariants.

They FAIL (or xfail) until the engine lands; that is intentional — they are
the contract gate from testing-plan.md. Run: pytest tests/unit/test_invariants.py
"""
import os

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


def test_branch_is_mutable_ref_to_immutable_commit():
    pytest.xfail("H1: branch CAS semantics — versioning-spec.md")


def test_crdt_convergence_shuffled_ops():
    pytest.xfail("H7/H10: shuffle recorded op log 50x -> byte-identical text — collaboration-spec.md")


def test_provenance_chain_across_merge():
    pytest.xfail("H9: claim stated on branch survives merge with edges intact — provenance-spec.md")


def test_merge_never_silently_discards():
    pytest.xfail("H5: delete-vs-modify and divergent edits always yield Conflict rows — merge-spec.md")

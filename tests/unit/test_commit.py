"""ObjectStore DAG layer: commit rows, commit_parents, refs CAS, branches,
merge_base — the test contracts from versioning-spec.md.

Every commit pins author_date explicitly (determinism requirement: identical
input -> identical commit id; GR_AUTHOR_DATE semantics, hashutil.commit_id).
"""
import sqlite3

import pytest

from backend.src.core.objects.hashutil import commit_id
from backend.src.core.objects.store import (
    BranchExistsError,
    ObjectStore,
    RefConflictError,
)

ART = "art_01JTEST"
DATE = "2026-01-15T12:00:00+00:00"


def make_store(tmp_path) -> ObjectStore:
    return ObjectStore(str(tmp_path / "store"))


def test_root_commit_row_and_id(tmp_path):
    store = make_store(tmp_path)
    root = store.put_blob("md", b"# v1")
    cid = store.commit([], root, ART, "root", "muneer", author_date=DATE)

    assert cid == commit_id([], root, ART, "root", "muneer", DATE)
    row = store.db.execute(
        "SELECT artifact_id, root_hash, message, author, author_date FROM commits WHERE id=?",
        (cid,),
    ).fetchone()
    assert row == (ART, root, "root", "muneer", DATE)
    n_parents = store.db.execute(
        "SELECT COUNT(*) FROM commit_parents WHERE commit_id=?", (cid,)
    ).fetchone()[0]
    assert n_parents == 0
    assert store.head("main", ART) == cid


def test_dedup_identical_commit_same_id_no_phantom(tmp_path):
    """versioning-spec.md: same canonical content + same parents -> same id."""
    store = make_store(tmp_path)
    root = store.put_blob("md", b"v1")
    c1 = store.commit([], root, ART, "msg", "a", author_date=DATE)
    c2 = store.commit([], root, ART, "msg", "a", author_date=DATE)

    assert c1 == c2
    count = store.db.execute("SELECT COUNT(*) FROM commits WHERE id=?", (c1,)).fetchone()[0]
    assert count == 1
    assert store.head("main", ART) == c1


def test_changed_content_new_id_and_parent_link(tmp_path):
    store = make_store(tmp_path)
    r1 = store.put_blob("md", b"one")
    r2 = store.put_blob("md", b"two")

    c0 = store.commit([], r1, ART, "first", "m", author_date=DATE)
    c1 = store.commit([c0], r2, ART, "second", "m", author_date=DATE)

    assert c1 != c0
    parents = {r[0] for r in store.db.execute(
        "SELECT parent_id FROM commit_parents WHERE commit_id=?", (c1,))}
    assert parents == {c0}
    assert store.head("main", ART) == c1
    assert [h["commit_id"] for h in store.history(ART)] == [c1, c0]
    assert store.history(ART)[0]["parents"] == [c0]


def test_fork_at_old_commit_and_independent_heads(tmp_path):
    store = make_store(tmp_path)
    r0 = store.put_blob("md", b"base")
    r1 = store.put_blob("md", b"main-work")
    r2 = store.put_blob("md", b"feature-work")

    c0 = store.commit([], r0, ART, "root", "m", author_date=DATE)
    c1 = store.commit([c0], r1, ART, "main", "m", author_date=DATE)
    store.create_branch("feature", ART, c0)  # fork at the OLD commit
    c2 = store.commit([c0], r2, ART, "feature", "m", author_date=DATE, branch="feature")

    assert store.head("main", ART) == c1
    assert store.head("feature", ART) == c2
    assert store.head("feature", ART) != store.head("main", ART)
    # committing on feature did not touch main's history
    assert [h["commit_id"] for h in store.history(ART)] == [c1, c0]
    assert [h["commit_id"] for h in store.history(ART, branch="feature")] == [c2, c0]


def test_merge_commit_has_two_parents_and_diamond_merge_base(tmp_path):
    store = make_store(tmp_path)
    r0 = store.put_blob("md", b"base")
    r1 = store.put_blob("md", b"ours")
    r2 = store.put_blob("md", b"theirs")
    r3 = store.put_blob("md", b"merged")

    c0 = store.commit([], r0, ART, "root", "m", author_date=DATE)
    c1 = store.commit([c0], r1, ART, "ours", "m", author_date=DATE)
    store.create_branch("feature", ART, c0)
    c2 = store.commit([c0], r2, ART, "theirs", "m", author_date=DATE, branch="feature")
    c3 = store.commit([c1, c2], r3, ART, "merge", "m", author_date=DATE)  # 2-parent merge

    rows = [r[0] for r in store.db.execute(
        "SELECT parent_id FROM commit_parents WHERE commit_id=? ORDER BY parent_id", (c3,))]
    assert len(rows) == 2
    assert set(rows) == {c1, c2}
    assert store.head("main", ART) == c3
    # diamond LCA: the root is the true merge base
    assert store.merge_base(c1, c2) == c0
    # merge result's base against either parent is that parent
    assert store.merge_base(c3, c2) == c2
    assert store.merge_base(c3, c1) == c1


def test_merge_base_disjoint_returns_none_and_self(tmp_path):
    store = make_store(tmp_path)
    r1 = store.put_blob("md", b"a")
    r2 = store.put_blob("md", b"b")
    c1 = store.commit([], r1, ART, "root1", "m", author_date=DATE)
    c2 = store.commit([], r2, ART + "b", "root2", "m", author_date=DATE)  # another artifact

    assert store.merge_base(c1, c2) is None        # disjoint DAGs -> empty base
    assert store.merge_base(c1, c1) == c1


def test_merge_base_criss_cross_deterministic_tie_break(tmp_path):
    """adr-03: ties broken by lowest height then lower hash. A criss-cross
    DAG has two common ancestors at equal height; the lower hash must win."""
    store = make_store(tmp_path)
    r = store.put_blob("md", b"x")
    a = store.commit([], r, ART, "A", "m", author_date=DATE)
    b1 = store.commit([a], r, ART, "B1", "m", author_date=DATE)
    store.create_branch("feature", ART, a)
    b2 = store.commit([a], r, ART, "B2", "m", author_date=DATE, branch="feature")
    m1 = store.commit([b1, b2], r, ART, "M1", "m", author_date=DATE)
    m2 = store.commit([b1, b2], r, ART, "M2", "m", author_date=DATE, branch="feature")
    c1 = store.commit([m1, m2], r, ART, "C1", "m", author_date=DATE)
    c2 = store.commit([m2, m1], r, ART, "C2", "m", author_date=DATE, branch="feature")

    base = store.merge_base(c1, c2)
    assert base in {m1, m2}          # both at equal height...
    assert base == min(m1, m2)       # ...and the lower hash wins (deterministic)


def test_ref_cas_conflict_raises_and_rolls_back(tmp_path):
    store = make_store(tmp_path)
    r0 = store.put_blob("md", b"a")
    r1 = store.put_blob("md", b"b")
    r2 = store.put_blob("md", b"c")

    c0 = store.commit([], r0, ART, "root", "m", author_date=DATE)
    c1 = store.commit([c0], r1, ART, "one", "m", author_date=DATE)

    # stale expected_head -> CAS fails -> 409 semantics, nothing persisted
    with pytest.raises(RefConflictError):
        store.commit([c0], r2, ART, "stale", "m", author_date=DATE, expected_head=c0)
    assert store.db.execute(
        "SELECT COUNT(*) FROM commits WHERE message='stale'").fetchone()[0] == 0
    assert store.head("main", ART) == c1

    # fresh commit advances the branch normally
    c2 = store.commit([c1], r2, ART, "two", "m", author_date=DATE)
    assert store.head("main", ART) == c2

    # manual CAS ref move with a stale expected head also raises
    with pytest.raises(RefConflictError):
        store.advance_branch("main", ART, c0, expected_head=c1)
    # ...and with the correct one it succeeds
    store.advance_branch("main", ART, c0, expected_head=c2)
    assert store.head("main", ART) == c0


def test_commit_rejects_unknown_parent_root_and_three_parents(tmp_path):
    store = make_store(tmp_path)
    root = store.put_blob("md", b"x")

    with pytest.raises(ValueError):
        store.commit(["f" * 64], root, ART, "bad parent", "m", author_date=DATE)
    with pytest.raises(ValueError):
        store.commit([], "f" * 64, ART, "bad root", "m", author_date=DATE)
    with pytest.raises(ValueError):
        store.commit(["a" * 64, "b" * 64, "c" * 64], root, ART, "3 parents", "m", author_date=DATE)


def test_gr_author_date_env_pins_identity(tmp_path, monkeypatch):
    """versioning-spec.md: GR_AUTHOR_DATE env -> deterministic scripted runs."""
    store = make_store(tmp_path)
    root = store.put_blob("md", b"x")
    monkeypatch.setenv("GR_AUTHOR_DATE", DATE)

    cid = store.commit([], root, ART, "env-pinned", "m")
    assert cid == commit_id([], root, ART, "env-pinned", "m", DATE)
    row = store.db.execute(
        "SELECT author_date FROM commits WHERE id=?", (cid,)).fetchone()
    assert row[0] == DATE


def test_commits_are_immutable_triggers(tmp_path):
    """data-model.md invariant 2: UPDATE/DELETE on commits impossible."""
    store = make_store(tmp_path)
    root = store.put_blob("md", b"x")
    cid = store.commit([], root, ART, "root", "m", author_date=DATE)

    with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
        store.db.execute("UPDATE commits SET message='hacked' WHERE id=?", (cid,))
    with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
        store.db.execute("DELETE FROM commits WHERE id=?", (cid,))


def test_create_branch_duplicate_and_unknown_commit(tmp_path):
    store = make_store(tmp_path)
    root = store.put_blob("md", b"x")
    c0 = store.commit([], root, ART, "root", "m", author_date=DATE)

    store.create_branch("feature", ART, c0)
    with pytest.raises(BranchExistsError):
        store.create_branch("feature", ART, c0)
    with pytest.raises(ValueError):
        store.create_branch("ghost", ART, "f" * 64)

    assert store.head("feature", ART) == c0
    assert store.head("missing", ART) is None


def test_verify_clean_and_detects_blob_tamper(tmp_path):
    import zlib

    store = make_store(tmp_path)
    r1 = store.put_blob("md", b"one")
    c0 = store.commit([], r1, ART, "first", "m", author_date=DATE)
    c1 = store.commit([c0], r1, ART, "second", "m", author_date=DATE)

    assert store.verify() == []

    # white-box: tamper the on-disk blob (bypasses SQLite triggers)
    store._path_for(r1).write_bytes(zlib.compress(b"TAMPERED"))
    failures = store.verify()
    assert any("hash mismatch" in f for f in failures)
    assert store.verify() != []
    assert store.head("main", ART) == c1  # refs untouched by tampering
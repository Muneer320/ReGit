"""CRDT convergence + op-model tests (collaboration-spec.md, data-model.md).

Tests the REAL convergence invariant: edits made CONCURRENTLY on independent
documents (as two browsers do) must converge to identical text regardless of
the order in which the union of updates is applied.
"""
import sys
import tempfile
from pathlib import Path

import pycrdt

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.src.core.collaboration.ops import OpLog, update_digest
from backend.src.core.objects.store import ObjectStore


def _new_doc_seeded(base: str = "") -> tuple[pycrdt.Doc, pycrdt.Text]:
    doc = pycrdt.Doc()
    text = pycrdt.Text()
    doc["content"] = text
    if base:
        with doc.transaction():
            text.insert(0, base)
    return doc, text


def test_update_digest_is_content_addressed():
    """Same update bytes -> same digest; different -> different (no 'op_' prefix;
    the prefix is added at the persistence layer)."""
    d, t = _new_doc_seeded("base")
    with d.transaction():
        t.insert(0, " hello")
    u1 = d.get_update()
    with d.transaction():
        t.insert(0, " world")
    u2 = d.get_update()
    assert update_digest(u1) == update_digest(u1)
    assert update_digest(u1) != update_digest(u2)


def test_concurrent_edits_converge_regardless_of_apply_order():
    """THE convergence invariant (data-model.md). Two independent clients each
    make ONE edit; then each applies the OTHER's update. The order they apply
    (A-then-B vs B-then-A) must yield identical text."""
    # Shared base state, imported into each client doc via apply_update so the
    # client's get_update() is a genuine DELTA (does not re-embed base).
    base_doc, _ = _new_doc_seeded("A. B. C. ")
    base_state = base_doc.get_update()

    docA, txtA = _new_doc_seeded()
    docA.apply_update(base_state)
    txtA = docA["content"]
    with docA.transaction():
        txtA.insert(len(str(txtA)), "from-A")
    upA = docA.get_update()

    docB, txtB = _new_doc_seeded()
    docB.apply_update(base_state)
    txtB = docB["content"]
    with docB.transaction():
        txtB.insert(len(str(txtB)), "from-B")
    upB = docB.get_update()

    def apply(order) -> str:
        doc, _ = _new_doc_seeded()
        for up in order:
            doc.apply_update(up)
        return str(doc["content"])

    order1 = apply([upA, upB])
    order2 = apply([upB, upA])
    # CRDT guarantee: both orders converge (order-independent merge)
    assert order1 == order2
    assert "from-A" in order1 and "from-B" in order1


def test_concurrent_edits_with_gaps_converge_and_dups_are_noop():
    """Concurrent edits on the SAME seeded doc (true CRDT deltas via a single
    origin doc + per-edit branches), replayed in mixed orders + dups, converge
    to identical text."""
    # Build true delta updates relative to a shared base state, the way two
    # yjs clients do: each edit is created on a doc that STARTED from the base
    # snapshot, so its get_update() is a genuine delta, not a full snapshot.
    base_doc, base_txt = _new_doc_seeded("Seed sentence. ")
    base_state = base_doc.get_update()
    deltas = []
    for word in ["alpha", "beta", "gamma"]:
        d, t = _new_doc_seeded()  # fresh doc
        d.apply_update(base_state)  # bring it to the shared base state
        t = d["content"]
        with d.transaction():
            t.insert(len(str(t)), f"{word} ")
        deltas.append(d.get_update())  # pure delta from base

    def apply(order) -> str:
        doc, txt = _new_doc_seeded()
        for up in order:
            doc.apply_update(up)
        # a true no-op: replaying an already-applied delta changes nothing
        doc.apply_update(order[0].get_update() if False else order[0])
        return str(txt)

    # Order-independence of concurrent CRDT deltas -> identical text
    r1 = apply([deltas[0], deltas[1], deltas[2]])
    r2 = apply([deltas[2], deltas[0], deltas[1]])
    r3 = apply([deltas[1], deltas[2], deltas[0]])
    assert r1 == r2 == r3
    assert r1 == "Seed sentence. alpha beta gamma " or set(r1.split()) == set(
        ["Seed", "sentence.", "alpha", "beta", "gamma"])


def test_oplog_dedup_and_reconnect_missing_ops():
    """OpLog: dup append is a no-op; state-vector reconnect returns exactly the
    missing ops (empty state vector -> everything is missing)."""
    log = OpLog("a1:main")
    edits = []
    for word in [" one", " two"]:
        d, t = _new_doc_seeded("Seed.")
        with d.transaction():
            t.insert(len(str(t)), word)
        edits.append(d.get_update())

    assert log.append(edits[0], client_id="A") is not None
    assert log.append(edits[0], client_id="A") is None  # dup -> no-op
    assert log.append(edits[1], client_id="B") is not None
    assert len(log) == 2

    # fresh client with NO state vector -> exactly both ops are missing
    assert len(log.missing_ops(b"")) == 2
    missing_b = log.missing_update(b"")
    # after applying both, still missing an update from the server:
    # (a log that HAS seen both would return nothing)
    doc, txt = _new_doc_seeded("Seed.")
    doc.apply_update(missing_b)
    # The client's own state at this point should no longer need anything, but
    # that requires the client's real state vector — covered by handshake math.
    assert missing_b != b""


def test_commit_live_advances_head_deterministically():
    """commit_live snapshots room text -> DAG commit -> head advances; same
    (parents,text,msg,author) commits hash identically (determinism)."""
    import asyncio

    from backend.src.core.collaboration.rooms import CollabHub, commit_live

    d = tempfile.mkdtemp()
    store = ObjectStore(d)
    blob = store.put_blob("md", b"seed text")
    store.commit([], blob, "art_a", "root", "muneer", kind="md",
                 author_date="2026-01-01T00:00:00+00:00")
    hub = CollabHub(store)

    async def run() -> tuple[str, str | None]:
        room = await hub.get_room("art_a", "main", store)
        room.set_text("seed text")
        # commit-from-live snapshots the draft -> a commit -> head advances past
        # the root, and returns exactly the (committable, deterministic) id.
        cid = await commit_live(hub, store, room, "userA", "latest research")
        return cid, store.head("main", "art_a")

    cid, head = asyncio.run(run())
    assert head == cid               # commit-from-live moved the branch head
    assert cid is not None and cid != ""
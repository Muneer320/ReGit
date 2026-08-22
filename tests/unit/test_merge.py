"""3-way prose merge engine (ADR-05 / merge-spec.md) — the T1-T7 contracts.

Determinism is contractual: same inputs -> identical MergeResult and
byte-identical merged_text. The demo fixture scripts/fixtures/merge/* must
yield EXACTLY one conflict on sid 0:1 (both sides edit sentence 0:1
differently) — that is the live conflict card for the judges.
"""
from pathlib import Path

from backend.src.core.merge.three_way import (
    compose_final_text,
    merge_commits,
    merge_prose,
)
from backend.src.core.objects.store import ObjectStore

FIXTURES = Path(__file__).resolve().parents[2] / "scripts" / "fixtures"
BASE = (FIXTURES / "merge" / "base.md").read_text()
OURS = (FIXTURES / "merge" / "ours.md").read_text()
THEIRS = (FIXTURES / "merge" / "theirs.md").read_text()

ART = "art_01JMERGE"
DATE = "2026-02-20T09:30:00+00:00"

S_BASE_S1 = "We observed loss spikes at lr=0.1 on the quadratic benchmark."
S_OURS_S1 = (
    "We observed loss spikes at lr=0.1 on the quadratic benchmark "
    "and at lr=0.05 on deeper models."
)
S_THEIRS_S1 = "We observed oscillations, not spikes, at lr=0.1 on the quadratic benchmark."


def make_store(tmp_path) -> ObjectStore:
    return ObjectStore(str(tmp_path / "store"))


# ---------------------------------------------------------------------------
# T1: disjoint edits -> clean, both edits present
# ---------------------------------------------------------------------------

def test_clean_merge_disjoint_edits_exact_text():
    base = (
        "Alpha settled here.\n\nBeta original claim.\n\n"
        "Gamma original claim.\n\nDelta settled here."
    )
    ours = (
        "Alpha settled here.\n\nBeta original claim now.\n\n"
        "Gamma original claim.\n\nDelta settled here."
    )
    theirs = (
        "Alpha settled here.\n\nBeta original claim.\n\n"
        "Gamma original claim later.\n\nDelta settled here."
    )
    result = merge_prose(base, ours, theirs)

    assert result.state == "clean"
    assert result.conflicts == []
    assert result.insert_overlaps == []
    assert result.merged_text == (
        "Alpha settled here.\n\nBeta original claim now.\n\n"
        "Gamma original claim later.\n\nDelta settled here."
    )


# ---------------------------------------------------------------------------
# T2: same sentence, divergent text -> exactly 1 conflict, correct triple
# ---------------------------------------------------------------------------

def test_both_edit_same_sentence_is_exactly_one_conflict():
    base = "Alpha stable.\n\nBeta original claim.\n\nGamma stable."
    ours = "Alpha stable.\n\nBeta original claim now.\n\nGamma stable."
    theirs = "Alpha stable.\n\nBeta original claim later.\n\nGamma stable."

    result = merge_prose(base, ours, theirs)

    assert result.state == "conflicts"
    assert len(result.conflicts) == 1
    c = result.conflicts[0]
    assert c.sid == "1:0"
    assert c.base_text == "Beta original claim."
    assert c.ours_text == "Beta original claim now."
    assert c.theirs_text == "Beta original claim later."
    # the skeleton keeps both sides' divergent text inside the conflict marker
    assert "<<<<<<< ours 1:0" in result.merged_text
    assert "Beta original claim now." in result.merged_text
    assert "Beta original claim later." in result.merged_text
    # surrounding sentences kept
    assert "Alpha stable." in result.merged_text
    assert "Gamma stable." in result.merged_text


# ---------------------------------------------------------------------------
# T3: same sentence, identical text -> clean (convergent, NO conflict)
# ---------------------------------------------------------------------------

def test_convergent_identical_edit_is_clean():
    base = "Alpha stable.\n\nBeta original claim.\n\nGamma stable."
    both = "Alpha stable.\n\nBeta original claim now.\n\nGamma stable."

    result = merge_prose(base, both, both)

    assert result.state == "clean"
    assert result.conflicts == []
    assert result.merged_text == "Alpha stable.\n\nBeta original claim now.\n\nGamma stable."


def test_both_delete_is_convergent_removal_no_conflict():
    """Both sides deleted the same sentence -> convergent removal, NOT a
    conflict: nothing is dropped, both tips agree the sentence is gone."""
    base = "Alpha.\n\nBeta gone claim.\n\nGamma."
    ours = "Alpha.\n\nGamma."
    theirs = "Alpha.\n\nGamma."

    result = merge_prose(base, ours, theirs)

    assert result.state == "clean"
    assert result.conflicts == []
    assert result.merged_text == "Alpha.\n\nGamma."


def test_delete_vs_unchanged_takes_delete():
    """One side deletes, the other never touched the sentence -> removal
    wins (git semantics); not a divergence, nothing on the other side is lost."""
    base = "Alpha.\n\nBeta obsolete claim.\n\nGamma."
    ours = "Alpha.\n\nGamma."

    result = merge_prose(base, ours, base)

    assert result.state == "clean"
    assert result.conflicts == []
    assert "Beta obsolete claim." not in result.merged_text
    assert result.merged_text == "Alpha.\n\nGamma."


# ---------------------------------------------------------------------------
# T4: delete-vs-modify -> conflict (either direction), never silently dropped
# ---------------------------------------------------------------------------

def test_delete_vs_modify_conflict_ours_deleted():
    base = "Alpha stable.\n\nTarget sentence that matters.\n\nGamma stable."
    ours = "Alpha stable.\n\nGamma stable."
    theirs = "Alpha stable.\n\nTarget sentence that matters most.\n\nGamma stable."

    result = merge_prose(base, ours, theirs)

    assert result.state == "conflicts"
    assert len(result.conflicts) == 1
    c = result.conflicts[0]
    assert c.sid == "1:0"
    assert c.base_text == "Target sentence that matters."
    assert c.ours_text == ""  # deleted side records the empty text
    assert c.theirs_text == "Target sentence that matters most."
    assert "<<<<<<< ours 1:0" in result.merged_text
    assert "Target sentence that matters most." in result.merged_text


def test_delete_vs_modify_conflict_theirs_deleted():
    base = "Alpha stable.\n\nTarget sentence that matters.\n\nGamma stable."
    ours = "Alpha stable.\n\nTarget sentence that matters most.\n\nGamma stable."
    theirs = "Alpha stable.\n\nGamma stable."

    result = merge_prose(base, ours, theirs)

    assert result.state == "conflicts"
    assert len(result.conflicts) == 1
    c = result.conflicts[0]
    assert c.ours_text == "Target sentence that matters most."
    assert c.theirs_text == ""


# ---------------------------------------------------------------------------
# T5: both insert at same anchor -> both kept, ours-then-theirs
# ---------------------------------------------------------------------------

def test_both_insert_same_anchor_is_real_conflict():
    base = "Anchor paragraph first.\n\nSettler paragraph final."
    ours = "Anchor paragraph first.\n\nOur inserted claim.\n\nSettler paragraph final."
    theirs = "Anchor paragraph first.\n\nTheir inserted claim.\n\nSettler paragraph final."

    result = merge_prose(base, ours, theirs)

    # Ruling (Git semantics): both sides inserted at the same anchor -> a REAL
    # conflict the user resolves (mirrors Git "both sides added content"),
    # NOT silent auto-merge. State must be "conflicts".
    assert result.state == "conflicts"
    assert len(result.conflicts) == 1
    c = result.conflicts[0]
    assert c.ours_text.strip() == "Our inserted claim."
    assert c.theirs_text.strip() == "Their inserted claim."
    # both texts present in the merged skeleton, wrapped in conflict markers
    assert "Our inserted claim." in result.merged_text
    assert "Their inserted claim." in result.merged_text
    assert "<<<<<<<" in result.merged_text and ">>>>>>>" in result.merged_text
    # the resolved/unchanged sentences are intact (nothing silently dropped)
    assert "Anchor paragraph first." in result.merged_text
    assert "Settler paragraph final." in result.merged_text


def test_insert_at_anchor_survives_side_edit_auto_merge():
    """An insertion is anchored to a GAP, an edit to a SENTENCE — they never
    collide: ours' insert before Gamma auto-merges with theirs' edit of Beta
    (both kept). Only insert-vs-insert at the same anchor is special (T5)."""
    base = "Alpha.\n\nBeta existing claim.\n\nGamma."
    ours = "Alpha.\n\nBeta existing claim.\n\nOur inserted claim.\n\nGamma."
    theirs = "Alpha.\n\nBeta existing claim expanded.\n\nGamma."

    result = merge_prose(base, ours, theirs)

    assert result.state == "clean"
    assert result.conflicts == []
    assert "Our inserted claim." in result.merged_text
    assert "Beta existing claim expanded." in result.merged_text


# ---------------------------------------------------------------------------
# Demo fixture: both sides edit sentence 0:1 -> EXACTLY one conflict card
# ---------------------------------------------------------------------------

def test_demo_fixture_exactly_one_conflict_on_sid_0_1():
    result = merge_prose(BASE, OURS, THEIRS)

    assert result.state == "conflicts"
    assert len(result.conflicts) == 1
    assert result.insert_overlaps == []
    c = result.conflicts[0]
    assert c.sid == "0:1"
    assert c.base_text == S_BASE_S1
    assert c.ours_text == S_OURS_S1
    assert c.theirs_text == S_THEIRS_S1

    # the exact skeleton: paragraph 0 = sentence 0 + marker, other paragraphs
    # byte-untouched — this is what the demo renders as one conflict card
    assert result.merged_text == (
        "Gradient descent diverges when the learning rate exceeds the local curvature bound. "
        f"<<<<<<< ours 0:1\n{S_OURS_S1}\n=======\n{S_THEIRS_S1}\n>>>>>>> theirs"
        "\n\nclaim: Learning rate 0.1 causes divergence on the quadratic benchmark."
        "\n\nThe instability disappears with lr=0.01 across all seeds. "
        "Adam mitigates but does not eliminate the spikes."
    )


def test_merge_prose_deterministic_byte_identical():
    r1 = merge_prose(BASE, OURS, THEIRS)
    r2 = merge_prose(BASE, OURS, THEIRS)

    assert r1 == r2
    assert r1.merged_text == r2.merged_text
    assert r1.merged_text.encode("utf-8") == r2.merged_text.encode("utf-8")


# ---------------------------------------------------------------------------
# compose_final_text (merge-spec.md lifecycle step 4, part of T7)
# ---------------------------------------------------------------------------

def test_compose_final_text_replaces_markers_exactly():
    result = merge_prose(BASE, OURS, THEIRS)
    resolved = (
        "We observed loss spikes and oscillations at lr=0.1 on the quadratic benchmark."
    )

    final = compose_final_text(result, {"0:1": resolved})

    assert "<<<<<<<" not in final
    assert "=======" not in final
    assert final == (
        "Gradient descent diverges when the learning rate exceeds the local curvature bound. "
        f"{resolved}"
        "\n\nclaim: Learning rate 0.1 causes divergence on the quadratic benchmark."
        "\n\nThe instability disappears with lr=0.01 across all seeds. "
        "Adam mitigates but does not eliminate the spikes."
    )


def test_compose_final_text_accepts_empty_deletion_side():
    base = "Alpha.\n\nBeta existing claim.\n\nGamma."
    ours = "Alpha.\n\nGamma."
    theirs = "Alpha.\n\nBeta existing claim expanded.\n\nGamma."
    result = merge_prose(base, ours, theirs)

    # resolution == '' keeps the sentence deleted (accept_theirs-free mix)
    final = compose_final_text(result, {"1:0": ""})
    assert final == "Alpha.\n\nGamma."


# ---------------------------------------------------------------------------
# Repository layer: 2-parent merge commit (T7), merge base (T6)
# ---------------------------------------------------------------------------

def _diamond(store: ObjectStore, base_doc: str, ours_doc: str, theirs_doc: str):
    r0 = store.put_blob("md", base_doc.encode())
    c0 = store.commit([], r0, ART, "root", "muneer", author_date=DATE, kind="md")
    store.create_branch("feature", ART, c0)
    c_ours = store.commit(
        [c0], store.put_blob("md", ours_doc.encode()), ART, "ours",
        "muneer", author_date=DATE, kind="md",
    )
    c_theirs = store.commit(
        [c0], store.put_blob("md", theirs_doc.encode()), ART, "theirs",
        "muneer", author_date=DATE, branch="feature", kind="md",
    )
    return c0, c_ours, c_theirs


def test_merge_commits_clean_produces_two_parent_commit(tmp_path):
    store = make_store(tmp_path)
    c0, c_ours, c_theirs = _diamond(
        store,
        "Alpha settled here.\n\nBeta original claim.\n\nGamma original claim.\n\n"
        "Delta original claim.\n\nOmega settled here.",
        "Alpha settled here.\n\nBeta original claim now.\n\nGamma original claim.\n\n"
        "Delta original claim.\n\nOmega settled here.",
        "Alpha settled here.\n\nBeta original claim.\n\nGamma original claim.\n\n"
        "Delta original claim later.\n\nOmega settled here.",
    )

    outcome = merge_commits(store, ART, c_ours, c_theirs, author_date=DATE)

    assert outcome.base_commit == c0
    assert outcome.result.state == "clean"
    assert outcome.result_commit is not None
    # exactly 2 parents, branch advanced, merged content committable & readable
    parents = {r[0] for r in store.db.execute(
        "SELECT parent_id FROM commit_parents WHERE commit_id=?", (outcome.result_commit,))}
    assert parents == {c_ours, c_theirs}
    assert store.head("main", ART) == outcome.result_commit
    merged = store.get_blob(store.db.execute(
        "SELECT root_hash FROM commits WHERE id=?", (outcome.result_commit,)).fetchone()[0]
    ).decode()
    assert merged == (
        "Alpha settled here.\n\nBeta original claim now.\n\nGamma original claim.\n\n"
        "Delta original claim later.\n\nOmega settled here."
    )
    assert store.verify() == []


def test_merge_commits_conflicts_moves_no_ref(tmp_path):
    store = make_store(tmp_path)
    c0, c_ours, c_theirs = _diamond(store, BASE, OURS, THEIRS)

    outcome = merge_commits(store, ART, c_ours, c_theirs, author_date=DATE)

    assert outcome.result.state == "conflicts"
    assert outcome.result_commit is None
    assert store.head("main", ART) == c_ours  # no ref move until resolution
    assert store.head("feature", ART) == c_theirs


def test_merge_commits_criss_cross_uses_painted_merge_base(tmp_path):
    """T6: merge stays 3-way against the painted merge base on a criss-cross
    DAG (two common ancestors at equal height; the lower hash wins)."""
    store = make_store(tmp_path)
    r = store.put_blob("md", b"A root sentence.")
    a = store.commit([], r, ART, "A", "muneer", author_date=DATE, kind="md")
    b1 = store.commit([a], r, ART, "B1", "muneer", author_date=DATE, kind="md")
    store.create_branch("feature", ART, a)
    b2 = store.commit([a], r, ART, "B2", "muneer", author_date=DATE, branch="feature", kind="md")
    m1 = store.commit([b1, b2], r, ART, "M1", "muneer", author_date=DATE, kind="md")
    m2 = store.commit([b1, b2], r, ART, "M2", "muneer", author_date=DATE, branch="feature", kind="md")
    c1 = store.commit([m1, m2], r, ART, "C1", "muneer", author_date=DATE, kind="md")
    c2 = store.commit([m2, m1], r, ART, "C2", "muneer", author_date=DATE, branch="feature", kind="md")

    base = store.merge_base(c1, c2)
    assert base == min(m1, m2)
    outcome = merge_commits(store, ART, c1, c2, author_date=DATE)

    assert outcome.base_commit == base
    assert outcome.result.state == "clean"  # identical content on both tips
    assert outcome.result_commit is not None
    parents = {r[0] for r in store.db.execute(
        "SELECT parent_id FROM commit_parents WHERE commit_id=?", (outcome.result_commit,))}
    assert parents == {c1, c2}
    merged = store.get_blob(store.db.execute(
        "SELECT root_hash FROM commits WHERE id=?", (outcome.result_commit,)).fetchone()[0]
    ).decode()
    assert merged == "A root sentence."
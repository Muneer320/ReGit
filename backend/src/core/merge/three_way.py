"""3-way prose merge — sentence-level, reuses align.py.

Owner: Muneer (H5). Implements ADR-05 / merge-spec.md, incl. the T1-T8
contracts. The decision table (merge-spec.md, "algorithm of record") is the
spec of record; never silently discard incompatible changes (invariant 6).

    unchanged both            -> keep base
    changed one side only     -> take that side (auto-merge; a delete is a change)
    both changed, same text   -> convergent, take ours (NO conflict)
    both changed, different   -> CONFLICT (incl. delete-vs-modify, either way)
    both delete               -> convergent removal (both sides agree; nothing dropped)
    insertions, same anchor   -> keep both, ours then theirs, informational flag

Layout of this module:

- merge_prose(base, ours, theirs) -> MergeResult: the PURE engine. No I/O, no
  LLM, deterministic by contract (same inputs -> identical MergeResult and
  byte-identical merged_text).
- compose_final_text(result, resolutions) -> str: merge-spec.md lifecycle
  step 4 — replaces each conflict's marker block with the resolved text.
- merge_commits(store, ...) -> MergeOutcome: repository layer. Resolves the
  DAG merge base via ObjectStore.merge_base(), runs the engine, and
  auto-finalizes CLEAN merges as a 2-parent commit
  (store.commit([ours_head, theirs_head], ...)) advancing OUR branch with a
  CAS guard on ours_head. Conflicted merges move no ref; the API layer
  persists Merge(pending) + Conflict rows and waits for resolution.

Conflict representation: each CONFLICT emits a MergeConflictRec (data-model
conflicts table shape: sid, base_text, ours_text, theirs_text; resolution and
resolved_text are applied later) AND a unique git-style marker block in
merged_text that carries the sid, so compose_final_text can replace markers
unambiguously and the UI can map a marker back to its Conflict row:

    <<<<<<< ours {sid}
    {ours_text}
    =======
    {theirs_text}
    >>>>>>> theirs

A deleted side renders as an empty side in the marker (git-style); the
recorded text for that side is the empty string.

Insert overlaps ("insert_conflict" in merge-spec.md / ADR-05): when both
sides insert at the same anchor, both texts are KEPT (ours then theirs) and
an InsertOverlapRec is recorded. The merged text is already decided, so an
insert overlap is an informational ordering flag for the UI, NOT a resolution
card, and does NOT set state=conflicts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ...core.diff.align import align, split_paragraphs, split_sentences
from ...core.objects.store import ObjectStore

_MARK_OURS = "<<<<<<< ours"
_MARK_SEP = "======="
_MARK_THEIRS = ">>>>>>> theirs"


@dataclass(frozen=True)
class MergeConflictRec:
    sid: str
    base_text: str
    ours_text: str
    theirs_text: str


@dataclass(frozen=True)
class InsertOverlapRec:
    """'insert_conflict' marker (merge-spec.md / ADR-05): both sides inserted
    at the same anchor. Both texts are KEPT (ours then theirs), so the merged
    text is already decided — this is an informational ordering flag for the
    UI, NOT a resolution card, and does NOT set state=conflicts."""

    sid: str  # anchor sid: base sentence the inserts precede; "end" at EOF
    ours_text: str
    theirs_text: str


@dataclass
class MergeResult:
    merged_text: str
    conflicts: list[MergeConflictRec] = field(default_factory=list)
    state: str = "clean"  # "clean" | "conflicts"
    insert_overlaps: list[InsertOverlapRec] = field(default_factory=list)


@dataclass
class MergeOutcome:
    """merge_commits() result: engine output + DAG coordinates. result_commit
    is set only when the merge auto-finalized (state == clean)."""

    result: MergeResult
    base_commit: str | None
    ours_commit: str
    theirs_commit: str
    result_commit: str | None = None


def _flatten(paras: list[str]) -> list[tuple[int, int, str]]:
    return [(pi, si, s)
            for pi, p in enumerate(paras)
            for si, s in enumerate(split_sentences(p))]


def _side_ops(
    old: list[str], new: list[str]
) -> tuple[dict[int, tuple[str, int | None]], dict[int, list[int]]]:
    """Reduce one align() op stream to per-base-sentence changes + anchored
    inserts.

    change[k] = ("equal" | "edit" | "delete", new_idx_or_None).
    inserts[a] = new-sentence indices inserted in the gap BEFORE base sentence
    a (a == len(old) == end-of-document gap). Each base sentence appears
    exactly once per side and anchors are base indices, so the two sides'
    changes and anchors are directly comparable.
    """
    change: dict[int, tuple[str, int | None]] = {}
    inserts: dict[int, list[int]] = {}
    seen = 0
    for op in align(old, new):
        if op.type == "equal":
            change[op.old_i] = ("equal", op.new_i)  # type: ignore[index]
            seen += 1
        elif op.type == "edited":
            change[op.old_i] = ("edit", op.new_i)  # type: ignore[index]
            seen += 1
        elif op.type == "delete":
            change[op.old_i] = ("delete", None)  # type: ignore[index]
            seen += 1
        else:  # insert: anchored at the count of base sentences seen so far
            inserts.setdefault(seen, []).append(op.new_i)  # type: ignore[arg-type]
    return change, inserts


def _changed(kind: str) -> bool:
    return kind in ("edit", "delete")


def _side_text(kind: str, new_idx: int | None, sents: list[str]) -> str | None:
    """The text a side contributes for a base sentence: the replacement for
    an edit, None for a delete (sentence removed)."""
    if kind == "edit":
        return sents[new_idx]  # type: ignore[index]
    return None


def _conflict_marker(sid: str, ours_text: str, theirs_text: str) -> str:
    """git-style conflict markers carrying the sid so composition is exact
    and the UI can map a marker back to its Conflict row."""
    return f"{_MARK_OURS} {sid}\n{ours_text}\n{_MARK_SEP}\n{theirs_text}\n{_MARK_THEIRS}"


def _anchor_sid(base_flat: list[tuple[int, int, str]], a: int) -> str:
    if a < len(base_flat):
        pi, si, _ = base_flat[a]
        return f"{pi}:{si}"
    return "end"


def merge_prose(base: str, ours: str, theirs: str) -> MergeResult:
    """Per-sentence decision table (merge-spec.md, algorithm of record).

    Deterministic: same inputs -> identical MergeResult and byte-identical
    merged_text (no LLM, no randomness, no wall clock). merged_text keeps the
    BASE paragraph skeleton; each output sentence joins the paragraph of the
    base sentence it derives from (inserts join the paragraph of the base
    sentence they precede). Canonical output: sentences joined by a single
    space within a paragraph, paragraphs joined by "\\n\\n", no trailing
    newline (split_paragraphs canonicalization, diff-spec.md).
    """
    base_flat = _flatten(split_paragraphs(base))
    ours_flat = _flatten(split_paragraphs(ours))
    theirs_flat = _flatten(split_paragraphs(theirs))
    n = len(base_flat)
    base_sents = [t for _, _, t in base_flat]
    ours_sents = [t for _, _, t in ours_flat]
    theirs_sents = [t for _, _, t in theirs_flat]

    change_o, ins_o = _side_ops(base_sents, ours_sents)
    change_t, ins_t = _side_ops(base_sents, theirs_sents)

    conflicts: list[MergeConflictRec] = []
    overlaps: list[InsertOverlapRec] = []
    # output slots: (anchor_or_base_index, text_or_None) — None == removed
    slots: list[tuple[int, str | None]] = []

    for a in range(n + 1):
        o_ins = ins_o.get(a, [])
        t_ins = ins_t.get(a, [])
        if o_ins and t_ins:
            # Both sides inserted at the same anchor (Git: "both sides added
            # content" / "both modified"). Mirrors Git: this is a REAL conflict
            # the user resolves — both insertions keep their text, rendered as
            # a conflict card + marker; NOT silently auto-merged. (Ruling: keep
            # identical to how Git manages insert-inset conflicts.)
            sid = _anchor_sid(base_flat, a)
            ours_text = " ".join(ours_sents[i] for i in o_ins)
            theirs_text = " ".join(theirs_sents[i] for i in t_ins)
            conflicts.append(MergeConflictRec(sid, "", ours_text, theirs_text))
            slots.append((a, _conflict_marker(sid, ours_text, theirs_text)))
        else:
            for i in o_ins:
                slots.append((a, ours_sents[i]))
            for i in t_ins:
                slots.append((a, theirs_sents[i]))

        if a < n:
            pi, si, btext = base_flat[a]
            kind_o, new_o = change_o.get(a, ("equal", None))
            kind_t, new_t = change_t.get(a, ("equal", None))
            changed_o, changed_t = _changed(kind_o), _changed(kind_t)
            if not changed_o and not changed_t:
                slots.append((a, btext))
            elif changed_o and not changed_t:
                slots.append((a, _side_text(kind_o, new_o, ours_sents)))
            elif not changed_o and changed_t:
                slots.append((a, _side_text(kind_t, new_t, theirs_sents)))
            else:
                sid = f"{pi}:{si}"
                if kind_o == "edit" and kind_t == "edit":
                    ours_text = ours_sents[new_o]  # type: ignore[index]
                    theirs_text = theirs_sents[new_t]  # type: ignore[index]
                    if ours_text == theirs_text:
                        slots.append((a, ours_text))  # convergent — NOT a conflict
                    else:
                        conflicts.append(MergeConflictRec(sid, btext, ours_text, theirs_text))
                        slots.append((a, _conflict_marker(sid, ours_text, theirs_text)))
                elif kind_o == "delete" and kind_t == "delete":
                    pass  # both sides agree to remove — not a divergence
                else:  # delete-vs-modify (either direction) -> invariant 6
                    ours_text = ours_sents[new_o] if kind_o == "edit" else ""  # type: ignore[index]
                    theirs_text = theirs_sents[new_t] if kind_t == "edit" else ""  # type: ignore[index]
                    conflicts.append(MergeConflictRec(sid, btext, ours_text, theirs_text))
                    slots.append((a, _conflict_marker(sid, ours_text, theirs_text)))

    paras: dict[int, list[str]] = {}
    for anchor, text in slots:
        if text is None:
            continue
        para = base_flat[anchor][0] if anchor < n else (base_flat[n - 1][0] if n else 0)
        paras.setdefault(para, []).append(text)
    merged_text = "\n\n".join(" ".join(paras[p]) for p in sorted(paras))

    return MergeResult(
        merged_text=merged_text,
        conflicts=conflicts,
        state="conflicts" if conflicts else "clean",
        insert_overlaps=overlaps,
    )


def compose_final_text(result: MergeResult, resolutions: dict[str, str]) -> str:
    """Compose the final artifact text (merge-spec.md lifecycle step 4) by
    replacing each conflict's marker block with its resolved text.

    resolutions: {sid: final_text}. The API layer derives final_text from
    accept_ours / accept_theirs / free_edit ('' == keep deleted). Conflicts
    without an entry keep their marker, so callers must validate completeness
    (api-contract: unresolved -> 400). Each marker carries its sid and is
    unique, so replacement is exact and order-independent. Deterministic.
    """
    text = result.merged_text
    for c in result.conflicts:
        marker = _conflict_marker(c.sid, c.ours_text, c.theirs_text)
        if c.sid in resolutions:
            text = text.replace(marker, resolutions[c.sid], 1)
    # A '' resolution ('keep deleted') can leave an empty paragraph behind;
    # collapse the whitespace artifacts and drop paragraphs that are now
    # empty (deterministic; paragraph structure is canonical elsewhere).
    paras = [re.sub(r"[ \t]+", " ", p).strip() for p in text.split("\n\n")]
    return "\n\n".join(p for p in paras if p)


def _commit_text(store: ObjectStore, cid: str) -> str:
    row = store.db.execute(
        "SELECT root_hash, kind FROM commits WHERE id=?", (cid,)
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown commit {cid}")
    root_hash, kind = row
    if kind not in (None, "md", "txt"):
        raise NotImplementedError(
            f"prose merge supports md/txt artifacts only (commit {cid} kind={kind!r})"
        )
    return store.get_blob(root_hash).decode("utf-8")


def merge_commits(
    store: ObjectStore,
    artifact_id: str,
    ours_head: str,
    theirs_head: str,
    *,
    branch: str = "main",
    message: str = "merge",
    author: str = "muneer",
    author_date: str | None = None,
    kind: str = "md",
) -> MergeOutcome:
    """Full 3-way merge against the DAG (merge-spec.md lifecycle).

    base = content at store.merge_base(ours_head, theirs_head) (empty string
    when the DAGs share no ancestor -> everything is an addition). Clean
    merges auto-finalize: result blob + 2-parent commit [ours_head,
    theirs_head] advancing the OUR branch, CAS-guarded on ours_head
    (RefConflictError -> HTTP 409 upstream). Conflicted merges do NOT move
    any ref; the API layer persists Merge(pending) + Conflict rows and waits
    for per-conflict resolution before composing the final commit (T7/T8).
    """
    base_commit = store.merge_base(ours_head, theirs_head)
    base_text = _commit_text(store, base_commit) if base_commit else ""
    result = merge_prose(
        base_text, _commit_text(store, ours_head), _commit_text(store, theirs_head)
    )
    result_commit = None
    if result.state == "clean":
        root = store.put_blob(kind, result.merged_text.encode("utf-8"))
        result_commit = store.commit(
            [ours_head, theirs_head], root, artifact_id, message, author,
            author_date=author_date, branch=branch, expected_head=ours_head, kind=kind,
        )
    return MergeOutcome(result, base_commit, ours_head, theirs_head, result_commit)
# ReGit Changelog

## 2026-08-22 — Versioning DAG layer + prose alignment spine (H1/H2/H4 reference implementation)

No specs were rewritten; these notes record spec-vs-code interpretations and
drift found while implementing `backend/src/core/objects/store.py` and
`backend/src/core/diff/align.py`. Review with Muneer.

**Spec drift / interpretations (code deviates in shape, not semantics):**

- **`Change.sid` vs `Change.span` naming.** `docs/data-model.md` Change record
  is `{sid|span, ...}`; `core/models.py` names the field `span`, while
  `diff-spec.md` and the `align.py` stub both say `sid`. `diff_prose()` emits
  dicts with key **`sid`** (diff-spec.md is the diff engine's spec of record).
  Recommend renaming `models.Change.span` → `sid` (or documenting the alias).
- **`refs` vs `branches` tables.** data-model.md DDL defines BOTH
  `refs(name, artifact_id, head)` and `branches(..., head_commit_id, created_at)`.
  `ObjectStore` treats `refs` as the operational CAS table (source of truth)
  and `branches` as a metadata mirror kept in sync in the same transaction.
  No drift in behavior; the duplication is spec-authored.
- **`merge_base` "height" definition.** adr-03 says "ties broken by lowest
  height then hash order" without defining height; implementation uses
  `height = dist_from(c1) + dist_from(c2)` (shortest BFS distances back to the
  two heads), final tie-break lower commit id (hash). Deterministic; verified
  on diamond and criss-cross DAGs.
- **`commit()` signature extends the stub.** Added keyword params
  `branch="main"`, `expected_head=None`, `kind=None` — required by
  api-contract.md (`{branch, content, message, base_commit?}` → stale base_commit
  is 409) and versioning-spec.md's "ref CAS update (WHERE head = :expected)".
  Callers with no `expected_head` get the read-inside-transaction CAS
  (serialized per artifact via `BEGIN IMMEDIATE`).
- **2-parent commits "must link a Merge row"** (data-model.md) is enforced at
  the merge service layer (merge-spec.md lifecycle), NOT in `ObjectStore.commit`
  — the store is a primitive and doesn't know about `merges`.
- **`diff_prose` sids are `para:sent` by default.** The full `artifact:para:sent`
  sid needs artifact context, which the primitive doesn't have; pass
  `artifact_id=` to compose it, otherwise the API layer must prefix.
- **"moved" detection.** Equal-hash sentence pairs whose paragraph offset
  differs from the modal offset of the whole alignment → `moved` (a uniform
  offset, e.g. a heading prepended, is NOT a move). Known limitation: a
  paragraph reorder that crosses an LCS anchor surfaces as delete+add for one
  of the swapped paragraphs (LCS is order-preserving; documented in align.py).
- **`split_paragraphs` canonicalizes** blocks (`.strip()`), so a trailing
  newline after the last paragraph is not part of paragraph identity.
- **`author_date` resolution** in `commit()`: explicit param > `GR_AUTHOR_DATE`
  env > wall clock; the resolved value is what lands in `commits.author_date`
  and what was hashed (hashutil.commit_id), so `verify()` stays exact.

**Added:** `ObjectStore.commit/merge_base/verify/history/head/create_branch/
advance_branch` (store.py); `align/diff_prose` (align.py); unit tests
`tests/unit/test_commit.py`, `tests/unit/test_align.py`; invariant test
`test_branch_is_mutable_ref_to_immutable_commit` turned green (real test,
not weakened). Baseline was 3 passed / 4 xfailed; now 35 passed / 3 xfailed.

## 2026-08-22 — 3-way prose merge engine (H5 reference implementation)

Implements `backend/src/core/merge/three_way.py` per merge-spec.md / ADR-05,
reusing the align spine (`align()` over flattened sentences) and
`ObjectStore.merge_base()/commit()`. No specs were rewritten; these notes
record the interpretations and drift found while implementing. Review with
Muneer.

**Spec drift / interpretations (code deviates in shape, not semantics):**

- **`insert_conflict` is informational, not a resolution card.** merge-spec.md
  says "insertions at same anchor in both sides: keep both (ours then theirs),
  mark insert_conflict" without defining the marker's payload. Since both
  texts are KEPT, the merged text is already decided — a resolution card would
  be unresolvable. Implemented as `MergeResult.insert_overlaps:
  [InsertOverlapRec]` (sid/ours_text/theirs_text); it does NOT set
  state=conflicts, so an insert overlap does not block auto-finalize. UI can
  render it as an ordering hint.
- **Conflict markers carry the sid.** Prose markers are git-style
  `<<<<<<< ours {sid} / ======= / >>>>>>> theirs` instead of bare
  `<<<<<<< ours`. The sid makes `compose_final_text()` replacement exact and
  order-independent (identical ours/theirs text on two different sids cannot
  collide) and lets the UI map a marker back to its Conflict row. Code-floor
  markers in merge-spec.md are line-level and stay as spec'd.
- **Both-sides delete = convergent removal, NOT a conflict.** The decision
  table's convergent rule (`text(ca) == text(cb)`) covers deletions: both
  tips agree the sentence is gone, so nothing is dropped and no conflict is
  emitted. Invariant 6 still holds — delete-vs-edit (either direction) and
  divergent edits always yield Conflict records.
- **`merge_commits()` advances the OUR branch with a CAS guard**
  (`expected_head=ours_head` → RefConflictError → 409 upstream), matching
  api-contract.md. Persisting the `Merge`/`Conflict` rows themselves stays in
  the API layer (merge-spec.md lifecycle); the engine emits the records and
  the 2-parent commit.
- **merged_text paragraph skeleton comes from BASE.** Each output sentence
  joins the paragraph of the base sentence it derives from; inserted
  sentences join the paragraph of the base sentence they precede (all inserts
  at the same anchor therefore share one paragraph). Source-side paragraph
  boundaries of insertions are flattened — documented crudeness, deterministic.
- **Empty merge base (disjoint DAGs) → everything is a same-anchor insert.**
  Both tips' full documents are kept, ours then theirs, in one paragraph —
  the deterministic root-merge fallback (and it is flagged as an insert
  overlap when both sides have content).
- **Low-similarity rewrites (< 0.7) surface as delete+insert** (diff-spec.md
  threshold, locked) and therefore merge as delete-vs-* rather than
  edit-vs-*; the rewrite text is still kept as an anchored insert. Tests and
  the demo fixture use ≥ 0.7 edits so the conflict path is exercised exactly
  as the spec's T2/T4 contracts describe.

**Added:** `merge_prose/compose_final_text/merge_commits` + `MergeConflictRec`,
`InsertOverlapRec`, `MergeResult`, `MergeOutcome` (three_way.py); unit tests
`tests/unit/test_merge.py` (T1-T7 + demo fixture exact shape + determinism);
invariant test `test_merge_never_silently_discards` turned green (real test,
not weakened). Baseline was 35 passed / 3 xfailed; now 52 passed / 2 xfailed.
`tests/integration/test_api.py::test_merge_stub_returns_501` was updated to
the real clean-merge path (merge main into main -> state clean, 2-parent
result commit, head advanced) — the engine replaced the stub.